import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TELEGRAM_TOKEN_ENCRYPTION_KEY", "InHwts8E1W6J6PyE8QXIkYTiX-c6jOi4E2vNT6Gf0lA=")

import httpx
from provisao_api.config import Settings
from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import Attachment, Channel, ChannelBot, Company, Conversation, ConversationMessage, ExternalEvent, OutboxEvent
from provisao_api.services.conversations import process_pending_outbox, queue_outbound_message
from provisao_api.services.crypto import CredentialCipher, masked_token, token_fingerprint
from provisao_api.services.delivery import TelegramOutboxDelivery
from provisao_api.services.inbox_worker import process_event_batch
from provisao_api.services.storage import LocalStorage, detect_mime
from provisao_api.services.telegram import normalize_update


TOKEN="123456:fake-token-for-contract-tests"


class FakeTelegram:
    def __init__(self): self.sent=[]
    def __call__(self, request: httpx.Request) -> httpx.Response:
        method=request.url.path.rsplit("/",1)[-1]
        if method=="getMe": result={"id":123456,"is_bot":True,"username":"provisao_test_bot"}
        elif method=="getFile": result={"file_id":"photo-1","file_path":"photos/photo-1.jpg","file_size":12}
        elif method in {"sendMessage","sendPhoto","sendDocument","sendAudio","sendVideo"}:
            self.sent.append(method); result={"message_id":9001}
        elif method in {"setWebhook","deleteWebhook"}: result=True
        elif method=="getWebhookInfo": result={"url":"https://example.test/webhook","pending_update_count":0}
        elif method=="getUpdates": result=[]
        elif "/file/" in request.url.path or request.url.path.endswith("photo-1.jpg"):
            return httpx.Response(200,content=b"\xff\xd8\xffcontract-image")
        else: return httpx.Response(404,json={"ok":False,"description":"unknown method"})
        return httpx.Response(200,json={"ok":True,"result":result})


def update(update_id=10, message_id=20):
    return {"update_id":update_id,"message":{"message_id":message_id,"date":1700000000,"from":{"id":77,"first_name":"Ana","username":"not-an-identity"},"chat":{"id":88,"type":"private"},"caption":"Falha no equipamento","photo":[{"file_id":"small"},{"file_id":"photo-1","file_size":12}]}}


class TelegramVerticalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=SessionLocal(); self.fake=FakeTelegram()
        self.cfg=Settings(app_secret_key="test-secret-with-sufficient-length",database_url="sqlite+pysqlite:///:memory:",redis_url="redis://localhost",telegram_token_encryption_key=os.environ["TELEGRAM_TOKEN_ENCRYPTION_KEY"],storage_root=self.temp.name,telegram_api_base_url="https://telegram.test",telegram_file_base_url="https://telegram.test/file")
        company=Company(name=f"Vertical {uuid.uuid4()}"); self.db.add(company); self.db.flush(); self.company=company
        channel=Channel(company_id=company.id,kind="telegram",name=f"Bot {uuid.uuid4()}"); self.db.add(channel); self.db.flush(); self.channel=channel
        cipher=CredentialCipher(self.cfg.telegram_token_encryption_key)
        bot=ChannelBot(company_id=company.id,channel_id=channel.id,name=channel.name,public_id=str(uuid.uuid4()),active=True,token_ciphertext=cipher.encrypt(TOKEN),token_fingerprint=token_fingerprint(TOKEN),mode="webhook",status="active")
        self.db.add(bot); self.db.commit(); self.bot=bot

    def tearDown(self): self.db.rollback(); self.db.close(); self.temp.cleanup()

    def test_token_is_authenticated_encrypted_and_masked(self):
        cipher=CredentialCipher(self.cfg.telegram_token_encryption_key); encrypted=cipher.encrypt(TOKEN)
        self.assertNotIn(TOKEN,encrypted); self.assertEqual(cipher.decrypt(encrypted),TOKEN)
        self.assertNotIn(TOKEN,masked_token(token_fingerprint(TOKEN)))
        with self.assertRaises(ValueError): CredentialCipher("not-a-fernet-key")

    def test_media_update_to_inbox_and_outbox_delivery(self):
        payload=update(); event=ExternalEvent(company_id=self.company.id,channel_id=self.channel.id,bot_id=self.bot.id,external_event_id="10",idempotency_key=f"telegram:{self.bot.id}:10",payload=payload,status="received")
        self.db.add(event); self.db.commit()
        processed=process_event_batch(self.db,self.cfg,transport=httpx.MockTransport(self.fake)); self.db.commit()
        self.assertGreaterEqual(processed,1); self.assertEqual(event.status,"processed")
        conversation=self.db.query(Conversation).filter_by(bot_id=self.bot.id).one(); self.assertEqual(conversation.status,"queued")
        inbound=self.db.query(ConversationMessage).filter_by(conversation_id=conversation.id,direction="inbound").one(); self.assertEqual(inbound.message_type,"image")
        attachment=self.db.query(Attachment).filter_by(message_id=inbound.id).one(); self.assertEqual(attachment.detected_mime_type,"image/jpeg")
        self.assertEqual(LocalStorage(self.temp.name).read(attachment.storage_key),b"\xff\xd8\xffcontract-image")
        _,outbox,_=queue_outbound_message(self.db,conversation=conversation,channel=self.channel,author_name="Atendente",body="Recebemos sua foto",idempotency_key="reply-contract-0001",bot_id=self.bot.id); self.db.commit()
        count=process_pending_outbox(self.db,TelegramOutboxDelivery(self.db,self.cfg,transport=httpx.MockTransport(self.fake)),worker_id="test")
        self.assertEqual(count,1); self.assertEqual(outbox.status,"sent"); self.assertEqual(self.fake.sent,["sendMessage"])

    def test_duplicate_event_and_expired_lock(self):
        conversation=Conversation(company_id=self.company.id,channel="telegram",channel_id=self.channel.id,bot_id=self.bot.id,subject="88",status="queued"); self.db.add(conversation); self.db.flush()
        _,event,_=queue_outbound_message(self.db,conversation=conversation,channel=self.channel,author_name="A",body="B",idempotency_key="unique-outbox-lock",bot_id=self.bot.id); event.status="processing"; event.locked_at=__import__("datetime").datetime.now(__import__("datetime").UTC); event.locked_by="other"; self.db.commit()
        self.assertEqual(process_pending_outbox(self.db,lambda _:None,worker_id="test",lock_seconds=60),0)

    def test_failed_media_download_rolls_back_partial_message_for_retry(self):
        self.cfg.max_image_bytes=5; payload=update(update_id=333,message_id=444); event=ExternalEvent(company_id=self.company.id,channel_id=self.channel.id,bot_id=self.bot.id,external_event_id="333",idempotency_key=f"telegram:{self.bot.id}:333",payload=payload,status="received");self.db.add(event);self.db.commit()
        self.assertEqual(process_event_batch(self.db,self.cfg,transport=httpx.MockTransport(self.fake)),0);self.db.commit()
        self.assertEqual(event.status,"retry");self.assertEqual(event.attempts,1)
        self.assertEqual(self.db.query(ConversationMessage).filter_by(provider_update_id="333").count(),0)

    def test_normalization_and_storage_reject_spoofing_and_traversal(self):
        envelope=normalize_update(update(),self.bot.id); self.assertEqual(envelope.message_type,"image"); self.assertEqual(envelope.external_user_id,"77")
        storage=LocalStorage(self.temp.name)
        with self.assertRaises(ValueError): storage.store(b"",max_bytes=10)
        with self.assertRaises(ValueError): storage.store(b"MZ malicious executable",max_bytes=100)
        with self.assertRaises(ValueError): storage.read("../../etc/passwd")
        self.assertEqual(detect_mime(b"%PDF-1.7\n"),"application/pdf")


if __name__=="__main__": unittest.main()

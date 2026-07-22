import json
import os
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("APP_SECRET_KEY","test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL","sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL","redis://localhost:6379/0")
os.environ.setdefault("TELEGRAM_TOKEN_ENCRYPTION_KEY","InHwts8E1W6J6PyE8QXIkYTiX-c6jOi4E2vNT6Gf0lA=")

from fastapi import HTTPException
from starlette.requests import Request
from provisao_api.db import Base,SessionLocal,engine
from provisao_api.main import BotCreateIn,create_bot,telegram_webhook,token_hash
from provisao_api.models import Channel,ChannelBot,Company,ExternalEvent,User


def request_for(payload:dict,secret:str)->Request:
    body=json.dumps(payload).encode(); sent=False
    async def receive():
        nonlocal sent
        if sent:return {"type":"http.disconnect"}
        sent=True;return {"type":"http.request","body":body,"more_body":False}
    return Request({"type":"http","method":"POST","path":"/","headers":[(b"x-telegram-bot-api-secret-token",secret.encode())]},receive)


class TelegramApiTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)
    def setUp(self):
        self.db=SessionLocal();company=Company(name=f"API {uuid.uuid4()}");self.db.add(company);self.db.flush();self.user=User(company_id=company.id,email=f"admin-{uuid.uuid4()}@example.test",name="Admin",password_hash="unused");self.db.add(self.user);self.db.commit();self.company_id=company.id
    def tearDown(self):self.db.rollback();self.db.close()

    def test_bot_token_is_encrypted_and_never_returned(self):
        token="123456:plain-secret-token-value"
        with patch("provisao_api.main.TelegramClient.get_me",return_value={"id":123456,"username":"safe_bot"}):
            body=create_bot(BotCreateIn(name=f"Bot {uuid.uuid4()}",token=token,mode="webhook"),self.user,self.db)
        self.assertNotIn(token,json.dumps(body,default=str));self.assertNotIn("token_ciphertext",body)
        bot=self.db.get(ChannelBot,body["id"]);self.assertNotIn(token,bot.token_ciphertext)

    async def test_webhook_validates_secret_and_deduplicates(self):
        secret="webhook-secret-for-test";channel=Channel(company_id=self.company_id,kind="telegram",name=f"Webhook {uuid.uuid4()}");self.db.add(channel);self.db.flush();bot=ChannelBot(company_id=self.company_id,channel_id=channel.id,name=channel.name,public_id=str(uuid.uuid4()),active=True,mode="webhook",status="active",webhook_secret_hash=token_hash(secret));self.db.add(bot);self.db.commit()
        payload={"update_id":901,"message":{"message_id":1,"date":1700000000,"from":{"id":2,"first_name":"A"},"chat":{"id":3},"text":"Olá"}}
        with self.assertRaises(HTTPException) as denied:await telegram_webhook(bot.public_id,request_for(payload,"wrong"),self.db)
        self.assertEqual(denied.exception.status_code,403)
        first=await telegram_webhook(bot.public_id,request_for(payload,secret),self.db);self.assertFalse(first["duplicate"])
        duplicate=await telegram_webhook(bot.public_id,request_for(payload,secret),self.db);self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.db.query(ExternalEvent).filter_by(bot_id=bot.id,external_event_id="901").count(),1)


if __name__=="__main__":unittest.main()

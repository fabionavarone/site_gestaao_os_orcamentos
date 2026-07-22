import os
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from provisao_api.db import Base, engine, SessionLocal
from provisao_api.models import Channel, Company, Conversation, OutboxEvent
from provisao_api.services.conversations import ingest_external_event, process_pending_outbox, queue_outbound_message


class OmnichannelServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)

    def setUp(self):
        self.db = SessionLocal()
        company = Company(name=f"Omnichannel test company {uuid.uuid4()}")
        self.db.add(company); self.db.flush()
        self.company_id = company.id
        self.channel = Channel(company_id=company.id, kind="telegram", name="Primary")
        self.db.add(self.channel); self.db.commit()

    def tearDown(self):
        self.db.rollback(); self.db.close()

    def test_external_envelope_is_idempotent_and_creates_one_inbox_message(self):
        first, created = ingest_external_event(self.db, company_id=self.company_id, channel=self.channel, bot_id=None, external_event_id="update-10", idempotency_key="telegram:primary:update-10", external_sender_id="tg-77", sender_name="Ana", external_chat_id="chat-77", message_type="text", text="Preciso de ajuda")
        self.assertTrue(created); self.db.commit()
        duplicate, created_again = ingest_external_event(self.db, company_id=self.company_id, channel=self.channel, bot_id=None, external_event_id="update-10", idempotency_key="telegram:primary:update-10", external_sender_id="tg-77", sender_name="Ana", external_chat_id="chat-77", message_type="text", text="Preciso de ajuda")
        self.assertFalse(created_again)
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(self.db.query(Conversation).filter_by(company_id=self.company_id).count(), 1)

    def test_outbox_is_idempotent(self):
        conversation = Conversation(company_id=self.company_id, channel="telegram", subject="chat-88")
        self.db.add(conversation); self.db.commit()
        message, event, created = queue_outbound_message(self.db, conversation=conversation, channel=self.channel, author_name="Atendente", body="Olá", idempotency_key="reply:88:1")
        self.assertTrue(created); self.db.commit()
        same_message, same_event, created_again = queue_outbound_message(self.db, conversation=conversation, channel=self.channel, author_name="Atendente", body="Olá", idempotency_key="reply:88:1")
        self.assertFalse(created_again)
        self.assertEqual(message.id, same_message.id)
        self.assertEqual(event.id, same_event.id)
        self.assertEqual(self.db.query(OutboxEvent).filter_by(company_id=self.company_id).count(), 1)

    def test_outbox_retries_then_dead_letters(self):
        conversation = Conversation(company_id=self.company_id, channel="telegram", subject="chat-99")
        self.db.add(conversation); self.db.flush()
        _, event, _ = queue_outbound_message(self.db, conversation=conversation, channel=self.channel, author_name="Atendente", body="Olá", idempotency_key="reply:99:1")
        self.db.commit()
        for _ in range(5):
            event.available_at = event.available_at.replace(year=2000)
            self.db.commit()
            process_pending_outbox(self.db, lambda _: (_ for _ in ()).throw(RuntimeError("gateway offline")))
            self.db.commit()
        self.assertEqual(event.status, "dead_letter")
        self.assertEqual(event.attempts, 5)

import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from provisao_api.db import Base, engine, SessionLocal
from provisao_api.models import AuditLog, Conversation, ConversationMessage, Customer, Equipment, ServiceOrder, ServiceOrderEvent, User

spec = importlib.util.spec_from_file_location("sqlite_import", Path(__file__).parents[3] / "scripts" / "import_sqlite.py")
sqlite_import = importlib.util.module_from_spec(spec); spec.loader.exec_module(sqlite_import)

class SQLiteImportTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
        self.path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        source = sqlite3.connect(self.path)
        source.executescript("""
          CREATE TABLE users (id TEXT PRIMARY KEY,name TEXT,email TEXT,password_hash TEXT,role TEXT,active INTEGER,created_at TEXT);
          CREATE TABLE customers (id TEXT PRIMARY KEY,name TEXT,document TEXT,email TEXT,phone TEXT,kind TEXT,created_at TEXT);
          CREATE TABLE equipment (id TEXT PRIMARY KEY,customer_id TEXT,category TEXT,manufacturer TEXT,model TEXT,serial_number TEXT,internal_code TEXT,notes TEXT,created_at TEXT);
          CREATE TABLE service_orders (id TEXT PRIMARY KEY,number INTEGER,customer_id TEXT,equipment_id TEXT,title TEXT,symptom TEXT,priority TEXT,status TEXT,assigned_to TEXT,created_at TEXT,updated_at TEXT);
          CREATE TABLE service_order_events (id TEXT PRIMARY KEY,service_order_id TEXT,actor_id TEXT,event_type TEXT,detail TEXT,created_at TEXT);
          CREATE TABLE conversations (id TEXT PRIMARY KEY,channel TEXT,subject TEXT,customer_id TEXT,status TEXT,assigned_to TEXT,created_at TEXT,updated_at TEXT);
          CREATE TABLE messages (id TEXT PRIMARY KEY,conversation_id TEXT,direction TEXT,author_name TEXT,body TEXT,internal INTEGER,created_at TEXT);
          CREATE TABLE audit_logs (id TEXT PRIMARY KEY,actor_id TEXT,action TEXT,entity_type TEXT,entity_id TEXT,detail TEXT,created_at TEXT);
        """)
        stamp = "2026-01-01T10:00:00+00:00"
        source.execute("INSERT INTO users VALUES ('u1','Ana','ana@example.test','legacy','admin',1,?)", (stamp,))
        source.execute("INSERT INTO customers VALUES ('c1','Cliente','1','c@example.test','55','person',?)", (stamp,))
        source.execute("INSERT INTO equipment VALUES ('e1','c1','Inversor','Marca','M1','S1','EQ-1','',?)", (stamp,))
        source.execute("INSERT INTO service_orders VALUES ('o1',7,'c1','e1','Falha','Nao liga','normal','draft','u1',?,?)", (stamp,stamp))
        source.execute("INSERT INTO service_order_events VALUES ('oe1','o1','u1','created','Criada',?)", (stamp,))
        source.execute("INSERT INTO conversations VALUES ('v1','telegram','Chat','c1','human_queue','u1',?,?)", (stamp,stamp))
        source.execute("INSERT INTO messages VALUES ('m1','v1','inbound','Cliente','Ola',0,?)", (stamp,))
        source.execute("INSERT INTO audit_logs VALUES ('a1','u1','create','customer','c1','Cliente',?)", (stamp,))
        source.commit(); source.close()

    def tearDown(self): Path(self.path).unlink(missing_ok=True)

    def test_import_preserves_counts_and_relationships_idempotently(self):
        first = sqlite_import.import_database(Path(self.path), "Empresa importada")
        self.assertEqual(first, {"users": 1, "customers": 1, "equipment": 1, "service_orders": 1, "events": 1, "conversations": 1, "messages": 1, "audit_logs": 1})
        self.assertTrue(all(value == 0 for value in sqlite_import.import_database(Path(self.path), "Empresa importada").values()))
        session = SessionLocal()
        self.assertFalse(session.get(User, "u1").active)
        self.assertEqual(session.get(Equipment, "e1").customer_id, session.get(Customer, "c1").id)
        self.assertEqual(session.get(ServiceOrder, "o1").equipment_id, "e1")
        self.assertEqual(session.get(ServiceOrderEvent, "oe1").service_order_id, "o1")
        self.assertEqual(session.get(ConversationMessage, "m1").conversation_id, session.get(Conversation, "v1").id)
        self.assertEqual(session.query(AuditLog).count(), 1)
        session.close()

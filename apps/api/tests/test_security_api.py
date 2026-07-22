import os
import unittest

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from fastapi.testclient import TestClient
from provisao_api.db import Base, engine, SessionLocal
from provisao_api.main import app, pwd
from provisao_api.models import Company, User


class SecurityApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
        db = SessionLocal()
        company = Company(name="Empresa de teste")
        db.add(company); db.flush()
        db.add(User(company_id=company.id, name="Operador", email="operator@example.com", password_hash=pwd.hash("a-strong-test-password")))
        db.commit(); db.close()

    def setUp(self):
        self.client = TestClient(app)

    def login(self):
        result = self.client.post("/api/v1/auth/login", json={"email":"operator@example.com", "password":"a-strong-test-password"})
        self.assertEqual(result.status_code, 200)
        return result.json()["csrf_token"]

    def test_login_requires_valid_credentials_and_csrf(self):
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email":"operator@example.com", "password":"wrong-password-value"}).status_code, 401)
        csrf = self.login()
        self.assertEqual(self.client.post("/api/v1/customers", json={"name":"Cliente"}).status_code, 403)
        ok = self.client.post("/api/v1/customers", headers={"X-CSRF-Token":csrf}, json={"name":"Cliente"})
        self.assertEqual(ok.status_code, 201)

    def test_customer_tenant_scope_and_equipment(self):
        csrf = self.login()
        customer = self.client.post("/api/v1/customers", headers={"X-CSRF-Token":csrf}, json={"name":"Cliente A"}).json()["id"]
        result = self.client.post("/api/v1/equipment", headers={"X-CSRF-Token":csrf}, json={"customer_id":customer,"category":"Inversor"})
        self.assertEqual(result.status_code, 201)
        denied = self.client.post("/api/v1/equipment", headers={"X-CSRF-Token":csrf}, json={"customer_id":"other-tenant","category":"Inversor"})
        self.assertEqual(denied.status_code, 404)

if __name__ == "__main__": unittest.main()

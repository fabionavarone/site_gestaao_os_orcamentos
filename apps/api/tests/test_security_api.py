import os
import unittest

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import httpx
from provisao_api.db import Base, engine, SessionLocal
from provisao_api.main import app, pwd
from provisao_api.models import Company, User


class SecurityApiTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
        db = SessionLocal()
        company = Company(name="Empresa de teste")
        db.add(company); db.flush()
        db.add(User(company_id=company.id, name="Operador", email="operator@example.com", password_hash=pwd.hash("a-strong-test-password")))
        db.commit(); db.close()

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def login(self):
        result = await self.client.post("/api/v1/auth/login", json={"email":"operator@example.com", "password":"a-strong-test-password"})
        self.assertEqual(result.status_code, 200)
        return result.json()["csrf_token"]

    async def test_login_requires_valid_credentials_and_csrf(self):
        self.assertEqual((await self.client.post("/api/v1/auth/login", json={"email":"operator@example.com", "password":"wrong-password-value"})).status_code, 401)
        csrf = await self.login()
        self.assertEqual((await self.client.post("/api/v1/customers", json={"name":"Cliente"})).status_code, 403)
        ok = await self.client.post("/api/v1/customers", headers={"X-CSRF-Token":csrf}, json={"name":"Cliente"})
        self.assertEqual(ok.status_code, 201)

    async def test_customer_tenant_scope_and_equipment(self):
        csrf = await self.login()
        customer = (await self.client.post("/api/v1/customers", headers={"X-CSRF-Token":csrf}, json={"name":"Cliente A"})).json()["id"]
        result = await self.client.post("/api/v1/equipment", headers={"X-CSRF-Token":csrf}, json={"customer_id":customer,"category":"Inversor"})
        self.assertEqual(result.status_code, 201)
        denied = await self.client.post("/api/v1/equipment", headers={"X-CSRF-Token":csrf}, json={"customer_id":"other-tenant","category":"Inversor"})
        self.assertEqual(denied.status_code, 404)

if __name__ == "__main__": unittest.main()

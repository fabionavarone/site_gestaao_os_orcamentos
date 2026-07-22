import os
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from sqlalchemy import select
from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import Company, Customer, User
from provisao_api.crm_api import AddressPayload, ContactPayload, CustomerPayload, build_router

class CrmApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)
    def setUp(self):
        self.db = SessionLocal(); self.company = Company(name=f"CRM {uuid.uuid4()}"); other = Company(name=f"CRM other {uuid.uuid4()}"); self.db.add_all([self.company, other]); self.db.flush()
        self.user = User(company_id=self.company.id, name="CRM Admin", email=f"crm-{uuid.uuid4()}@example.test", password_hash="unused"); self.other_user = User(company_id=other.id, name="Other", email=f"other-{uuid.uuid4()}@example.test", password_hash="unused"); self.db.add_all([self.user, self.other_user]); self.db.commit()
        self.router = build_router(lambda: None, lambda _: lambda: self.user, lambda *args, **kwargs: None)
    def tearDown(self): self.db.rollback(); self.db.close()
    def endpoint(self, path, method):
        return next(route.endpoint for route in self.router.routes if route.path == path and method in route.methods)
    def test_customer_normalizes_and_rejects_duplicate_document(self):
        create = self.endpoint("/api/v1/crm/customers", "POST")
        payload = CustomerPayload(name="Acme", customer_type="company", document="12.345.678/0001-90", email="ACME@EXAMPLE.COM", phone="(11) 99999-0000")
        first = create(payload, self.user, self.db); self.assertEqual(first["status"], "active")
        stored = self.db.get(Customer, first["id"]); self.assertEqual(stored.normalized_document, "12345678000190"); self.assertEqual(stored.normalized_email, "acme@example.com"); self.assertEqual(stored.normalized_phone, "11999990000")
        with self.assertRaises(Exception) as duplicate: create(payload, self.user, self.db)
        self.assertIn("duplicate", str(duplicate.exception))
    def test_contacts_addresses_and_tenant_isolation(self):
        create = self.endpoint("/api/v1/crm/customers", "POST"); customer = create(CustomerPayload(name="Cliente"), self.user, self.db); self.db.commit()
        contact = self.endpoint("/api/v1/crm/customers/{customer_id}/contacts", "POST")(customer["id"], ContactPayload(name="Contato", email="contato@example.com"), self.user, self.db)
        address = self.endpoint("/api/v1/crm/customers/{customer_id}/addresses", "POST")(customer["id"], AddressPayload(street="Rua A", city="São Paulo", state="SP"), self.user, self.db)
        self.assertEqual(contact["name"], "Contato"); self.assertEqual(address["city"], "São Paulo")
        get = self.endpoint("/api/v1/crm/customers/{customer_id}", "GET"); self.assertEqual(len(get(customer["id"], self.user, self.db)["contacts"]), 1)
        updated_contact = self.endpoint("/api/v1/crm/customers/{customer_id}/contacts/{contact_id}", "PATCH")(customer["id"], contact["id"], ContactPayload(name="Contato atualizado", email="novo@example.com"), self.user, self.db)
        updated_address = self.endpoint("/api/v1/crm/customers/{customer_id}/addresses/{address_id}", "PATCH")(customer["id"], address["id"], AddressPayload(street="Rua B", city="Campinas", state="SP"), self.user, self.db)
        self.assertEqual(updated_contact["name"], "Contato atualizado"); self.assertEqual(updated_address["street"], "Rua B")
        with self.assertRaises(Exception): get(customer["id"], self.other_user, self.db)

if __name__ == "__main__": unittest.main()

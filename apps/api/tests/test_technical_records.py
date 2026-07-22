import os
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from fastapi import HTTPException

from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import ChecklistTemplate, Company, Customer, ServiceOrder, ServiceOrderDiagnosis, User
from provisao_api.operations_api import IntakePayload, build_router as build_operations_router
from provisao_api.technical_api import (
    ChecklistTemplatePayload,
    ChecklistUpdatePayload,
    DiagnosisPayload,
    MeasurementPayload,
    ReviewPayload,
    TechnicalTestPayload,
    build_router,
)


class TechnicalRecordsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)

    def setUp(self):
        self.db = SessionLocal()
        self.company = Company(name=f"Technical {uuid.uuid4()}")
        self.db.add(self.company)
        self.db.flush()
        self.user = User(company_id=self.company.id, name="Technician", email=f"tech-{uuid.uuid4()}@example.test", password_hash="unused")
        self.customer = Customer(company_id=self.company.id, name="Customer")
        self.db.add_all([self.user, self.customer])
        self.db.commit()
        allow = lambda _permission: (lambda: self.user)
        self.operations = build_operations_router(lambda: self.user, allow, lambda *args, **kwargs: None)
        self.router = build_router(lambda: self.user, allow, lambda *args, **kwargs: None)
        create = self.endpoint(self.operations, "/api/v1/service-orders/from-conversation", "POST")
        self.order = create(IntakePayload(customer_id=self.customer.id, title="Technical intake"), self.user, self.db)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    @staticmethod
    def endpoint(router, path, method):
        return next(route.endpoint for route in router.routes if route.path == path and method in route.methods)

    def test_diagnosis_review_approval_and_new_version(self):
        create = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/diagnoses", "POST")
        submit = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/diagnoses/{diagnosis_id}/submit-review", "POST")
        approve = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/diagnoses/{diagnosis_id}/approve", "POST")
        first = create(self.order["id"], DiagnosisPayload(summary="Fonte em curto", repairable=True), self.user, self.db)
        self.assertEqual(first["version"], 1)
        self.assertEqual(submit(self.order["id"], first["id"], ReviewPayload(), self.user, self.db)["status"], "under_review")
        self.assertEqual(approve(self.order["id"], first["id"], ReviewPayload(reason="Validado"), self.user, self.db)["status"], "approved")
        with self.assertRaises(HTTPException):
            approve(self.order["id"], first["id"], ReviewPayload(), self.user, self.db)
        second = create(self.order["id"], DiagnosisPayload(summary="Fonte substituída", repairable=True), self.user, self.db)
        self.assertEqual(second["version"], 2)
        self.assertEqual(self.db.get(ServiceOrderDiagnosis, first["id"]).status, "superseded")

    def test_measurement_and_technical_test_are_recorded(self):
        measurement = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/measurements", "POST")
        technical_test = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/technical-tests", "POST")
        result = measurement(self.order["id"], MeasurementPayload(parameter="Tensão", value="12", unit="V"), self.user, self.db)
        self.assertEqual(result["parameter"], "Tensão")
        result = technical_test(self.order["id"], TechnicalTestPayload(name="Teste de carga", status="passed"), self.user, self.db)
        self.assertEqual(result["status"], "passed")

    def test_published_checklist_is_immutable_and_completion_requires_required_items(self):
        create = self.endpoint(self.router, "/api/v1/checklist-templates", "POST")
        publish = self.endpoint(self.router, "/api/v1/checklist-templates/{template_id}/publish", "POST")
        assign = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/checklists", "POST")
        update = self.endpoint(self.router, "/api/v1/service-orders/{order_id}/checklists/{checklist_id}", "PATCH")
        template = create(ChecklistTemplatePayload(name="Recepção", items=[{"code": "power", "label": "Liga", "required": True}]), self.user, self.db)
        self.assertEqual(publish(template["id"], self.user, self.db)["status"], "published")
        checklist = assign(self.order["id"], template["id"], self.user, self.db)
        with self.assertRaises(HTTPException):
            update(self.order["id"], checklist["id"], ChecklistUpdatePayload(items=[]), self.user, self.db)
        completed = update(self.order["id"], checklist["id"], ChecklistUpdatePayload(items=[{"code": "power", "label": "Liga", "required": True, "value": True}]), self.user, self.db)
        self.assertEqual(completed["status"], "completed")
        with self.assertRaises(HTTPException):
            publish(template["id"], self.user, self.db)


if __name__ == "__main__":
    unittest.main()

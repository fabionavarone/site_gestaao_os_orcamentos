import os
import unittest
import uuid
from datetime import UTC, datetime, timedelta
os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
from fastapi import HTTPException
from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import Company, Customer, ServiceOrder, User
from provisao_api.operations_api import IntakePayload, build_router as build_operations_router
from provisao_api.completion_api import (CompletePayload, DeliveryPayload, ReturnPayload, VisitPayload, VisitStatePayload, WarrantyPayload, WorkPayload, WorkStatePayload, build_router)
from provisao_api.technical_api import DiagnosisPayload, ReviewPayload, build_router as build_technical_router

class CompletionOperationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)
    def setUp(self):
        self.db=SessionLocal(); self.company=Company(name=f"Completion {uuid.uuid4()}"); self.db.add(self.company); self.db.flush(); self.user=User(company_id=self.company.id,name="Tech",email=f"completion-{uuid.uuid4()}@example.test",password_hash="unused"); self.customer=Customer(company_id=self.company.id,name="Customer"); self.db.add_all([self.user,self.customer]); self.db.commit(); allow=lambda _permission: (lambda:self.user); self.router=build_router(lambda:self.user,allow,lambda *args,**kwargs:None); op=build_operations_router(lambda:self.user,allow,lambda *args,**kwargs:None); create=next(x.endpoint for x in op.routes if x.path=="/api/v1/service-orders/from-conversation"); self.order=create(IntakePayload(customer_id=self.customer.id,title="Repair"),self.user,self.db); tech=build_technical_router(lambda:self.user,allow,lambda *args,**kwargs:None); self.create_diagnosis=next(x.endpoint for x in tech.routes if x.path=="/api/v1/service-orders/{order_id}/diagnoses" and "POST" in x.methods); self.submit_diagnosis=next(x.endpoint for x in tech.routes if x.path.endswith("submit-review")); self.approve_diagnosis=next(x.endpoint for x in tech.routes if x.path.endswith("/approve"))
    def tearDown(self): self.db.rollback();self.db.close()
    def endpoint(self,path,method): return next(x.endpoint for x in self.router.routes if x.path==path and method in x.methods)
    def test_work_session_visit_delivery_warranty_and_return(self):
        start=self.endpoint("/api/v1/service-orders/{order_id}/work-sessions","POST"); state=self.endpoint("/api/v1/service-orders/{order_id}/work-sessions/{session_id}","PATCH")
        work=start(self.order["id"],WorkPayload(mode="bench"),self.user,self.db); self.assertEqual(state(self.order["id"],work["id"],WorkStatePayload(status="completed",result="Reparo concluído"),self.user,self.db)["status"],"completed")
        visit=self.endpoint("/api/v1/service-orders/{order_id}/visits","POST")(self.order["id"],VisitPayload(address="Rua A, 10",scheduled_start=datetime.now(UTC)+timedelta(days=1)),self.user,self.db); self.assertEqual(self.endpoint("/api/v1/service-orders/{order_id}/visits/{visit_id}","PATCH")(self.order["id"],visit["id"],VisitStatePayload(status="confirmed"),self.user,self.db)["status"],"confirmed")
        warranty=self.endpoint("/api/v1/service-orders/{order_id}/warranty","POST")(self.order["id"],WarrantyPayload(starts_at=datetime.now(UTC),ends_at=datetime.now(UTC)+timedelta(days=90),coverage="Reparo"),self.user,self.db); self.assertEqual(warranty["status"],"active")
        returned=self.endpoint("/api/v1/service-orders/{order_id}/warranty-return","POST")(self.order["id"],ReturnPayload(reason="Falha recorrente"),self.user,self.db); self.assertEqual(returned["original_service_order_id"],self.order["id"])
    def test_delivery_closes_order_and_rejects_duplicate(self):
        deliver=self.endpoint("/api/v1/service-orders/{order_id}/delivery","POST"); result=deliver(self.order["id"],DeliveryPayload(mode="pickup",condition="OK"),self.user,self.db); self.assertEqual(result["status"],"closed")
        with self.assertRaises(HTTPException): deliver(self.order["id"],DeliveryPayload(mode="pickup"),self.user,self.db)
    def test_assignment_and_sla_pause_resume(self):
        assignment=self.endpoint("/api/v1/service-orders/{order_id}/assignment","PATCH")
        result=assignment(self.order["id"],__import__("provisao_api.completion_api",fromlist=["AssignmentPayload"]).AssignmentPayload(technician_id=self.user.id),self.user,self.db); self.assertEqual(result["status"],"assigned")
        sla=self.endpoint("/api/v1/service-orders/{order_id}/sla/{action}","POST"); paused=sla(self.order["id"],"pause",self.user,self.db); self.assertIsNotNone(paused["sla_paused_at"]); resumed=sla(self.order["id"],"resume",self.user,self.db); self.assertIsNone(resumed["sla_paused_at"])
    def test_completion_requires_approved_diagnosis(self):
        complete=self.endpoint("/api/v1/service-orders/{order_id}/complete","POST")
        with self.assertRaises(HTTPException): complete(self.order["id"],CompletePayload(),self.user,self.db)
        diagnosis=self.create_diagnosis(self.order["id"],DiagnosisPayload(summary="Reparo aprovado"),self.user,self.db); self.submit_diagnosis(self.order["id"],diagnosis["id"],ReviewPayload(),self.user,self.db); self.approve_diagnosis(self.order["id"],diagnosis["id"],ReviewPayload(),self.user,self.db)
        result=complete(self.order["id"],CompletePayload(notes="OK"),self.user,self.db); self.assertEqual(result["status"],"completed")
if __name__=="__main__": unittest.main()

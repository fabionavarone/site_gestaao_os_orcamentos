import os, unittest, uuid
os.environ.setdefault("APP_SECRET_KEY","test-secret-with-sufficient-length");os.environ.setdefault("DATABASE_URL","sqlite+pysqlite:///:memory:");os.environ.setdefault("REDIS_URL","redis://localhost:6379/0")
from provisao_api.db import Base,SessionLocal,engine
from provisao_api.models import Company,Customer,User,Conversation
from provisao_api.operations_api import IntakePayload,TaskPayload,TriagePayload,build_router

class ServiceOrderOperationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)
    def setUp(self):
        self.db=SessionLocal();self.company=Company(name=f"OS {uuid.uuid4()}");self.db.add(self.company);self.db.flush();self.user=User(company_id=self.company.id,name="Supervisor",email=f"os-{uuid.uuid4()}@example.test",password_hash="unused");self.customer=Customer(company_id=self.company.id,name="Client");self.db.add_all([self.user,self.customer]);self.db.commit();self.router=build_router(lambda:None,lambda _:lambda:self.user,lambda *args,**kwargs:None)
    def tearDown(self):self.db.rollback();self.db.close()
    def endpoint(self,path,method):return next(x.endpoint for x in self.router.routes if x.path==path and method in x.methods)
    def test_intake_number_triage_tasks_timeline_and_duplicate(self):
        create=self.endpoint("/api/v1/service-orders/from-conversation","POST"); order=create(IntakePayload(customer_id=self.customer.id,title="Diagnóstico de equipamento",symptom="Não liga"),self.user,self.db);self.assertGreater(order["number"],0)
        triage=self.endpoint("/api/v1/service-orders/{order_id}/triage","POST")(order["id"],TriagePayload(powers_on=False,suggested_priority="high"),self.user,self.db);self.assertEqual(triage["suggested_priority"],"high")
        task=self.endpoint("/api/v1/service-orders/{order_id}/tasks","POST")(order["id"],TaskPayload(title="Testar fonte"),self.user,self.db);self.assertEqual(task["status"],"pending")
        dependent=self.endpoint("/api/v1/service-orders/{order_id}/tasks","POST")(order["id"],TaskPayload(title="Registrar resultado",depends_on_task_id=task["id"]),self.user,self.db);self.assertEqual(dependent["depends_on_task_id"],task["id"])
        self.endpoint("/api/v1/service-orders/{order_id}/timeline","POST")(order["id"],__import__("provisao_api.operations_api",fromlist=["TimelinePayload"]).TimelinePayload(detail="Triagem concluída"),self.user,self.db)
        detail=self.endpoint("/api/v1/service-orders/{order_id}","GET")(order["id"],self.user,self.db);self.assertEqual(len(detail["tasks"]),2);self.assertEqual(len(detail["timeline"]),5)
        conversation=Conversation(company_id=self.company.id,channel="web",subject="Origem",status="queued");self.db.add(conversation);self.db.flush()
        create(IntakePayload(customer_id=self.customer.id,conversation_id=conversation.id,title="Abertura"),self.user,self.db)
        with self.assertRaises(Exception):create(IntakePayload(customer_id=self.customer.id,conversation_id=conversation.id,title="Duplicada"),self.user,self.db)

if __name__=="__main__":unittest.main()

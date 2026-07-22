import os, unittest, uuid
os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length"); os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:"); os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import Company, Customer, User
from provisao_api.equipment_api import AccessoryPayload, CatalogPayload, EquipmentPayload, build_router

class EquipmentApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): Base.metadata.create_all(engine)
    def setUp(self):
        self.db=SessionLocal(); self.company=Company(name=f"Equipment {uuid.uuid4()}"); self.db.add(self.company); self.db.flush(); self.user=User(company_id=self.company.id,name="Tech",email=f"tech-{uuid.uuid4()}@example.test",password_hash="unused"); self.customer=Customer(company_id=self.company.id,name="Client"); self.db.add_all([self.user,self.customer]); self.db.commit(); self.router=build_router(lambda:None,lambda _:lambda:self.user,lambda *args,**kwargs:None)
    def tearDown(self): self.db.rollback(); self.db.close()
    def endpoint(self,path,method): return next(x.endpoint for x in self.router.routes if x.path==path and method in x.methods)
    def test_catalog_asset_duplicate_and_accessory(self):
        category=self.endpoint("/api/v1/equipment/categories","POST")(CatalogPayload(name="Notebook"),self.user,self.db); brand=self.endpoint("/api/v1/equipment/brands","POST")(CatalogPayload(name="Marca"),self.user,self.db); self.db.commit()
        create=self.endpoint("/api/v1/equipment","POST"); payload=EquipmentPayload(customer_id=self.customer.id,category="Notebook",category_id=category["id"],brand_id=brand["id"],serial_number="SER-1")
        item=create(payload,self.user,self.db); self.assertEqual(item["status"],"active")
        with self.assertRaises(Exception): create(payload,self.user,self.db)
        accessory=self.endpoint("/api/v1/equipment/{equipment_id}/accessories","POST")(item["id"],AccessoryPayload(description="Fonte"),self.user,self.db); self.assertEqual(accessory["quantity"],1)
        detail=self.endpoint("/api/v1/equipment/{equipment_id}","GET")(item["id"],self.user,self.db); self.assertEqual(len(detail["accessories"]),1)

if __name__=="__main__": unittest.main()

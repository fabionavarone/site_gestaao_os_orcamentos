import os
from http.cookies import SimpleCookie
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY","test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL","sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL","redis://localhost:6379/0")

from fastapi import HTTPException,Response
from starlette.requests import Request
from provisao_api.db import Base,SessionLocal,engine
from provisao_api.main import COOKIE,CustomerIn,EquipmentIn,Login,create_customer,create_equipment,current_user,login,logout,pwd
from provisao_api.models import Company,Customer,Session,User


def request(method="GET",cookie="",csrf=""):
    headers=[]
    if cookie:headers.append((b"cookie",f"{COOKIE}={cookie}".encode()))
    if csrf:headers.append((b"x-csrf-token",csrf.encode()))
    return Request({"type":"http","method":method,"path":"/","headers":headers})


class SecurityApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Base.metadata.create_all(engine)
    def setUp(self):
        self.db=SessionLocal();company=Company(name=f"Security {uuid.uuid4()}");self.db.add(company);self.db.flush();self.user=User(company_id=company.id,name="Operador",email=f"operator-{uuid.uuid4()}@example.com",password_hash=pwd.hash("a-strong-test-password"));self.db.add(self.user);self.db.commit()
    def tearDown(self):self.db.rollback();self.db.close()
    def authenticate(self):
        response=Response();body=login(Login(email=self.user.email,password="a-strong-test-password"),response,self.db);cookie=SimpleCookie();cookie.load(response.headers["set-cookie"]);return body["csrf_token"],cookie[COOKIE].value

    def test_login_csrf_expiration_and_revocation(self):
        with self.assertRaises(HTTPException) as invalid:login(Login(email=self.user.email,password="wrong-password-value"),Response(),self.db)
        self.assertEqual(invalid.exception.status_code,401)
        csrf,raw=self.authenticate();self.assertEqual(current_user(request(cookie=raw),self.db).id,self.user.id)
        with self.assertRaises(HTTPException) as denied:current_user(request("POST",raw,"wrong"),self.db)
        self.assertEqual(denied.exception.status_code,403)
        logout_response=Response();logout(request("POST",raw,csrf),logout_response,self.user,self.db)
        with self.assertRaises(HTTPException):current_user(request(cookie=raw),self.db)

    def test_customer_tenant_scope_and_equipment(self):
        customer=create_customer(CustomerIn(name="Cliente A"),self.user,self.db)["id"]
        result=create_equipment(EquipmentIn(customer_id=customer,category="Inversor"),self.user,self.db);self.assertIn("id",result)
        other_company=Company(name=f"Other {uuid.uuid4()}");self.db.add(other_company);self.db.flush();other=Customer(company_id=other_company.id,name="Outro");self.db.add(other);self.db.commit()
        with self.assertRaises(HTTPException) as denied:create_equipment(EquipmentIn(customer_id=other.id,category="Inversor"),self.user,self.db)
        self.assertEqual(denied.exception.status_code,404)


if __name__=="__main__":unittest.main()

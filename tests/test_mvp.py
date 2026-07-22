import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from app import server


class ProvisaoManagerApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(cls.temp.name)
        server.DB_PATH = server.DATA_DIR / "test.db"
        server.migrate()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def request(self, method, path, body=None, cookie=None):
        handler = object.__new__(server.Handler)
        raw = json.dumps(body).encode() if body is not None else b""
        handler.path = path
        handler.headers = {"Content-Length": str(len(raw)), "Cookie": cookie or ""}
        handler.rfile = BytesIO(raw)
        handler.wfile = BytesIO()
        captured = {"headers": {}}
        handler.send_response = lambda status: captured.update(status=status)
        handler.send_header = lambda key, value: captured["headers"].update({key: value})
        handler.end_headers = lambda: None
        if method == "GET":
            parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(path)
            handler.api_get(parsed.path, {})
        else:
            handler.api_post(path)
        return captured["status"], json.loads(handler.wfile.getvalue()), captured["headers"].get("Set-Cookie")

    def login(self):
        status, data, cookie = self.request("POST", "/api/v1/auth/login", {"email": "admin@provisao.local", "password": "provisao123"})
        self.assertEqual(status, 200)
        self.assertEqual(data["user"]["role"], "admin")
        return cookie.split(";", 1)[0]

    def test_health_is_public(self):
        status, payload, _ = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_operational_flow_and_transition_guards(self):
        cookie = self.login()
        status, customer, _ = self.request("POST", "/api/v1/customers", {"name": "Cliente Teste", "email": "cliente@example.test"}, cookie)
        self.assertEqual(status, 201)
        status, equipment, _ = self.request("POST", "/api/v1/equipment", {"customer_id": customer["item"]["id"], "category": "Inversor", "manufacturer": "Deye", "model": "SUN-5K"}, cookie)
        self.assertEqual(status, 201)
        status, order, _ = self.request("POST", "/api/v1/service-orders", {"customer_id": customer["item"]["id"], "equipment_id": equipment["item"]["id"], "title": "Nao liga", "symptom": "Sem sinal", "priority": "alta"}, cookie)
        self.assertEqual(status, 201)
        order_id = order["item"]["id"]
        status, error, _ = self.request("POST", f"/api/v1/service-orders/{order_id}/transition", {"status": "repair_in_progress"}, cookie)
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "SERVICE_ORDER_INVALID_TRANSITION")
        status, _, _ = self.request("POST", f"/api/v1/service-orders/{order_id}/transition", {"status": "awaiting_receipt"}, cookie)
        self.assertEqual(status, 200)
        status, detail, _ = self.request("GET", f"/api/v1/service-orders/{order_id}", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(detail["item"]["status"], "awaiting_receipt")

    def test_telegram_ingestion_is_idempotent(self):
        cookie = self.login()
        update = {"subject": "5511999999999", "text": "Meu equipamento nao liga", "sender": "Cliente", "external_message_id": "update-1"}
        status, first, _ = self.request("POST", "/api/v1/telegram/updates", update, cookie)
        self.assertEqual(status, 200)
        status, second, _ = self.request("POST", "/api/v1/telegram/updates", update, cookie)
        self.assertEqual(status, 200)
        self.assertTrue(second["duplicate"])
        status, conversation, _ = self.request("GET", f"/api/v1/conversations/{first['conversation_id']}", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(len(conversation["messages"]), 1)


if __name__ == "__main__":
    unittest.main()

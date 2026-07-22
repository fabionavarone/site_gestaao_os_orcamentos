"""Provisao Manager MVP.

Single-process standard-library implementation intended for local operation and
for exercising the operational domain before production services are split out.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "app" / "static"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "provisao_manager.db"
SESSION_COOKIE = "provisao_session"

SERVICE_ORDER_STATES = {
    "draft": ["awaiting_receipt", "received", "cancelled"],
    "awaiting_receipt": ["received", "cancelled"],
    "received": ["triage", "cancelled"],
    "triage": ["diagnosis", "technical_hold", "customer_hold", "cancelled"],
    "diagnosis": ["awaiting_budget", "technical_hold", "no_repair_condition"],
    "awaiting_budget": ["awaiting_customer_approval", "technical_hold"],
    "awaiting_customer_approval": ["approved", "rejected", "customer_hold"],
    "approved": ["awaiting_parts", "repair_in_progress", "financial_hold"],
    "rejected": ["ready_for_delivery", "closed", "cancelled"],
    "awaiting_parts": ["repair_in_progress", "technical_hold"],
    "repair_in_progress": ["quality_test", "technical_hold"],
    "quality_test": ["ready_for_delivery", "repair_in_progress", "technical_hold"],
    "technical_hold": ["triage", "diagnosis", "repair_in_progress", "cancelled"],
    "customer_hold": ["triage", "awaiting_customer_approval", "cancelled"],
    "financial_hold": ["approved", "ready_for_delivery", "cancelled"],
    "ready_for_delivery": ["delivered", "financial_hold"],
    "delivered": ["closed", "warranty_return"],
    "closed": ["warranty_return"],
    "warranty_return": ["triage", "diagnosis"],
    "no_repair_condition": ["ready_for_delivery", "closed"],
    "cancelled": [],
}

ROLES = {"admin", "attendant", "technician", "viewer"}
WRITE_ROLES = {"admin", "attendant", "technician"}
ADMIN_ROLES = {"admin"}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
    return f"{salt}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    salt, _ = encoded.split("$", 1)
    return secrets.compare_digest(password_hash(password, salt), encoded)


def connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def migrate() -> None:
    db = connection()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, document TEXT, email TEXT, phone TEXT,
          kind TEXT NOT NULL DEFAULT 'person', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS equipment (
          id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), category TEXT NOT NULL,
          manufacturer TEXT, model TEXT, serial_number TEXT, internal_code TEXT NOT NULL UNIQUE,
          notes TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS service_orders (
          id TEXT PRIMARY KEY, number INTEGER NOT NULL UNIQUE, customer_id TEXT NOT NULL REFERENCES customers(id),
          equipment_id TEXT REFERENCES equipment(id), title TEXT NOT NULL, symptom TEXT, priority TEXT NOT NULL,
          status TEXT NOT NULL, assigned_to TEXT REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS service_order_events (
          id TEXT PRIMARY KEY, service_order_id TEXT NOT NULL REFERENCES service_orders(id), actor_id TEXT REFERENCES users(id),
          event_type TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY, channel TEXT NOT NULL, subject TEXT NOT NULL, customer_id TEXT REFERENCES customers(id),
          status TEXT NOT NULL DEFAULT 'human_queue', assigned_to TEXT REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), direction TEXT NOT NULL,
          author_name TEXT NOT NULL, body TEXT NOT NULL, internal INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
          id TEXT PRIMARY KEY, actor_id TEXT REFERENCES users(id), action TEXT NOT NULL, entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """
    )
    if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        db.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, 1, ?)",
            (str(uuid.uuid4()), "Administrador", "admin@provisao.local", password_hash("provisao123"), "admin", now()),
        )
    db.commit()
    db.close()


def row(item: sqlite3.Row | None) -> dict | None:
    return dict(item) if item else None


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.api_get(parsed.path, parse_qs(parsed.query))
        else:
            self.serve_static(parsed.path)

    def do_POST(self) -> None:
        self.api_post(urlparse(self.path).path)

    def serve_static(self, path: str) -> None:
        target = STATIC_DIR / ("index.html" if path in {"/", ""} else path.lstrip("/"))
        try:
            target.resolve().relative_to(STATIC_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            target = STATIC_DIR / "index.html"
        mime = "text/html; charset=utf-8"
        if target.suffix == ".js": mime = "application/javascript; charset=utf-8"
        if target.suffix == ".css": mime = "text/css; charset=utf-8"
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.fail(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "JSON invalido.")
            raise ValueError

    def respond(self, value: object, status: HTTPStatus = HTTPStatus.OK, cookie: str | None = None) -> None:
        data = json.dumps(value, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def fail(self, status: HTTPStatus, code: str, message: str) -> None:
        self.respond({"error": {"code": code, "message": message}}, status)

    def user(self) -> dict | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        if not token: return None
        db = connection()
        result = db.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>? AND u.active=1",
            (token.value, now()),
        ).fetchone()
        db.close()
        return row(result)

    def require(self, roles: set[str] | None = None) -> dict | None:
        user = self.user()
        if not user:
            self.fail(HTTPStatus.UNAUTHORIZED, "AUTH_REQUIRED", "Autenticacao necessaria.")
            return None
        if roles and user["role"] not in roles:
            self.audit(user, "access_denied", "route", self.path, "Permissao insuficiente")
            self.fail(HTTPStatus.FORBIDDEN, "ACCESS_DENIED", "Permissao insuficiente.")
            return None
        return user

    def audit(self, user: dict | None, action: str, entity_type: str, entity_id: str, detail: str) -> None:
        db = connection()
        db.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), user["id"] if user else None, action, entity_type, entity_id, detail, now()))
        db.commit(); db.close()

    def api_get(self, path: str, query: dict) -> None:
        if path == "/api/v1/health":
            self.respond({"status": "ok", "database": "ok", "ai": "disabled"}); return
        user = self.require()
        if not user: return
        db = connection()
        try:
            if path == "/api/v1/me": self.respond({"user": public_user(user)}); return
            if path == "/api/v1/dashboard":
                counts = {s: db.execute("SELECT count(*) FROM service_orders WHERE status=?", (s,)).fetchone()[0] for s in ["draft", "triage", "diagnosis", "awaiting_customer_approval", "repair_in_progress", "ready_for_delivery"]}
                self.respond({"orders_by_status": counts, "customers": db.execute("SELECT count(*) FROM customers").fetchone()[0], "conversations": db.execute("SELECT count(*) FROM conversations WHERE status != 'completed'").fetchone()[0]}); return
            if path == "/api/v1/customers":
                self.respond({"items": [row(x) for x in db.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall()]}); return
            if path == "/api/v1/equipment":
                self.respond({"items": [row(x) for x in db.execute("SELECT e.*, c.name customer_name FROM equipment e JOIN customers c ON c.id=e.customer_id ORDER BY e.created_at DESC").fetchall()]}); return
            if path == "/api/v1/service-orders":
                status = query.get("status", [None])[0]
                sql = "SELECT o.*, c.name customer_name, e.manufacturer, e.model, u.name assigned_name FROM service_orders o JOIN customers c ON c.id=o.customer_id LEFT JOIN equipment e ON e.id=o.equipment_id LEFT JOIN users u ON u.id=o.assigned_to"
                params = ()
                if status: sql += " WHERE o.status=?"; params = (status,)
                self.respond({"items": [row(x) for x in db.execute(sql + " ORDER BY o.updated_at DESC", params).fetchall()], "states": SERVICE_ORDER_STATES}); return
            if path.startswith("/api/v1/service-orders/"):
                order_id = path.rsplit("/", 1)[-1]
                order = db.execute("SELECT o.*, c.name customer_name, e.internal_code, e.manufacturer, e.model FROM service_orders o JOIN customers c ON c.id=o.customer_id LEFT JOIN equipment e ON e.id=o.equipment_id WHERE o.id=?", (order_id,)).fetchone()
                if not order: self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "OS nao encontrada."); return
                events = db.execute("SELECT ev.*, u.name actor_name FROM service_order_events ev LEFT JOIN users u ON u.id=ev.actor_id WHERE service_order_id=? ORDER BY created_at DESC", (order_id,)).fetchall()
                self.respond({"item": row(order), "events": [row(x) for x in events], "allowed_transitions": SERVICE_ORDER_STATES[row(order)["status"]]}); return
            if path == "/api/v1/conversations":
                self.respond({"items": [row(x) for x in db.execute("SELECT c.*, cu.name customer_name, u.name assigned_name FROM conversations c LEFT JOIN customers cu ON cu.id=c.customer_id LEFT JOIN users u ON u.id=c.assigned_to ORDER BY c.updated_at DESC").fetchall()]}); return
            if path.startswith("/api/v1/conversations/"):
                conversation_id = path.rsplit("/", 1)[-1]
                convo = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
                if not convo: self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Conversa nao encontrada."); return
                self.respond({"item": row(convo), "messages": [row(x) for x in db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation_id,)).fetchall()]}); return
            if path == "/api/v1/users":
                if user["role"] not in ADMIN_ROLES: self.fail(HTTPStatus.FORBIDDEN, "ACCESS_DENIED", "Permissao insuficiente."); return
                self.respond({"items": [public_user(row(x)) for x in db.execute("SELECT * FROM users ORDER BY name").fetchall()]}); return
            self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Rota nao encontrada.")
        finally: db.close()

    def api_post(self, path: str) -> None:
        try: data = self.payload()
        except ValueError: return
        if path == "/api/v1/auth/login":
            db = connection(); item = db.execute("SELECT * FROM users WHERE email=? AND active=1", (str(data.get("email", "")).lower(),)).fetchone(); db.close()
            if not item or not password_matches(str(data.get("password", "")), item["password_hash"]): self.fail(HTTPStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "Credenciais invalidas."); return
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(UTC) + timedelta(hours=8)).isoformat(timespec="seconds")
            db = connection(); db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token, item["id"], expires_at)); db.commit(); db.close()
            self.audit(row(item), "login", "session", token[:8], "Sessao iniciada")
            self.respond({"user": public_user(row(item))}, cookie=f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800"); return
        if path == "/api/v1/auth/logout":
            user = self.user(); cookie = SimpleCookie(self.headers.get("Cookie")); token = cookie.get(SESSION_COOKIE)
            if token:
                db = connection(); db.execute("DELETE FROM sessions WHERE token=?", (token.value,)); db.commit(); db.close()
            if user: self.audit(user, "logout", "session", "current", "Sessao encerrada")
            self.respond({"ok": True}, cookie=f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"); return
        user = self.require(WRITE_ROLES)
        if not user: return
        db = connection()
        try:
            if path == "/api/v1/customers":
                name = clean_required(data, "name")
                item = {"id": str(uuid.uuid4()), "name": name, "document": clean(data, "document"), "email": clean(data, "email"), "phone": clean(data, "phone"), "kind": data.get("kind", "person"), "created_at": now()}
                db.execute("INSERT INTO customers VALUES (:id,:name,:document,:email,:phone,:kind,:created_at)", item); db.commit(); self.audit(user, "create", "customer", item["id"], name); self.respond({"item": item}, HTTPStatus.CREATED); return
            if path == "/api/v1/equipment":
                customer_id = clean_required(data, "customer_id")
                if not db.execute("SELECT 1 FROM customers WHERE id=?", (customer_id,)).fetchone(): self.fail(HTTPStatus.UNPROCESSABLE_ENTITY, "CUSTOMER_NOT_FOUND", "Cliente nao encontrado."); return
                item = {"id": str(uuid.uuid4()), "customer_id": customer_id, "category": clean_required(data, "category"), "manufacturer": clean(data, "manufacturer"), "model": clean(data, "model"), "serial_number": clean(data, "serial_number"), "internal_code": f"EQ-{uuid.uuid4().hex[:8].upper()}", "notes": clean(data, "notes"), "created_at": now()}
                db.execute("INSERT INTO equipment VALUES (:id,:customer_id,:category,:manufacturer,:model,:serial_number,:internal_code,:notes,:created_at)", item); db.commit(); self.audit(user, "create", "equipment", item["id"], item["internal_code"]); self.respond({"item": item}, HTTPStatus.CREATED); return
            if path == "/api/v1/service-orders":
                customer_id = clean_required(data, "customer_id")
                equipment_id = clean(data, "equipment_id")
                if not db.execute("SELECT 1 FROM customers WHERE id=?", (customer_id,)).fetchone(): self.fail(HTTPStatus.UNPROCESSABLE_ENTITY, "CUSTOMER_NOT_FOUND", "Cliente nao encontrado."); return
                if equipment_id and not db.execute("SELECT 1 FROM equipment WHERE id=? AND customer_id=?", (equipment_id, customer_id)).fetchone(): self.fail(HTTPStatus.UNPROCESSABLE_ENTITY, "EQUIPMENT_NOT_FOUND", "Equipamento nao pertence ao cliente."); return
                number = db.execute("SELECT coalesce(max(number), 0) + 1 FROM service_orders").fetchone()[0]
                item = {"id": str(uuid.uuid4()), "number": number, "customer_id": customer_id, "equipment_id": equipment_id, "title": clean_required(data, "title"), "symptom": clean(data, "symptom"), "priority": data.get("priority", "normal"), "status": "draft", "assigned_to": user["id"], "created_at": now(), "updated_at": now()}
                db.execute("INSERT INTO service_orders VALUES (:id,:number,:customer_id,:equipment_id,:title,:symptom,:priority,:status,:assigned_to,:created_at,:updated_at)", item); self.order_event(db, item["id"], user["id"], "created", "OS criada como rascunho"); db.commit(); self.audit(user, "create", "service_order", item["id"], f"OS #{number}"); self.respond({"item": item}, HTTPStatus.CREATED); return
            if path.startswith("/api/v1/service-orders/") and path.endswith("/transition"):
                order_id = path.split("/")[-2]; target = clean_required(data, "status"); reason = clean(data, "reason")
                order = db.execute("SELECT * FROM service_orders WHERE id=?", (order_id,)).fetchone()
                if not order: self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "OS nao encontrada."); return
                if target not in SERVICE_ORDER_STATES[order["status"]]: self.fail(HTTPStatus.CONFLICT, "SERVICE_ORDER_INVALID_TRANSITION", "Transicao de estado nao permitida."); return
                if target in {"closed", "cancelled", "technical_hold", "customer_hold", "financial_hold"} and not reason: self.fail(HTTPStatus.UNPROCESSABLE_ENTITY, "JUSTIFICATION_REQUIRED", "Justificativa obrigatoria para este estado."); return
                db.execute("UPDATE service_orders SET status=?, updated_at=? WHERE id=?", (target, now(), order_id)); self.order_event(db, order_id, user["id"], "status_changed", f"{order['status']} -> {target}. {reason}".strip()); db.commit(); self.audit(user, "transition", "service_order", order_id, f"{order['status']} -> {target}"); self.respond({"ok": True}); return
            if path == "/api/v1/conversations":
                item = {"id": str(uuid.uuid4()), "channel": data.get("channel", "web"), "subject": clean_required(data, "subject"), "customer_id": clean(data, "customer_id"), "status": "human_queue", "assigned_to": user["id"], "created_at": now(), "updated_at": now()}
                db.execute("INSERT INTO conversations VALUES (:id,:channel,:subject,:customer_id,:status,:assigned_to,:created_at,:updated_at)", item); db.commit(); self.audit(user, "create", "conversation", item["id"], item["subject"]); self.respond({"item": item}, HTTPStatus.CREATED); return
            if path.startswith("/api/v1/conversations/") and path.endswith("/messages"):
                conversation_id = path.split("/")[-2]
                if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone(): self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Conversa nao encontrada."); return
                body = clean_required(data, "body"); internal = bool(data.get("internal", False)); message = {"id": str(uuid.uuid4()), "conversation_id": conversation_id, "direction": "internal" if internal else "outbound", "author_name": user["name"], "body": body, "internal": int(internal), "created_at": now()}
                db.execute("INSERT INTO messages VALUES (:id,:conversation_id,:direction,:author_name,:body,:internal,:created_at)", message); db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), conversation_id)); db.commit(); self.audit(user, "message", "conversation", conversation_id, "Nota interna" if internal else "Mensagem enviada"); self.respond({"item": message}, HTTPStatus.CREATED); return
            if path == "/api/v1/telegram/updates":
                # Gateway integration point: accepts a sanitized canonical update. No direct Telegram token or DB access outside this API.
                subject = clean_required(data, "subject"); body = clean_required(data, "text"); external_id = clean(data, "external_message_id") or str(uuid.uuid4())
                existing = db.execute("SELECT id FROM messages WHERE id=?", (f"tg-{external_id}",)).fetchone()
                if existing: self.respond({"ok": True, "duplicate": True}); return
                convo = db.execute("SELECT * FROM conversations WHERE channel='telegram' AND subject=? ORDER BY created_at DESC LIMIT 1", (subject,)).fetchone()
                if not convo:
                    convo_id = str(uuid.uuid4()); db.execute("INSERT INTO conversations VALUES (?, 'telegram', ?, NULL, 'human_queue', NULL, ?, ?)", (convo_id, subject, now(), now()))
                else: convo_id = convo["id"]
                db.execute("INSERT INTO messages VALUES (?, ?, 'inbound', ?, ?, 0, ?)", (f"tg-{external_id}", convo_id, clean(data, "sender") or "Telegram", body, now())); db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), convo_id)); db.commit(); self.audit(user, "ingest", "conversation", convo_id, "Telegram canonical update"); self.respond({"ok": True, "conversation_id": convo_id}); return
            self.fail(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Rota nao encontrada.")
        except ValueError as exc:
            self.fail(HTTPStatus.UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc))
        finally: db.close()

    @staticmethod
    def order_event(db: sqlite3.Connection, order_id: str, actor_id: str, event_type: str, detail: str) -> None:
        db.execute("INSERT INTO service_order_events VALUES (?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), order_id, actor_id, event_type, detail, now()))


def clean(data: dict, key: str) -> str | None:
    value = data.get(key)
    return str(value).strip() if value is not None and str(value).strip() else None


def clean_required(data: dict, key: str) -> str:
    value = clean(data, key)
    if not value: raise ValueError(f"Campo obrigatorio: {key}.")
    return value


def public_user(user: dict) -> dict:
    return {key: user[key] for key in ("id", "name", "email", "role", "active", "created_at")}


def main() -> None:
    migrate()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Provisao Manager disponivel em http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__": main()

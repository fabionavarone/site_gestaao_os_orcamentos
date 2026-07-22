#!/usr/bin/env python3
"""Importa uma base legada SQLite para o schema Alembic, de forma idempotente.

As senhas legadas usam um formato incompatível com Argon2; por segurança os
usuários importados ficam inativos até a redefinição administrativa da senha.
"""
import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from provisao_api.db import SessionLocal
from provisao_api.models import (AuditLog, Company, Conversation,
    ConversationMessage, Customer, Equipment, Role, ServiceOrder,
    ServiceOrderEvent, User, UserRole)

def date(value):
    if not value: return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)

def rows(source, table):
    present = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return source.execute(f"SELECT * FROM {table}").fetchall() if present else []

def import_database(source_path: Path, company_name: str, dry_run: bool = False) -> dict[str, int]:
    source = sqlite3.connect(source_path); source.row_factory = sqlite3.Row
    target = SessionLocal(); report = {name: 0 for name in ("users", "customers", "equipment", "service_orders", "events", "conversations", "messages", "audit_logs")}
    try:
        company = target.scalar(select(Company).where(Company.name == company_name))
        if not company:
            company = Company(name=company_name); target.add(company); target.flush()
        role_by_code = {}
        for legacy in rows(source, "users"):
            code = legacy["role"] or "operator"
            role = target.scalar(select(Role).where(Role.company_id == company.id, Role.code == code))
            if not role:
                role = Role(company_id=company.id, code=code, name=code.replace("_", " ").title(), permissions={"legacy_role": code})
                target.add(role); target.flush()
            role_by_code[code] = role
            if not target.get(User, legacy["id"]):
                target.add(User(id=legacy["id"], company_id=company.id, name=legacy["name"], email=legacy["email"].lower(), password_hash="!legacy-password-reset-required", active=False, created_at=date(legacy["created_at"])))
                target.flush(); target.add(UserRole(user_id=legacy["id"], role_id=role.id)); report["users"] += 1
        for legacy in rows(source, "customers"):
            if not target.get(Customer, legacy["id"]):
                target.add(Customer(id=legacy["id"], company_id=company.id, name=legacy["name"], document=legacy["document"], email=legacy["email"], phone=legacy["phone"], created_at=date(legacy["created_at"]))); report["customers"] += 1
        target.flush()
        for legacy in rows(source, "equipment"):
            if not target.get(Equipment, legacy["id"]):
                target.add(Equipment(id=legacy["id"], company_id=company.id, customer_id=legacy["customer_id"], category=legacy["category"], manufacturer=legacy["manufacturer"], model=legacy["model"], serial_number=legacy["serial_number"], internal_code=legacy["internal_code"], created_at=date(legacy["created_at"]))); report["equipment"] += 1
        for legacy in rows(source, "service_orders"):
            if not target.get(ServiceOrder, legacy["id"]):
                target.add(ServiceOrder(id=legacy["id"], company_id=company.id, number=legacy["number"], customer_id=legacy["customer_id"], equipment_id=legacy["equipment_id"], title=legacy["title"], symptom=legacy["symptom"], priority=legacy["priority"], status=legacy["status"], version=1, created_at=date(legacy["created_at"]), updated_at=date(legacy["updated_at"]))); report["service_orders"] += 1
        target.flush()
        for legacy in rows(source, "service_order_events"):
            if not target.get(ServiceOrderEvent, legacy["id"]):
                target.add(ServiceOrderEvent(id=legacy["id"], service_order_id=legacy["service_order_id"], actor_id=legacy["actor_id"], event_type=legacy["event_type"], detail=legacy["detail"], created_at=date(legacy["created_at"]))); report["events"] += 1
        for legacy in rows(source, "conversations"):
            if not target.get(Conversation, legacy["id"]):
                target.add(Conversation(id=legacy["id"], company_id=company.id, channel=legacy["channel"], subject=legacy["subject"], customer_id=legacy["customer_id"], status=legacy["status"], assigned_to=legacy["assigned_to"], automation_paused=False, created_at=date(legacy["created_at"]), updated_at=date(legacy["updated_at"]))); report["conversations"] += 1
        target.flush()
        for legacy in rows(source, "messages"):
            if not target.get(ConversationMessage, legacy["id"]):
                target.add(ConversationMessage(id=legacy["id"], conversation_id=legacy["conversation_id"], direction=legacy["direction"], author_name=legacy["author_name"], body=legacy["body"], internal=bool(legacy["internal"]), message_type="text", created_at=date(legacy["created_at"]))); report["messages"] += 1
        for legacy in rows(source, "audit_logs"):
            if not target.get(AuditLog, legacy["id"]):
                target.add(AuditLog(id=legacy["id"], company_id=company.id, actor_id=legacy["actor_id"], action=legacy["action"], entity_type=legacy["entity_type"], entity_id=legacy["entity_id"], detail={"legacy_detail": legacy["detail"]}, created_at=date(legacy["created_at"]))); report["audit_logs"] += 1
        if dry_run: target.rollback()
        else: target.commit()
        return report
    except Exception:
        target.rollback(); raise
    finally:
        target.close(); source.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("source", type=Path); parser.add_argument("--company", required=True); parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    if not arguments.source.is_file(): parser.error("source must be a SQLite file")
    print(import_database(arguments.source, arguments.company, arguments.dry_run))

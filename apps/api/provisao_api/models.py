import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid() -> str: return str(uuid.uuid4())

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("company_id", "code"),)

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    document: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    category: Mapped[str] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    internal_code: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ServiceOrderEvent(Base):
    __tablename__ = "service_order_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    service_order_id: Mapped[str] = mapped_column(ForeignKey("service_orders.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    subject: Mapped[str] = mapped_column(String(240))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="human_queue", index=True)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    automation_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    author_name: Mapped[str] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(20), default="text")
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    external_message_id: Mapped[str | None] = mapped_column(String(160))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("conversation_id", "external_message_id"),)

class ServiceOrder(Base):
    __tablename__ = "service_orders"
    __table_args__ = (UniqueConstraint("company_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    title: Mapped[str] = mapped_column(String(240))
    symptom: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
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

class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("company_id", "name"),)

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("company_id", "name"),)

class TeamMember(Base):
    __tablename__ = "team_members"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

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
    customer_type: Mapped[str] = mapped_column(String(16), default="individual", index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200))
    state_registration: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str | None] = mapped_column(String(80))
    normalized_document: Mapped[str | None] = mapped_column(String(20), index=True)
    normalized_email: Mapped[str | None] = mapped_column(String(320), index=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("company_id", "normalized_document"), CheckConstraint("customer_type IN ('individual','company')", name="customer_type"), CheckConstraint("status IN ('active','inactive','blocked')", name="customer_status"))

class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    job_title: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    preferred_channel: Mapped[str] = mapped_column(String(20), default="telegram")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    receives_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    normalized_email: Mapped[str | None] = mapped_column(String(320), index=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CustomerAddress(Base):
    __tablename__ = "customer_addresses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    address_type: Mapped[str] = mapped_column(String(20), default="service")
    postal_code: Mapped[str | None] = mapped_column(String(12))
    street: Mapped[str] = mapped_column(String(200))
    number: Mapped[str | None] = mapped_column(String(30))
    complement: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2))
    country: Mapped[str] = mapped_column(String(2), default="BR")
    reference: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[str | None] = mapped_column(String(32))
    longitude: Mapped[str | None] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CustomerMergeRequest(Base):
    __tablename__ = "customer_merge_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    source_customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    target_customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channels.id"), index=True)
    bot_id: Mapped[str | None] = mapped_column(ForeignKey("channel_bots.id"), index=True)
    external_identity_id: Mapped[str | None] = mapped_column(ForeignKey("external_identities.id"), index=True)
    subject: Mapped[str] = mapped_column(String(240))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    service_order_id: Mapped[str | None] = mapped_column(ForeignKey("service_orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    automation_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("company_id", "kind", "name"), CheckConstraint("kind IN ('web','telegram')", name="channel_kind"))

class ChannelBot(Base):
    __tablename__ = "channel_bots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    public_id: Mapped[str] = mapped_column(String(36), unique=True, default=uid, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    telegram_bot_id: Mapped[str | None] = mapped_column(String(32), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    token_fingerprint: Mapped[str | None] = mapped_column(String(16))
    webhook_secret_ciphertext: Mapped[str | None] = mapped_column(Text)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), default="disabled")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    polling_offset: Mapped[int] = mapped_column(Integer, default=0)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("company_id", "name"),
        CheckConstraint("mode IN ('webhook','polling','disabled')", name="telegram_bot_mode"),
        CheckConstraint("status IN ('draft','validating','active','inactive','error')", name="telegram_bot_status"),
    )

class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    bot_id: Mapped[str | None] = mapped_column(ForeignKey("channel_bots.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    external_chat_id: Mapped[str | None] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="telegram")
    username: Mapped[str | None] = mapped_column(String(160))
    display_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("channel_id", "bot_id", "external_id", "external_chat_id"),)

class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    external_identity_id: Mapped[str] = mapped_column(ForeignKey("external_identities.id"), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(32), default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channels.id"), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    author_name: Mapped[str] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(20), default="text")
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    external_message_id: Mapped[str | None] = mapped_column(String(160))
    provider_update_id: Mapped[str | None] = mapped_column(String(160), index=True)
    sender_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    sender_external_identity_id: Mapped[str | None] = mapped_column(ForeignKey("external_identities.id"))
    reply_to_message_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_messages.id"))
    normalized_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("conversation_id", "external_message_id"),)

class ExternalEvent(Base):
    __tablename__ = "external_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    bot_id: Mapped[str | None] = mapped_column(ForeignKey("channel_bots.id"), index=True)
    external_event_id: Mapped[str] = mapped_column(String(160))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("channel_id", "external_event_id"),)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    bot_id: Mapped[str | None] = mapped_column(ForeignKey("channel_bots.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_messages.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="send_message")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("conversation_messages.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    service_order_id: Mapped[str | None] = mapped_column(ForeignKey("service_orders.id"), index=True)
    storage_provider: Mapped[str] = mapped_column(String(20), default="local")
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    safe_filename: Mapped[str] = mapped_column(String(255))
    declared_mime_type: Mapped[str | None] = mapped_column(String(160))
    detected_mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    workflow_instance_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_instances.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ServiceOrderSequence(Base):
    __tablename__ = "service_order_sequences"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1)
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

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(80), default="service_order")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("company_id", "code"), CheckConstraint("status IN ('draft','active','inactive','archived')", name="workflow_definition_status"))

class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_definition_id: Mapped[str] = mapped_column(ForeignKey("workflow_definitions.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("workflow_definition_id", "version_number"), CheckConstraint("status IN ('draft','published','superseded','archived')", name="workflow_version_status"))

class WorkflowState(Base):
    __tablename__ = "workflow_states"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30))
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    __table_args__ = (UniqueConstraint("workflow_version_id", "code"),)

class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    from_state_id: Mapped[str] = mapped_column(ForeignKey("workflow_states.id"), index=True)
    to_state_id: Mapped[str] = mapped_column(ForeignKey("workflow_states.id"), index=True)
    required_permission: Mapped[str | None] = mapped_column(String(100))
    requires_reason: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_assignment: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_checklist_completion: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_diagnosis: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_customer_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("workflow_version_id", "code"), CheckConstraint("from_state_id <> to_state_id", name="workflow_transition_distinct_states"))

class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    workflow_version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    current_state_id: Mapped[str] = mapped_column(ForeignKey("workflow_states.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    __table_args__ = (UniqueConstraint("company_id", "entity_type", "entity_id"), CheckConstraint("status IN ('running','paused','completed','cancelled')", name="workflow_instance_status"))

class WorkflowExecutionEvent(Base):
    __tablename__ = "workflow_execution_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_instance_id: Mapped[str] = mapped_column(ForeignKey("workflow_instances.id", ondelete="CASCADE"), index=True)
    transition_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_transitions.id"), index=True)
    from_state_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_states.id"))
    to_state_id: Mapped[str] = mapped_column(ForeignKey("workflow_states.id"))
    performed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class WorkflowActionExecution(Base):
    __tablename__ = "workflow_action_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_execution_event_id: Mapped[str] = mapped_column(ForeignKey("workflow_execution_events.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Canonical conversation application service shared by Web and channel gateways."""
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models import Channel, Conversation, ConversationMessage, ExternalEvent, ExternalIdentity, OutboxEvent


def utcnow() -> datetime:
    return datetime.now(UTC)


def ingest_external_event(session: Session, *, company_id: str, channel: Channel, bot_id: str | None,
                          external_event_id: str, idempotency_key: str, external_sender_id: str,
                          sender_name: str | None, external_chat_id: str, message_type: str,
                          text: str | None, metadata: dict | None = None) -> tuple[ConversationMessage, bool]:
    """Persist a channel envelope exactly once and resolve its inbox conversation.

    The adapter supplies only transport facts.  Routing and persistence are deliberately
    centralized here so Telegram and Web cannot diverge in business behavior.
    """
    prior = session.scalar(select(ExternalEvent).where(ExternalEvent.idempotency_key == idempotency_key))
    if prior:
        message = session.scalar(select(ConversationMessage).where(ConversationMessage.external_message_id == external_event_id))
        return message, False
    identity = session.scalar(select(ExternalIdentity).where(ExternalIdentity.channel_id == channel.id, ExternalIdentity.external_id == external_sender_id))
    if not identity:
        identity = ExternalIdentity(company_id=company_id, channel_id=channel.id, external_id=external_sender_id, display_name=sender_name)
        session.add(identity); session.flush()
    conversation = session.scalar(select(Conversation).where(Conversation.company_id == company_id, Conversation.channel == channel.kind, Conversation.subject == external_chat_id, Conversation.status != "closed"))
    if not conversation:
        conversation = Conversation(company_id=company_id, channel=channel.kind, subject=external_chat_id, customer_id=identity.customer_id, status="human_queue")
        session.add(conversation); session.flush()
    event = ExternalEvent(company_id=company_id, channel_id=channel.id, bot_id=bot_id, external_event_id=external_event_id, idempotency_key=idempotency_key, payload=metadata or {})
    message = ConversationMessage(conversation_id=conversation.id, direction="inbound", author_name=sender_name or external_sender_id, body=text, message_type=message_type, internal=False, external_message_id=external_event_id, metadata_json={"external_chat_id": external_chat_id, **(metadata or {})})
    session.add_all((event, message)); session.flush(); event.processed_at = utcnow()
    return message, True


def queue_outbound_message(session: Session, *, conversation: Conversation, channel: Channel,
                           author_name: str, body: str, idempotency_key: str, bot_id: str | None = None) -> tuple[ConversationMessage, OutboxEvent, bool]:
    existing = session.scalar(select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key))
    if existing:
        return session.get(ConversationMessage, existing.message_id), existing, False
    message = ConversationMessage(conversation_id=conversation.id, direction="outbound", author_name=author_name, body=body, internal=False)
    session.add(message); session.flush()
    outbox = OutboxEvent(company_id=conversation.company_id, channel_id=channel.id, bot_id=bot_id, conversation_id=conversation.id, message_id=message.id, payload={"text": body}, idempotency_key=idempotency_key)
    session.add(outbox)
    return message, outbox, True


def mark_outbox_failure(session: Session, event: OutboxEvent, error: str) -> None:
    event.attempts += 1; event.last_error = error[:2000]
    event.status = "dead_letter" if event.attempts >= 5 else "pending"
    if event.status == "pending":
        event.available_at = utcnow() + timedelta(seconds=min(300, 2 ** event.attempts))


def process_pending_outbox(session: Session, deliver, *, limit: int = 25) -> int:
    """Run a bounded delivery batch; failed items receive exponential backoff.

    `deliver` is supplied by the channel gateway, keeping external transports out
    of the domain transaction and making this routine deterministic in tests.
    """
    events = session.scalars(select(OutboxEvent).where(OutboxEvent.status == "pending", OutboxEvent.available_at <= utcnow()).order_by(OutboxEvent.created_at).limit(limit)).all()
    delivered = 0
    for event in events:
        event.status = "processing"; event.attempts += 1
        try:
            deliver(event)
        except Exception as exc:  # gateway errors are persisted, never discarded
            event.last_error = str(exc)[:2000]
            event.status = "dead_letter" if event.attempts >= 5 else "pending"
            if event.status == "pending": event.available_at = utcnow() + timedelta(seconds=min(300, 2 ** event.attempts))
        else:
            event.status = "delivered"; event.delivered_at = utcnow(); event.last_error = None; delivered += 1
    return delivered

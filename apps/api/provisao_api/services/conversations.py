"""Canonical conversation application service shared by Web and channel gateways."""
from datetime import UTC, datetime, timedelta
import random
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from ..models import AuditLog, Channel, Conversation, ConversationMessage, ConversationParticipant, ExternalEvent, ExternalIdentity, OutboxEvent


def utcnow() -> datetime:
    return datetime.now(UTC)


def ingest_external_event(session: Session, *, company_id: str, channel: Channel, bot_id: str | None,
                          external_event_id: str, idempotency_key: str, external_sender_id: str,
                          sender_name: str | None, external_chat_id: str, message_type: str,
                          text: str | None, metadata: dict | None = None,
                          external_message_id: str | None = None,
                          existing_event: ExternalEvent | None = None) -> tuple[ConversationMessage, bool]:
    """Persist a channel envelope exactly once and resolve its inbox conversation.

    The adapter supplies only transport facts.  Routing and persistence are deliberately
    centralized here so Telegram and Web cannot diverge in business behavior.
    """
    prior = existing_event or session.scalar(select(ExternalEvent).where(ExternalEvent.idempotency_key == idempotency_key))
    message_external_id = external_message_id or external_event_id
    if prior and prior.processed_at:
        message = session.scalar(select(ConversationMessage).where(ConversationMessage.provider_update_id == external_event_id, ConversationMessage.channel_id == channel.id))
        return message, False
    identity = session.scalar(select(ExternalIdentity).where(ExternalIdentity.channel_id == channel.id, ExternalIdentity.bot_id == bot_id, ExternalIdentity.external_id == external_sender_id, ExternalIdentity.external_chat_id == external_chat_id))
    if not identity:
        identity = ExternalIdentity(company_id=company_id, channel_id=channel.id, bot_id=bot_id, external_id=external_sender_id, external_chat_id=external_chat_id, display_name=sender_name)
        session.add(identity); session.flush()
    conversation = session.scalar(select(Conversation).where(Conversation.company_id == company_id, Conversation.bot_id == bot_id, Conversation.external_identity_id == identity.id, Conversation.status != "closed"))
    if not conversation:
        conversation = Conversation(company_id=company_id, channel=channel.kind, channel_id=channel.id, bot_id=bot_id, external_identity_id=identity.id, subject=external_chat_id, customer_id=identity.customer_id, status="queued")
        session.add(conversation); session.flush()
        session.add(ConversationParticipant(conversation_id=conversation.id, external_identity_id=identity.id, role="customer"))
    event = prior or ExternalEvent(company_id=company_id, channel_id=channel.id, bot_id=bot_id, external_event_id=external_event_id, idempotency_key=idempotency_key, payload=metadata or {})
    message = ConversationMessage(company_id=company_id, channel_id=channel.id, conversation_id=conversation.id, direction="inbound", author_name=sender_name or external_sender_id, body=text, normalized_text=text, message_type=message_type, status="received", internal=False, external_message_id=message_external_id, provider_update_id=external_event_id, sender_external_identity_id=identity.id, received_at=utcnow(), metadata_json={"external_chat_id": external_chat_id, **(metadata or {})})
    conversation.last_message_at=utcnow(); conversation.unread_count += 1
    event.status="processed"; event.attempts = (event.attempts or 0) + 1
    session.add_all((event, message)); session.flush(); event.processed_at = utcnow()
    return message, True


def queue_outbound_message(session: Session, *, conversation: Conversation, channel: Channel,
                           author_name: str, body: str, idempotency_key: str, bot_id: str | None = None) -> tuple[ConversationMessage, OutboxEvent, bool]:
    existing = session.scalar(select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key))
    if existing:
        return session.get(ConversationMessage, existing.message_id), existing, False
    message = ConversationMessage(company_id=conversation.company_id, channel_id=channel.id, conversation_id=conversation.id, direction="outbound", author_name=author_name, body=body, normalized_text=body, internal=False, status="pending")
    session.add(message); session.flush()
    outbox = OutboxEvent(company_id=conversation.company_id, channel_id=channel.id, bot_id=bot_id or conversation.bot_id, conversation_id=conversation.id, message_id=message.id, payload={"text": body,"external_chat_id":conversation.subject}, idempotency_key=idempotency_key)
    session.add(outbox)
    return message, outbox, True


def mark_outbox_failure(session: Session, event: OutboxEvent, error: str) -> None:
    event.attempts += 1; event.last_error = error[:2000]
    event.status = "dead_letter" if event.attempts >= 5 else "pending"
    if event.status == "pending":
        event.available_at = utcnow() + timedelta(seconds=min(300, 2 ** event.attempts))


def process_pending_outbox(session: Session, deliver, *, limit: int = 25, worker_id: str = "worker", lock_seconds: int = 60, max_attempts: int = 5) -> int:
    """Run a bounded delivery batch; failed items receive exponential backoff.

    `deliver` is supplied by the channel gateway, keeping external transports out
    of the domain transaction and making this routine deterministic in tests.
    """
    now=utcnow(); expired=now-timedelta(seconds=lock_seconds)
    candidates=session.scalars(select(OutboxEvent.id).where(OutboxEvent.status.in_(["pending","retry","processing"]),OutboxEvent.available_at<=now,or_(OutboxEvent.locked_at.is_(None),OutboxEvent.locked_at<expired)).order_by(OutboxEvent.created_at).limit(limit)).all()
    delivered = 0
    for event_id in candidates:
        claimed=session.execute(update(OutboxEvent).where(OutboxEvent.id==event_id,OutboxEvent.status.in_(["pending","retry","processing"]),or_(OutboxEvent.locked_at.is_(None),OutboxEvent.locked_at<expired)).values(status="processing",locked_at=now,locked_by=worker_id)).rowcount
        session.commit()
        if not claimed: continue
        event=session.get(OutboxEvent,event_id); event.attempts += 1; session.commit()
        try:
            deliver(event)
        except Exception as exc:
            event.last_error = str(exc)[:2000]
            permanent=getattr(exc,"permanent",False); retry_after=getattr(exc,"retry_after",None)
            event.status = "dead_letter" if permanent or event.attempts >= max_attempts else "retry"
            if event.status == "retry": event.available_at = utcnow() + timedelta(seconds=retry_after or min(300,(2 ** event.attempts)+random.uniform(0,1)))
            else: event.dead_lettered_at=utcnow()
            message=session.get(ConversationMessage,event.message_id)
            if message: message.status="failed" if permanent else event.status; message.failed_at=utcnow() if event.status=="dead_letter" else None
            session.add(AuditLog(company_id=event.company_id,actor_id=None,action="outbox_dead_letter" if event.status=="dead_letter" else "outbox_retry",entity_type="outbox_event",entity_id=event.id,detail={"attempts":event.attempts,"bot_id":event.bot_id}))
        else:
            event.status = "sent"; event.delivered_at = utcnow(); event.last_error = None; delivered += 1
            message=session.get(ConversationMessage,event.message_id)
            if message: message.status="sent"; message.sent_at=utcnow(); message.failed_at=None
            session.add(AuditLog(company_id=event.company_id,actor_id=None,action="outbox_sent",entity_type="outbox_event",entity_id=event.id,detail={"attempts":event.attempts,"bot_id":event.bot_id}))
        event.locked_at=None; event.locked_by=None; session.commit()
    return delivered

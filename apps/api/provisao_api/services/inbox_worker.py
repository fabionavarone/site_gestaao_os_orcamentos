"""Processing of persisted Telegram updates and their media."""
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import Settings
from ..models import Attachment, AuditLog, Channel, ChannelBot, ExternalEvent
from .conversations import ingest_external_event
from .crypto import CredentialCipher
from .storage import ALLOWED_MIME, LocalStorage
from .telegram import TelegramClient, normalize_update


TYPE_LIMIT = {"image":"max_image_bytes","voice":"max_audio_bytes","audio":"max_audio_bytes","document":"max_document_bytes","video":"max_video_bytes"}


def process_external_event(session: Session, event: ExternalEvent, cfg: Settings, *, transport=None) -> bool:
    bot=session.get(ChannelBot,event.bot_id); channel=session.get(Channel,event.channel_id)
    if not bot or not channel or not bot.token_ciphertext: raise RuntimeError("Telegram bot unavailable")
    envelope=normalize_update(event.payload,bot.id)
    if envelope is None:
        event.status="ignored"; event.processed_at=datetime.now(UTC); event.attempts += 1; return False
    cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys)
    client=TelegramClient(cipher.decrypt(bot.token_ciphertext),api_base=cfg.telegram_api_base_url,file_base=cfg.telegram_file_base_url,timeout=cfg.telegram_request_timeout_seconds,transport=transport)
    message,created=ingest_external_event(session,company_id=event.company_id,channel=channel,bot_id=bot.id,external_event_id=envelope.external_event_id,idempotency_key=event.idempotency_key,external_sender_id=envelope.external_user_id,sender_name=envelope.metadata.get("display_name"),external_chat_id=envelope.external_chat_id,message_type=envelope.message_type,text=envelope.text or envelope.caption,metadata=envelope.metadata,external_message_id=envelope.external_message_id,existing_event=event)
    if not created: return False
    storage=LocalStorage(cfg.storage_root); stored_keys=[]
    try:
        for item in envelope.attachments:
            limit=getattr(cfg,TYPE_LIMIT[item.type])
            if item.declared_size and item.declared_size > limit: raise ValueError("Telegram attachment exceeds configured limit")
            file_meta=client.get_file(item.file_id)
            if file_meta.get("file_size") and file_meta["file_size"] > limit: raise ValueError("Telegram attachment exceeds configured limit")
            data=client.download_file(file_meta["file_path"],limit)
            stored=storage.store(data,max_bytes=limit); stored_keys.append(stored.key)
            session.add(Attachment(company_id=event.company_id,message_id=message.id,conversation_id=message.conversation_id,storage_key=stored.key,original_filename=item.filename,safe_filename=stored.safe_filename,declared_mime_type=item.declared_mime,detected_mime_type=stored.detected_mime,size_bytes=stored.size,sha256=stored.sha256,telegram_file_id=item.file_id,status="available"))
    except Exception:
        for key in stored_keys: storage.delete(key)
        raise
    session.add(AuditLog(company_id=event.company_id,actor_id=None,action="telegram_update_processed",entity_type="external_event",entity_id=event.id,detail={"message_id":message.id,"attachment_count":len(envelope.attachments)}))
    return True


def process_event_batch(session: Session, cfg: Settings, *, limit: int=20, transport=None) -> int:
    event_ids=session.scalars(select(ExternalEvent.id).where(ExternalEvent.status.in_(["received","retry"])).order_by(ExternalEvent.received_at).limit(limit)).all(); done=0
    for event_id in event_ids:
        try:
            with session.begin_nested():
                event=session.get(ExternalEvent,event_id)
                if process_external_event(session,event,cfg,transport=transport): done += 1
        except Exception as exc:
            event=session.get(ExternalEvent,event_id); event.attempts=(event.attempts or 0)+1; event.error=str(exc)[:1000]
            event.status="dead_letter" if event.attempts >= 5 else "retry"
    return done

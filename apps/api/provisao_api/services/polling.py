"""Development polling using the same persisted inbox as webhooks."""
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import Settings
from ..models import AuditLog, ChannelBot, ExternalEvent
from .crypto import CredentialCipher
from .telegram import TelegramClient, payload_hash


def poll_active_bots(session: Session, cfg: Settings, *, transport=None) -> int:
    bots=session.scalars(select(ChannelBot).where(ChannelBot.active.is_(True),ChannelBot.mode=="polling",ChannelBot.status=="active")).all(); received=0
    cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys)
    for bot in bots:
        try:
            client=TelegramClient(cipher.decrypt(bot.token_ciphertext),api_base=cfg.telegram_api_base_url,file_base=cfg.telegram_file_base_url,timeout=cfg.telegram_request_timeout_seconds,transport=transport)
            updates=client.get_updates(bot.polling_offset,timeout=1)
            for payload in updates:
                update_id=int(payload["update_id"]); key=f"telegram:{bot.id}:{update_id}"
                if not session.scalar(select(ExternalEvent.id).where(ExternalEvent.idempotency_key==key)):
                    event=ExternalEvent(company_id=bot.company_id,channel_id=bot.channel_id,bot_id=bot.id,external_event_id=str(update_id),idempotency_key=key,payload=payload,payload_hash=payload_hash(payload),status="received")
                    session.add(event); session.flush(); session.add(AuditLog(company_id=bot.company_id,actor_id=None,action="telegram_update_polled",entity_type="external_event",entity_id=event.id,detail={"bot_id":bot.id,"update_id":str(update_id)})); received += 1
                bot.polling_offset=max(bot.polling_offset,update_id+1)
            bot.last_poll_at=datetime.now(UTC); bot.last_error=None
        except Exception as exc:
            bot.last_error=str(exc)[:500]
    return received

"""Outbox delivery through the Telegram adapter."""
from sqlalchemy.orm import Session
from ..config import Settings
from ..models import Attachment, ChannelBot, OutboxEvent
from .crypto import CredentialCipher
from .storage import LocalStorage
from .telegram import TelegramClient


class TelegramOutboxDelivery:
    def __init__(self, session: Session, cfg: Settings, *, transport=None):
        self.session=session; self.cfg=cfg; self.transport=transport

    def __call__(self, event: OutboxEvent) -> None:
        bot=self.session.get(ChannelBot,event.bot_id)
        if not bot or not bot.active or not bot.token_ciphertext: raise RuntimeError("active Telegram bot unavailable")
        token=CredentialCipher(self.cfg.telegram_token_encryption_key,self.cfg.telegram_token_encryption_previous_keys).decrypt(bot.token_ciphertext)
        client=TelegramClient(token,api_base=self.cfg.telegram_api_base_url,file_base=self.cfg.telegram_file_base_url,timeout=self.cfg.telegram_request_timeout_seconds,transport=self.transport)
        chat_id=str(event.payload.get("external_chat_id") or "")
        if not chat_id: raise ValueError("outbox item has no external chat")
        if event.event_type=="send_attachment":
            attachment=self.session.get(Attachment,event.payload.get("attachment_id"))
            if not attachment or attachment.deleted_at: raise ValueError("outbox attachment unavailable")
            data=LocalStorage(self.cfg.storage_root).read(attachment.storage_key)
            result=client.send_file(chat_id,data,attachment.safe_filename,attachment.detected_mime_type,event.payload.get("caption"))
        else:
            result=client.send_text(chat_id,str(event.payload.get("text") or ""))
        event.payload={**event.payload,"telegram_message_id":str(result.get("message_id"))}

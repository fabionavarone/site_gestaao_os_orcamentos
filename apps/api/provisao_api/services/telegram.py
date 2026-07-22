"""Telegram Bot API adapter; domain services remain provider-independent."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import httpx


class TelegramError(RuntimeError):
    def __init__(self, message: str, *, retry_after: int | None = None, permanent: bool = False):
        super().__init__(message); self.retry_after = retry_after; self.permanent = permanent


@dataclass(frozen=True)
class TelegramAttachment:
    file_id: str
    type: str
    filename: str | None = None
    declared_mime: str | None = None
    declared_size: int | None = None


@dataclass(frozen=True)
class CanonicalTelegramEnvelope:
    provider: str
    bot_id: str
    external_event_id: str
    external_message_id: str
    external_user_id: str
    external_chat_id: str
    message_type: str
    text: str | None
    caption: str | None
    reply_to_external_message_id: str | None
    attachments: tuple[TelegramAttachment, ...] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def normalize_update(update: dict, bot_id: str) -> CanonicalTelegramEnvelope | None:
    update_id = str(update.get("update_id", ""))
    message = update.get("message") or update.get("edited_message")
    if not update_id or not isinstance(message, dict): return None
    sender = message.get("from") or {}; chat = message.get("chat") or {}
    if "id" not in sender or "id" not in chat or "message_id" not in message: return None
    attachments: list[TelegramAttachment] = []
    kind = "text"
    if message.get("photo"):
        photo = message["photo"][-1]; kind = "image"; attachments.append(TelegramAttachment(str(photo["file_id"]), kind, declared_size=photo.get("file_size")))
    elif message.get("voice"):
        item=message["voice"]; kind="voice"; attachments.append(TelegramAttachment(str(item["file_id"]),kind,declared_mime=item.get("mime_type"),declared_size=item.get("file_size")))
    elif message.get("audio"):
        item=message["audio"]; kind="audio"; attachments.append(TelegramAttachment(str(item["file_id"]),kind,item.get("file_name"),item.get("mime_type"),item.get("file_size")))
    elif message.get("document"):
        item=message["document"]; kind="document"; attachments.append(TelegramAttachment(str(item["file_id"]),kind,item.get("file_name"),item.get("mime_type"),item.get("file_size")))
    elif message.get("video"):
        item=message["video"]; kind="video"; attachments.append(TelegramAttachment(str(item["file_id"]),kind,item.get("file_name"),item.get("mime_type"),item.get("file_size")))
    elif message.get("contact"): kind="contact"
    elif message.get("location"): kind="location"
    elif not message.get("text"): return None
    return CanonicalTelegramEnvelope(
        provider="telegram", bot_id=bot_id, external_event_id=update_id,
        external_message_id=str(message["message_id"]), external_user_id=str(sender["id"]),
        external_chat_id=str(chat["id"]), message_type=kind, text=message.get("text"),
        caption=message.get("caption"),
        reply_to_external_message_id=str(message["reply_to_message"]["message_id"]) if message.get("reply_to_message") else None,
        attachments=tuple(attachments),
        metadata={"edited": "edited_message" in update, "username": sender.get("username"), "display_name": " ".join(filter(None,[sender.get("first_name"),sender.get("last_name")])) or None, "contact": message.get("contact"), "location": message.get("location")},
        occurred_at=datetime.fromtimestamp(message.get("date", int(datetime.now(UTC).timestamp())), UTC),
    )


class TelegramClient:
    def __init__(self, token: str, *, api_base: str = "https://api.telegram.org", file_base: str = "https://api.telegram.org/file", timeout: float = 15, transport=None):
        self.token=token; self.api_base=api_base.rstrip("/"); self.file_base=file_base.rstrip("/")
        self.client=httpx.Client(timeout=timeout, transport=transport)

    def _call(self, method: str, data: dict | None = None, files=None):
        response=self.client.post(f"{self.api_base}/bot{self.token}/{method}", data=data, files=files)
        try: payload=response.json()
        except ValueError as exc: raise TelegramError("invalid Telegram response") from exc
        if response.status_code >= 400 or not payload.get("ok"):
            retry=(payload.get("parameters") or {}).get("retry_after")
            raise TelegramError(str(payload.get("description","Telegram request failed"))[:500],retry_after=retry,permanent=response.status_code in {400,401,403,404})
        return payload.get("result")

    def get_me(self): return self._call("getMe")
    def set_webhook(self, url: str, secret: str): return self._call("setWebhook", {"url":url,"secret_token":secret,"drop_pending_updates":"false"})
    def delete_webhook(self): return self._call("deleteWebhook", {"drop_pending_updates":"false"})
    def webhook_info(self): return self._call("getWebhookInfo")
    def get_updates(self, offset: int, timeout: int = 20): return self._call("getUpdates", {"offset":str(offset),"timeout":str(timeout),"allowed_updates":json.dumps(["message","edited_message"])})
    def get_file(self, file_id: str): return self._call("getFile", {"file_id":file_id})
    def download_file(self, path: str, max_bytes: int) -> bytes:
        with self.client.stream("GET",f"{self.file_base}/bot{self.token}/{path}") as response:
            response.raise_for_status(); chunks=[]; total=0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes: raise TelegramError("Telegram file exceeds configured limit", permanent=True)
                chunks.append(chunk)
        return b"".join(chunks)
    def send_text(self, chat_id: str, text: str): return self._call("sendMessage", {"chat_id":chat_id,"text":text})
    def send_file(self, chat_id: str, data: bytes, filename: str, mime: str, caption: str | None = None):
        field="photo" if mime.startswith("image/") else "audio" if mime.startswith("audio/") else "video" if mime.startswith("video/") else "document"
        return self._call("send"+field.capitalize(), {"chat_id":chat_id,"caption":caption or ""}, {field:(filename,data,mime)})


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

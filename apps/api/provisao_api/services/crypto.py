"""Authenticated encryption for provider credentials."""
import hashlib
from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CredentialCipher:
    def __init__(self, current_key: str, previous_keys: str = ""):
        values = [current_key, *[item.strip() for item in previous_keys.split(",") if item.strip()]]
        if not current_key:
            raise ValueError("TELEGRAM_TOKEN_ENCRYPTION_KEY is required")
        try:
            self._cipher = MultiFernet([Fernet(value.encode()) for value in values])
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid Telegram token encryption key") from exc

    def encrypt(self, token: str) -> str:
        if not token or len(token) > 256:
            raise ValueError("invalid Telegram token")
        return self._cipher.encrypt(token.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("unable to decrypt Telegram token") from exc

    def rotate(self, ciphertext: str) -> str:
        try:
            return self._cipher.rotate(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("unable to rotate Telegram token") from exc


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def masked_token(fingerprint: str | None) -> str | None:
    return f"•••••••• ({fingerprint})" if fingerprint else None

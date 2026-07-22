from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    app_secret_key: str
    database_url: str
    redis_url: str
    frontend_origins: str = "http://localhost,http://127.0.0.1"
    public_base_url: str = "http://localhost"
    telegram_webhook_max_bytes: int = 1_048_576
    max_upload_bytes: int = 26_214_400
    max_image_bytes: int = 10_485_760
    max_audio_bytes: int = 26_214_400
    max_document_bytes: int = 26_214_400
    max_video_bytes: int = 52_428_800
    storage_root: str = "/var/lib/provisao/uploads"
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_file_base_url: str = "https://api.telegram.org/file"
    telegram_request_timeout_seconds: float = 15.0
    outbox_max_attempts: int = 5
    outbox_lock_seconds: int = 60
    telegram_enabled: bool = False
    telegram_webhook_secret: str = ""
    telegram_token_encryption_key: str = ""
    telegram_token_encryption_previous_keys: str = ""
    local_llm_enabled: bool = False

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]

@lru_cache
def settings() -> Settings:
    return Settings()

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    app_secret_key: str
    database_url: str
    redis_url: str
    frontend_origins: str = "http://localhost,http://127.0.0.1"
    max_upload_bytes: int = 26_214_400
    telegram_enabled: bool = False
    telegram_webhook_secret: str = ""
    telegram_token_encryption_key: str = ""
    local_llm_enabled: bool = False

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]

@lru_cache
def settings() -> Settings:
    return Settings()

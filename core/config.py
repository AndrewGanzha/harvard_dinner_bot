from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    tg_token: str = Field(..., alias="TG_TOKEN")
    gigachat_token: str = Field("", alias="GIGACHAT_TOKEN")
    gigachat_api_url: str = Field(
        "https://gigachat.devices.sberbank.ru/api/v1",
        alias="GIGACHAT_API_URL",
    )
    gigachat_model: str = Field("GigaChat", alias="GIGACHAT_MODEL")
    gigachat_timeout_seconds: float = Field(30.0, alias="GIGACHAT_TIMEOUT_SECONDS")
    gigachat_max_retries: int = Field(3, alias="GIGACHAT_MAX_RETRIES")
    db_dsn: str = Field("sqlite+aiosqlite:///./app.db", alias="DB_DSN")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

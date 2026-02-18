from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    tg_token: str = Field(..., alias="TG_TOKEN")
    gigachat_token: str = Field("", alias="GIGACHAT_TOKEN")
    gigachat_auth_key: str = Field("", alias="GIGACHAT_AUTH_KEY")
    gigachat_oauth_url: str = Field(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="GIGACHAT_OAUTH_URL",
    )
    gigachat_scope: str = Field("GIGACHAT_API_PERS", alias="GIGACHAT_SCOPE")
    gigachat_api_url: str = Field(
        "https://gigachat.devices.sberbank.ru/api/v1",
        alias="GIGACHAT_API_URL",
    )
    gigachat_model: str = Field("GigaChat-2", alias="GIGACHAT_MODEL")
    gigachat_ssl_verify: bool = Field(True, alias="GIGACHAT_SSL_VERIFY")
    gigachat_ca_bundle: str = Field("", alias="GIGACHAT_CA_BUNDLE")
    gigachat_timeout_seconds: float = Field(30.0, alias="GIGACHAT_TIMEOUT_SECONDS")
    gigachat_max_retries: int = Field(3, alias="GIGACHAT_MAX_RETRIES")
    db_backend: str = Field("sqlite", alias="DB_BACKEND")
    db_dsn: str = Field("", alias="DB_DSN")
    db_dsn_sqlite: str = Field("sqlite+aiosqlite:///./app.db", alias="DB_DSN_SQLITE")
    db_dsn_mysql: str = Field(
        "mysql+asyncmy://harvard:harvard@mysql:3306/harvard_dinner",
        alias="DB_DSN_MYSQL",
    )
    db_auto_create: bool = Field(False, alias="DB_AUTO_CREATE")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_dsn(self) -> str:
        if self.db_dsn:
            return self.db_dsn
        if self.db_backend.lower() == "mysql":
            return self.db_dsn_mysql
        return self.db_dsn_sqlite

    @property
    def gigachat_authorization_key(self) -> str:
        # Backward compatibility: GIGACHAT_TOKEN may store Basic key in existing setups.
        return self.gigachat_auth_key or self.gigachat_token


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

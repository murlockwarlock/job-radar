from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "job-radar"
    log_level: str = "INFO"
    api_key: str | None = None
    api_docs_enabled: bool = True

    database_url: str = "postgresql+asyncpg://jobradar:change-me@postgres:5432/jobradar"
    database_sync_url: str = "postgresql+psycopg2://jobradar:change-me@postgres:5432/jobradar"
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)

    redis_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    redis_lock_ttl_seconds: int = Field(default=1800, ge=60)

    telegram_bot_token: str | None = None
    telegram_admin_chat_id: int | None = None
    telegram_polling_enabled: bool = True
    send_notifications_on_initial_sync: bool = False

    hh_access_token: str | None = None
    hh_user_agent: str = "job-radar/0.1.0 (admin@example.com)"
    hh_api_base_url: str = "https://api.hh.ru"
    hh_request_timeout_seconds: float = Field(default=20.0, gt=0)
    hh_min_request_interval_seconds: float = Field(default=1.0, ge=0)
    hh_per_page: int = Field(default=100, ge=1, le=100)
    hh_max_pages: int = Field(default=20, ge=1, le=20)

    default_polling_interval_seconds: int = Field(default=900, ge=30)
    scheduler_dispatch_interval_seconds: int = Field(default=30, ge=10)
    default_timezone: str = "UTC"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

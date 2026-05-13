from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────
    bot_token: str = Field(..., min_length=40)
    webhook_url: str | None = None
    webhook_secret: str | None = None

    # ── PostgreSQL ────────────────────────────────────────
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "exchange_db"
    postgres_user: str = "exchange_user"
    postgres_password: str = Field(..., min_length=8)

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """برای Alembic که sync نیاز داره"""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Redis ─────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    redis_fsm_db: int = 1
    redis_cache_db: int = 2

    @computed_field  # type: ignore[misc]
    @property
    def redis_fsm_url(self) -> str:
        base = self.redis_url.rsplit("/", 1)[0]
        return f"{base}/{self.redis_fsm_db}"

    @computed_field  # type: ignore[misc]
    @property
    def redis_cache_url(self) -> str:
        base = self.redis_url.rsplit("/", 1)[0]
        return f"{base}/{self.redis_cache_db}"

    # ── Celery ────────────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/3"
    celery_result_backend: str = "redis://redis:6379/4"

    # ── Rate Service ──────────────────────────────────────
    rate_cache_ttl: int = 60
    rate_provider_url: str = "https://api.exchangerate-api.com/v4/latest/USD"
    rate_provider_api_key: str = ""

    # ── Security ──────────────────────────────────────────
    admin_user_ids: list[int] = Field(default_factory=list)
    encryption_key: str = Field(..., min_length=32)

    # ── App ───────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    sentry_dsn: str | None = None

    # ── Limits ────────────────────────────────────────────
    rate_limit_requests: int = 30
    rate_limit_window: int = 60
    max_orders_per_day: int = 10

    @model_validator(mode="after")
    def validate_webhook(self) -> "Settings":
        if self.app_env == "production" and not self.webhook_url:
            raise ValueError("در محیط production باید webhook_url تنظیم بشه")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


@lru_cache
def get_settings() -> Settings:
    """
    Singleton settings - یک بار لود میشه و کش میشه.
    در تست‌ها میتونی این رو override کنی.
    """
    return Settings()  # type: ignore[call-arg]


# Shortcut برای استفاده مستقیم
settings = get_settings()

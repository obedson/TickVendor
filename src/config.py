"""Validated environment-backed application settings."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """TickVendor settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TickVendor"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    canonical_url: str = "https://tickvendor.com"
    frontend_url: str | None = None

    database_url: str = "sqlite:///./tickvendor.db"
    database_echo: bool = False

    secret_key: SecretStr = SecretStr("tickvendor-development-only-secret")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    bcrypt_rounds: int = Field(default=12, ge=12, le=16)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://tickvendor.com",
        "https://www.tickvendor.com",
    ]

    payment_provider: Literal["paystack", "flutterwave", "stripe", "test"] = "paystack"
    paystack_secret_key: SecretStr | None = None
    paystack_webhook_secret: SecretStr | None = None
    flutterwave_secret_key: SecretStr | None = None
    flutterwave_webhook_secret: SecretStr | None = None
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None

    email_provider: Literal["memory", "smtp"] = "memory"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_address: str | None = None
    push_provider: Literal["memory", "http"] = "memory"
    push_endpoint: str | None = None
    push_api_token: SecretStr | None = None
    redis_url: str | None = None
    distributed_rate_limit_enabled: bool = False
    storage_provider: Literal["local", "s3"] = "local"
    storage_local_root: str = "uploads"
    storage_bucket: str | None = None
    storage_region: str | None = None
    storage_endpoint: str | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_signed_url_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    metrics_endpoint: str | None = None
    monitoring_api_token: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json
                value = json.loads(text)
            else:
                value = text.split(",")
        if isinstance(value, list):
            return [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
        return value

    @model_validator(mode="after")
    def reject_unsafe_deployed_configuration(self) -> "Settings":
        if self.environment in {"staging", "production"}:
            secret = self.secret_key.get_secret_value()
            if len(secret) < 32 or "development" in secret or "change-me" in secret:
                raise ValueError("SECRET_KEY must be a strong deployment secret")
            if self.debug:
                raise ValueError("DEBUG must be disabled outside development and test")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed for staging or production")
            urls = (("CANONICAL_URL", self.canonical_url), ("FRONTEND_URL", self.frontend_url))
            for name, value in urls:
                if value is not None and not value.startswith("https://"):
                    raise ValueError(f"{name} must use HTTPS outside development and test")
            if self.storage_provider != "s3":
                raise ValueError("S3 object storage is required outside development and test")
            if not self.storage_bucket:
                raise ValueError("STORAGE_BUCKET is required for S3 storage")
            if not self.distributed_rate_limit_enabled or not self.redis_url:
                raise ValueError("Distributed Redis rate limiting is required outside development and test")
            if self.payment_provider == "paystack" and not self.paystack_secret_key:
                raise ValueError("PAYSTACK_SECRET_KEY is required for deployed Paystack")
            if self.email_provider == "smtp" and (not self.smtp_host or not self.smtp_from_address):
                raise ValueError("SMTP_HOST and SMTP_FROM_ADDRESS are required for SMTP")
            if self.push_provider == "http" and not self.push_endpoint:
                raise ValueError("PUSH_ENDPOINT is required for HTTP push")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
"""Validated environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TickEven settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TickEven"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./tickeven.db"
    database_echo: bool = False

    secret_key: SecretStr = SecretStr("tickeven-development-only-secret")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    bcrypt_rounds: int = Field(default=12, ge=12, le=16)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    payment_provider: Literal["paystack", "flutterwave", "stripe", "test"] = "paystack"
    paystack_secret_key: SecretStr | None = None
    flutterwave_secret_key: SecretStr | None = None
    stripe_secret_key: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
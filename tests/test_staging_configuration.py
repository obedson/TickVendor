"""Deployment settings reject unsafe local fallbacks."""
import pytest

from src.config import Settings


def deployed_settings(**overrides):
    values = {
        "environment": "staging", "secret_key": "x" * 40,
        "database_url": "postgresql+psycopg://app:secret@db/tickvendor",
        "canonical_url": "https://staging.example", "frontend_url": "https://staging.example",
        "storage_provider": "s3", "storage_bucket": "private-media",
        "distributed_rate_limit_enabled": True, "redis_url": "rediss://redis/0",
        "payment_provider": "paystack", "paystack_secret_key": "sk_test_value",
    }
    values.update(overrides)
    return Settings(**values)


def test_staging_configuration_accepts_required_production_adapters():
    assert deployed_settings().storage_provider == "s3"


@pytest.mark.parametrize("overrides", [
    {"database_url": "sqlite:///unsafe.db"},
    {"storage_provider": "local"},
    {"redis_url": None},
    {"frontend_url": "http://staging.example"},
])
def test_staging_configuration_rejects_local_or_insecure_fallbacks(overrides):
    with pytest.raises(ValueError):
        deployed_settings(**overrides)
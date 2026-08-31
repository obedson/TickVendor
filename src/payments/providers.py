"""Payment provider contracts and deterministic test adapter."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PaymentInitialization:
    provider_reference: str
    checkout_url: str


class PaymentProvider(Protocol):
    name: str
    def initialize(self, reference: str, amount: Decimal, currency: str, email: str) -> PaymentInitialization: ...
    def verify(self, provider_reference: str) -> bool: ...
    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]: ...


class TestPaymentProvider:
    name = "test"

    def initialize(self, reference: str, amount: Decimal, currency: str, email: str) -> PaymentInitialization:
        return PaymentInitialization(reference, f"https://payments.test/{reference}")

    def verify(self, provider_reference: str) -> bool:
        return provider_reference.startswith("success-")

    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]:
        import json
        if signature != "test-signature":
            raise ValueError("Invalid webhook signature")
        return json.loads(body)

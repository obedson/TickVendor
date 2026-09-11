"""Payment provider contracts and deterministic test adapter."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class PaymentProviderError(RuntimeError):
    """Safe, structured provider failure details for server-side diagnostics."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.safe_message = message[:300]
        self.http_status = http_status


@dataclass(frozen=True)
class PaymentInitialization:
    provider_reference: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentVerification:
    provider_reference: str
    amount: Decimal
    currency: str
    status: str

    @property
    def successful(self) -> bool:
        return self.status == "success"


class PaymentProvider(Protocol):
    name: str
    def initialize(self, reference: str, amount: Decimal, currency: str, email: str) -> PaymentInitialization: ...
    def verify(self, provider_reference: str) -> PaymentVerification: ...
    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]: ...
    def refund(self, provider_reference: str, amount: Decimal) -> dict[str, object]: ...


class TestPaymentProvider:
    name = "test"

    def initialize(self, reference: str, amount: Decimal, currency: str, email: str) -> PaymentInitialization:
        return PaymentInitialization(reference, f"https://payments.test/{reference}")

    def verify(self, provider_reference: str) -> PaymentVerification:
        return PaymentVerification(
            provider_reference,
            Decimal(100),
            "NGN",
            "success" if provider_reference.startswith("success-") else "failed",
        )

    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]:
        import json
        if signature != "test-signature":
            raise ValueError("Invalid webhook signature")
        return json.loads(body)

    def refund(self, provider_reference: str, amount: Decimal) -> dict[str, object]:
        return {"status": "success", "reference": provider_reference, "amount": str(amount)}

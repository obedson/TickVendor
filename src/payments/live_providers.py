"""Provider adapters for Nigeria-first payment integrations."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from src.config import settings
from src.payments.providers import (
    PaymentInitialization,
    PaymentProviderError,
    PaymentVerification,
)


def _provider_message(response: httpx.Response) -> str:
    try:
        message = response.json().get("message")
    except (ValueError, AttributeError):
        message = None
    return str(message or "Provider request was rejected").replace("\r", " ").replace("\n", " ")[:300]


class PaystackProvider:
    name = "paystack"

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str | None = None,
        callback_url: str | None = None,
    ):
        if not secret_key:
            raise ValueError("Paystack secret key is required")
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret or secret_key
        self.callback_url = callback_url or settings.frontend_url or settings.canonical_url

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    def initialize(
        self, reference: str, amount: Decimal, currency: str, email: str
    ) -> PaymentInitialization:
        try:
            response = httpx.post(
                "https://api.paystack.co/transaction/initialize",
                headers=self.headers,
                json={
                    "reference": reference,
                    "amount": int(amount * 100),
                    "currency": currency,
                    "email": email,
                    "callback_url": f"{self.callback_url.rstrip('/')}/payment/return",
                },
                timeout=15,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise PaymentProviderError("timeout", "Paystack request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise PaymentProviderError(
                "provider_rejection",
                _provider_message(exc.response),
                http_status=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise PaymentProviderError("connection", "Could not connect to Paystack") from exc
        try:
            payload = response.json()
            if payload.get("status") is False:
                raise PaymentProviderError(
                    "provider_rejection", str(payload.get("message") or "Paystack rejected initialization")
                )
            data = payload["data"]
            provider_reference = data["reference"]
            authorization_url = data["authorization_url"]
            if not isinstance(provider_reference, str) or not isinstance(authorization_url, str):
                raise TypeError("invalid initialization fields")
        except PaymentProviderError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise PaymentProviderError(
                "invalid_response", "Paystack returned an invalid initialization response"
            ) from exc
        return PaymentInitialization(provider_reference, authorization_url)

    def refund(self, provider_reference: str, amount: Decimal) -> dict[str, object]:
        response = httpx.post(
            "https://api.paystack.co/refund",
            headers=self.headers,
            json={"transaction": provider_reference, "amount": int(amount * 100)},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return {"status": data.get("status", "pending"), "reference": data.get("transaction", provider_reference)}

    def verify(self, provider_reference: str) -> PaymentVerification:
        response = httpx.get(
            f"https://api.paystack.co/transaction/verify/{provider_reference}",
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return PaymentVerification(
            str(data.get("reference", "")), Decimal(data.get("amount", 0)) / 100,
            str(data.get("currency", "")), str(data.get("status", "")),
        )

    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]:
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), body, hashlib.sha512
        ).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid Paystack webhook signature")
        event = json.loads(body)
        data = event.get("data", {})
        return {
            "event": event.get("event"),
            "provider_reference": data.get("reference"),
        }


class FlutterwaveProvider:
    name = "flutterwave"

    def __init__(self, secret_key: str, webhook_secret: str):
        if not secret_key or not webhook_secret:
            raise ValueError("Flutterwave credentials are required")
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    def initialize(
        self, reference: str, amount: Decimal, currency: str, email: str
    ) -> PaymentInitialization:
        response = httpx.post(
            "https://api.flutterwave.com/v3/payments",
            headers=self.headers,
            json={
                "tx_ref": reference,
                "amount": str(amount),
                "currency": currency,
                "customer": {"email": email},
            },
            timeout=15,
        )
        response.raise_for_status()
        return PaymentInitialization(reference, response.json()["data"]["link"])

    def verify(self, provider_reference: str) -> PaymentVerification:
        response = httpx.get(
            f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={provider_reference}",
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return PaymentVerification(
            str(data.get("tx_ref", "")), Decimal(str(data.get("amount", 0))),
            str(data.get("currency", "")),
            "success" if data.get("status") == "successful" else str(data.get("status", "")),
        )

    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]:
        if not signature or not hmac.compare_digest(signature, self.webhook_secret):
            raise ValueError("Invalid Flutterwave webhook signature")
        event = json.loads(body)
        data = event.get("data", {})
        return {
            "event": event.get("event"),
            "provider_reference": data.get("tx_ref"),
        }


class StripeProvider:
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str | None = None):
        if not secret_key:
            raise ValueError("Stripe secret key is required")
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    def initialize(self, reference: str, amount: Decimal, currency: str, email: str) -> PaymentInitialization:
        response = httpx.post("https://api.stripe.com/v1/checkout/sessions", headers=self.headers, data={
            "mode": "payment", "client_reference_id": reference, "customer_email": email,
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][product_data][name]": "TickVendor ticket",
            "line_items[0][price_data][unit_amount]": str(int(amount * 100)),
            "line_items[0][quantity]": "1", "success_url": "https://tickvendor.com/payment/success",
            "cancel_url": "https://tickvendor.com/payment/cancel"}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return PaymentInitialization(data["id"], data["url"])

    def verify(self, provider_reference: str) -> PaymentVerification:
        response = httpx.get(f"https://api.stripe.com/v1/checkout/sessions/{provider_reference}",
                             headers=self.headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return PaymentVerification(
            str(data.get("id", "")), Decimal(data.get("amount_total", 0)) / 100,
            str(data.get("currency", "")).upper(),
            "success" if data.get("payment_status") == "paid" else str(data.get("payment_status", "")),
        )

    def verify_webhook(self, body: bytes, signature: str | None) -> dict[str, object]:
        if not self.webhook_secret or not signature:
            raise ValueError("Stripe webhook secret and signature are required")
        timestamp, _, provided = signature.partition(",v1=")
        if not timestamp.startswith("t=") or not provided:
            raise ValueError("Invalid Stripe webhook signature")
        expected = hmac.new(self.webhook_secret.encode(), f"{timestamp[2:]}.".encode() + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise ValueError("Invalid Stripe webhook signature")
        event = json.loads(body)
        data = event.get("data", {}).get("object", {})
        return {"event": event.get("type"), "provider_reference": data.get("id")}

"""Provider adapters for Nigeria-first payment integrations."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from src.payments.providers import PaymentInitialization


class PaystackProvider:
    name = "paystack"

    def __init__(self, secret_key: str, webhook_secret: str | None = None):
        if not secret_key:
            raise ValueError("Paystack secret key is required")
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret or secret_key

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    def initialize(
        self, reference: str, amount: Decimal, currency: str, email: str
    ) -> PaymentInitialization:
        response = httpx.post(
            "https://api.paystack.co/transaction/initialize",
            headers=self.headers,
            json={
                "reference": reference,
                "amount": int(amount * 100),
                "currency": currency,
                "email": email,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return PaymentInitialization(data["reference"], data["authorization_url"])

    def verify(self, provider_reference: str) -> bool:
        response = httpx.get(
            f"https://api.paystack.co/transaction/verify/{provider_reference}",
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("data", {}).get("status") == "success"

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

    def verify(self, provider_reference: str) -> bool:
        response = httpx.get(
            f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={provider_reference}",
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("data", {}).get("status") == "successful"

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
            "line_items[0][price_data][product_data][name]": "TickEven ticket",
            "line_items[0][price_data][unit_amount]": str(int(amount * 100)),
            "line_items[0][quantity]": "1", "success_url": "https://tickeven.example/payment/success",
            "cancel_url": "https://tickeven.example/payment/cancel"}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return PaymentInitialization(data["id"], data["url"])

    def verify(self, provider_reference: str) -> bool:
        response = httpx.get(f"https://api.stripe.com/v1/checkout/sessions/{provider_reference}",
                             headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json().get("payment_status") == "paid"

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

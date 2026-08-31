"""Payment API schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class PaymentInitializeRequest(BaseModel):
    order_id: UUID
    idempotency_key: str = Field(min_length=16, max_length=128)


class PaymentInitializeResponse(BaseModel):
    payment_id: UUID
    provider_reference: str
    checkout_url: HttpUrl


class PaymentVerifyRequest(BaseModel):
    payment_id: UUID

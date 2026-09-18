"""Payment API schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator


class PaymentInitializeRequest(BaseModel):
    order_id: UUID
    idempotency_key: str = Field(min_length=16, max_length=128)


class PaymentInitializeResponse(BaseModel):
    payment_id: UUID
    provider_reference: str
    checkout_url: HttpUrl


class PaymentVerifyRequest(BaseModel):
    payment_id: UUID


class PaymentReferenceVerifyRequest(BaseModel):
    provider_reference: str = Field(min_length=1, max_length=128)


class PaymentCancelRequest(BaseModel):
    """The checkout a buyer is abandoning, named by whichever handle their page holds.

    A provider returns the browser to our callback URL with its own reference and no payment id, so
    the reference has to be accepted here: for a checkout that never succeeded it is the only handle
    the buyer's page is certain to have.

    `order_id` is the handle that survives a provider saying nothing at all. A checkout the buyer
    closes without paying redirects nowhere — there is no reference to hand back and no return page
    to carry it — but the buyer's own browser created the order, so it can still name the
    reservation it wants released.
    """

    payment_id: UUID | None = None
    provider_reference: str | None = Field(default=None, min_length=1, max_length=128)
    order_id: UUID | None = None

    @model_validator(mode="after")
    def require_one_handle(self):
        handles = (self.payment_id, self.provider_reference, self.order_id)
        if sum(handle is not None for handle in handles) != 1:
            raise ValueError("Provide exactly one of payment_id, provider_reference or order_id")
        return self

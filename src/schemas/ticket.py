"""Ticket inventory, order, wallet, and validation schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models import OrderStatus, TicketStatus, TicketVisibility


class TicketTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    quantity: int = Field(ge=0, le=10_000_000)
    sales_start: datetime | None = None
    sales_end: datetime | None = None
    visibility: TicketVisibility = TicketVisibility.PUBLIC
    max_per_user: int = Field(default=1, ge=1, le=100)


class TicketTypeResponse(TicketTypeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID


class OrderCreate(BaseModel):
    ticket_type_id: UUID
    quantity: int = Field(default=1, ge=1, le=100)
    idempotency_key: str = Field(min_length=16, max_length=128)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    user_id: UUID
    event_id: UUID
    status: OrderStatus
    total_amount: Decimal
    currency: str
    expires_at: datetime | None


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    public_id: str
    qr_token: str
    event_id: UUID
    ticket_type_id: UUID
    attendee_id: UUID
    order_id: UUID | None
    status: TicketStatus
    used_at: datetime | None


class TicketValidationRequest(BaseModel):
    qr_token: str = Field(min_length=32, max_length=128)


class TicketValidationResponse(BaseModel):
    result: str
    ticket: TicketResponse | None = None

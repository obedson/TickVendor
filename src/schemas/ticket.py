"""Ticket inventory, order, wallet, and validation schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models import (
    OrderStatus,
    RedemptionMode,
    TicketAssignmentState,
    TicketStatus,
    TicketVisibility,
    TransferStatus,
)


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
    max_per_order: int = Field(default=4, ge=1, le=100)


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


class TicketWalletResponse(TicketResponse):
    event_title: str
    event_starts_at: datetime
    event_ends_at: datetime | None = None
    venue_name: str | None
    venue_address: str | None
    ticket_type_name: str
    group: str
    purchaser_id: UUID | None = None
    assignment_state: TicketAssignmentState = TicketAssignmentState.CLAIMED
    transfer_state: str = "claimed"
    self_check_in_enabled: bool = False
    self_checkout_enabled: bool = False
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    duration_seconds: int | None = None


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    quantity: int | None = Field(default=None, ge=0, le=10_000_000)
    sales_start: datetime | None = None
    sales_end: datetime | None = None
    visibility: TicketVisibility | None = None
    max_per_user: int | None = Field(default=None, ge=1, le=100)
    max_per_order: int | None = Field(default=None, ge=1, le=100)


class CheckInStateResponse(BaseModel):
    attendance_id: UUID
    event_id: UUID
    ticket_id: UUID | None = None
    status: str
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    duration_seconds: int | None = None
    viable_methods: list[str] = Field(default_factory=list)


class TransferCreateInput(BaseModel):
    recipient_email: str | None = Field(default=None, max_length=320)


class TransferResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    status: TransferStatus
    expires_at: datetime
    claimed_at: datetime | None = None
    share_url: str | None = None


class TransferPreviewResponse(BaseModel):
    status: str
    claimable: bool
    expires_at: datetime | None = None
    event_title: str | None = None
    event_starts_at: datetime | None = None
    ticket_type_name: str | None = None
    requires_authentication: bool = True


class EntitlementCreate(BaseModel):
    ticket_type_id: UUID
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    quantity: int = Field(default=1, ge=0, le=1000)
    is_active: bool = True
    redemption_mode: RedemptionMode = RedemptionMode.EITHER
    redemption_starts_at: datetime | None = None
    redemption_ends_at: datetime | None = None
    requires_check_in: bool = True
    requires_checkout: bool = False
    min_attendance_minutes: int | None = Field(default=None, ge=0, le=10080)
    requires_geofence: bool = False
    requires_staff_validation: bool = True
    one_time: bool = True
    max_redemptions_per_ticket: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_window(self):
        if self.redemption_starts_at and self.redemption_ends_at and (
            self.redemption_ends_at <= self.redemption_starts_at
        ):
            raise ValueError("redemption_ends_at must be after redemption_starts_at")
        return self


class EntitlementUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    quantity: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None
    redemption_mode: RedemptionMode | None = None
    redemption_starts_at: datetime | None = None
    redemption_ends_at: datetime | None = None
    requires_check_in: bool | None = None
    requires_checkout: bool | None = None
    min_attendance_minutes: int | None = Field(default=None, ge=0, le=10080)
    requires_geofence: bool | None = None
    requires_staff_validation: bool | None = None
    one_time: bool | None = None
    max_redemptions_per_ticket: int | None = Field(default=None, ge=1, le=100)


class EntitlementResponse(EntitlementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID


class TicketEntitlementResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    quantity: int
    redemption_mode: str
    redemption_starts_at: datetime | None = None
    redemption_ends_at: datetime | None = None
    requires_check_in: bool = True
    requires_checkout: bool = False
    min_attendance_minutes: int | None = None
    requires_geofence: bool = False
    requires_staff_validation: bool = True
    remaining: int = 0
    status: str
    locked_reason: str | None = None
    last_redeemed_at: datetime | None = None


class RedemptionIssueResponse(BaseModel):
    status: str
    entitlement: str
    code: str | None = None
    qr_payload: str | None = None
    expires_at: datetime | None = None
    remaining: int | None = None


class RedemptionValidateInput(BaseModel):
    code: str | None = Field(default=None, min_length=4, max_length=4)
    qr_payload: str | None = Field(default=None, min_length=8, max_length=200)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: Decimal | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def require_credential(self):
        if not self.code and not self.qr_payload:
            raise ValueError("Enter a redemption code or scan a redemption QR")
        return self


class RedemptionValidateResponse(BaseModel):
    result: str
    entitlement: str
    event: str
    ticket: str
    public_id: str
    attendee: str
    status: str
    remaining: int
    redeemed_at: datetime | None = None


class TicketValidationRequest(BaseModel):
    qr_token: str = Field(min_length=32, max_length=128)


class TicketValidationResponse(BaseModel):
    result: str
    ticket: TicketResponse | None = None


class TicketDetailResponse(BaseModel):
    ticket: TicketResponse
    event_title: str
    event_starts_at: datetime
    event_ends_at: datetime | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    ticket_type_name: str
    self_check_in_enabled: bool = False
    self_checkout_enabled: bool = False
    attendance: CheckInStateResponse | None = None
    entitlements: list[TicketEntitlementResponse] = Field(default_factory=list)

"""Secure ticket transfer, claim-link lifecycle, and holder reassignment.

Transfer links carry a random token whose SHA-256 digest is all that is persisted. Claiming
locks the transfer row so two recipients cannot claim the same ticket, and a claim is refused
once the ticket has been checked in, used, cancelled, refunded or expired.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import (
    Attendance,
    Event,
    Ticket,
    TicketAssignmentState,
    TicketStatus,
    TicketTransfer,
    TransferStatus,
    User,
)
from src.services.availability import require_available
from src.services.event import as_utc
from src.services.notification import audit, notify

TRANSFER_TTL = timedelta(days=7)
_CLAIM_UNUSABLE_STATUSES = {
    TicketStatus.CANCELLED,
    TicketStatus.REFUNDED,
    TicketStatus.EXPIRED,
    TicketStatus.RESERVED,
    TicketStatus.PENDING_PAYMENT,
}


def hash_claim_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def transfer_state(ticket: Ticket) -> str:
    """Holder-facing state used by the wallet and the claim page."""
    if ticket.status in {TicketStatus.CANCELLED, TicketStatus.REFUNDED}:
        return "cancelled"
    if ticket.used_at is not None:
        return "checked_in"
    if ticket.assignment_state == TicketAssignmentState.UNASSIGNED:
        return "unassigned"
    if ticket.assignment_state == TicketAssignmentState.INVITATION_SENT:
        return "invitation_sent"
    return "claimed"


def _claimable(db: Session, ticket: Ticket) -> None:
    if ticket.status in _CLAIM_UNUSABLE_STATUSES:
        raise HTTPException(status_code=409, detail="This ticket is no longer valid for transfer")
    if ticket.status != TicketStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This ticket is no longer valid for transfer")
    if ticket.used_at is not None:
        raise HTTPException(status_code=409, detail="This ticket has already been used")
    if db.scalar(select(Attendance.id).where(
        Attendance.event_id == ticket.event_id,
        Attendance.user_id == ticket.attendee_id,
        Attendance.checked_in_at.is_not(None),
    )) is not None:
        raise HTTPException(status_code=409, detail="This ticket has already been checked in")


def create_transfer(
    db: Session,
    ticket: Ticket,
    user: User,
    *,
    recipient_email: str | None = None,
) -> tuple[TicketTransfer, str]:
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if ticket is None or ticket.attendee_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    event = require_available(db, db.get(Event, ticket.event_id))
    _claimable(db, ticket)
    now = datetime.now(UTC)
    for pending in db.scalars(select(TicketTransfer).where(
        TicketTransfer.ticket_id == ticket.id,
        TicketTransfer.status == TransferStatus.PENDING,
    ).with_for_update()):
        pending.status = TransferStatus.CANCELLED
    token = token_urlsafe(32)
    transfer = TicketTransfer(
        ticket_id=ticket.id,
        created_by_id=user.id,
        recipient_email=(recipient_email or None),
        claim_token_hash=hash_claim_token(token),
        status=TransferStatus.PENDING,
        expires_at=now + TRANSFER_TTL,
    )
    ticket.assignment_state = TicketAssignmentState.INVITATION_SENT
    db.add(transfer)
    db.flush()
    audit(db, actor_id=user.id, community_id=event.community_id, action="ticket.transfer_created",
          target_type="ticket", target_id=ticket.id,
          metadata={"transfer_id": str(transfer.id), "expires_at": transfer.expires_at.isoformat()},
          commit=False)
    db.commit()
    return transfer, token


def cancel_transfer(db: Session, ticket: Ticket, user: User) -> TicketTransfer:
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if ticket is None or ticket.attendee_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    transfer = db.scalar(select(TicketTransfer).where(
        TicketTransfer.ticket_id == ticket.id,
        TicketTransfer.status == TransferStatus.PENDING,
    ).with_for_update())
    if transfer is None:
        raise HTTPException(status_code=404, detail="No pending transfer for this ticket")
    transfer.status = TransferStatus.CANCELLED
    ticket.assignment_state = TicketAssignmentState.CLAIMED
    event = db.get(Event, ticket.event_id)
    audit(db, actor_id=user.id, community_id=event.community_id if event else None,
          action="ticket.transfer_cancelled", target_type="ticket", target_id=ticket.id,
          metadata={"transfer_id": str(transfer.id)}, commit=False)
    db.commit()
    return transfer


def _expire(db: Session, transfer: TicketTransfer) -> None:
    transfer.status = TransferStatus.EXPIRED
    ticket = db.get(Ticket, transfer.ticket_id)
    if ticket is not None and ticket.assignment_state == TicketAssignmentState.INVITATION_SENT:
        ticket.assignment_state = TicketAssignmentState.CLAIMED
    db.commit()


def transfer_preview(db: Session, token: str) -> dict:
    """Anonymous-safe preview. Never reveals who currently holds the ticket."""
    transfer = db.scalar(select(TicketTransfer).where(
        TicketTransfer.claim_token_hash == hash_claim_token(token)
    ))
    if transfer is None:
        raise HTTPException(status_code=404, detail="This transfer link is not valid")
    if transfer.status == TransferStatus.PENDING and as_utc(transfer.expires_at) <= datetime.now(UTC):
        _expire(db, transfer)
    ticket = db.get(Ticket, transfer.ticket_id)
    event = db.get(Event, ticket.event_id) if ticket else None
    from src.models import TicketType
    ticket_type = db.get(TicketType, ticket.ticket_type_id) if ticket else None
    return {
        "status": transfer.status.value,
        "claimable": transfer.status == TransferStatus.PENDING,
        "expires_at": transfer.expires_at,
        "event_title": event.title if event else None,
        "event_starts_at": event.starts_at if event else None,
        "ticket_type_name": ticket_type.name if ticket_type else None,
        "requires_authentication": True,
    }


def claim_transfer(db: Session, token: str, user: User) -> Ticket:
    # Every transfer mutation locks the ticket before the transfer row. The token lookup is
    # therefore a plain read, and the transfer is re-read under `populate_existing` once both
    # locks are held, so a concurrent claim of the same link is still detected.
    found = db.scalar(select(TicketTransfer).where(
        TicketTransfer.claim_token_hash == hash_claim_token(token)
    ))
    if found is None:
        raise HTTPException(status_code=404, detail="This transfer link is not valid")
    ticket = db.scalar(select(Ticket).where(Ticket.id == found.ticket_id).with_for_update())
    if ticket is None:
        raise HTTPException(status_code=404, detail="This transfer link is not valid")
    transfer = db.scalar(select(TicketTransfer).where(
        TicketTransfer.id == found.id
    ).with_for_update().execution_options(populate_existing=True))
    if transfer is None:
        raise HTTPException(status_code=404, detail="This transfer link is not valid")
    if transfer.status == TransferStatus.CLAIMED:
        raise HTTPException(status_code=409, detail="This ticket has already been claimed")
    if transfer.status != TransferStatus.PENDING:
        raise HTTPException(status_code=409, detail="This transfer link is no longer active")
    if as_utc(transfer.expires_at) <= datetime.now(UTC):
        _expire(db, transfer)
        raise HTTPException(status_code=409, detail="This transfer link has expired")
    if ticket.attendee_id == user.id:
        raise HTTPException(status_code=409, detail="You already hold this ticket")
    _claimable(db, ticket)
    now = datetime.now(UTC)
    previous_holder = ticket.attendee_id
    ticket.attendee_id = user.id
    ticket.assignment_state = TicketAssignmentState.CLAIMED
    transfer.status = TransferStatus.CLAIMED
    transfer.recipient_user_id = user.id
    transfer.claimed_at = now
    for other in db.scalars(select(TicketTransfer).where(
        TicketTransfer.ticket_id == ticket.id,
        TicketTransfer.status == TransferStatus.PENDING,
        TicketTransfer.id != transfer.id,
    ).with_for_update()):
        other.status = TransferStatus.CANCELLED
    event = db.get(Event, ticket.event_id)
    audit(db, actor_id=user.id, community_id=event.community_id if event else None,
          action="ticket.claimed", target_type="ticket", target_id=ticket.id,
          metadata={"transfer_id": str(transfer.id), "previous_holder_id": str(previous_holder)},
          commit=False)
    db.commit()
    notify(db, user.id, "ticket_claimed", "Ticket added to your wallet",
           f"Your ticket for {event.title if event else 'an event'} is now in My Tickets.",
           {"ticket_id": str(ticket.id), "event_id": str(ticket.event_id)},
           community_id=event.community_id if event else None, commit=False)
    db.commit()
    return ticket

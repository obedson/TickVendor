"""Privileged tenant-scoped audit log query API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import AuditLog, MembershipRole, User

router = APIRouter(prefix="/admin/communities/{community_id}/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    community_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    actor_id: UUID | None = None,
    action: str | None = Query(default=None, min_length=2, max_length=100),
    target_type: str | None = Query(default=None, min_length=2, max_length=80),
    target_id: UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    query = select(AuditLog).where(AuditLog.community_id == community_id)
    if actor_id is not None: query = query.where(AuditLog.actor_id == actor_id)
    if action is not None: query = query.where(AuditLog.action == action)
    if target_type is not None: query = query.where(AuditLog.target_type == target_type)
    if target_id is not None: query = query.where(AuditLog.target_id == target_id)
    if occurred_from is not None: query = query.where(AuditLog.occurred_at >= occurred_from)
    if occurred_to is not None: query = query.where(AuditLog.occurred_at <= occurred_to)
    rows = db.scalars(query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return [{"id": str(row.id), "actor_id": str(row.actor_id) if row.actor_id else None,
             "action": row.action, "target_type": row.target_type,
             "target_id": str(row.target_id) if row.target_id else None,
             "occurred_at": row.occurred_at.replace(tzinfo=row.occurred_at.tzinfo or UTC).isoformat(),
             "metadata": _redact(row.metadata_json)} for row in rows]


def _redact(value):
    if isinstance(value, dict):
        blocked = {"password", "password_hash", "token", "access_token", "refresh_token", "secret", "api_key", "webhook_secret", "credentials"}
        return {key: "[REDACTED]" if key.lower() in blocked else _redact(item) for key, item in value.items()}
    if isinstance(value, list): return [_redact(item) for item in value]
    return value

"""Scoped bulk task assignment with set-based lookup and durable notifications."""
import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select

from src.authorization import require_community_role
from src.models import (
    Membership,
    MembershipRole,
    MembershipStatus,
    Profile,
    ScheduledNotification,
    Task,
    TaskAssignment,
    User,
)
from src.services.availability import require_available
from src.services.notification import audit


def eligible_query(task):
    return select(User, Profile).join(Membership, Membership.user_id == User.id).outerjoin(Profile, Profile.user_id == User.id).where(
        Membership.community_id == task.community_id, Membership.status == MembershipStatus.ACTIVE, User.is_active.is_(True))


def resolve(db, task, actor, emails=None, search="", all_members=False):
    require_community_role(db, task.community_id, actor, MembershipRole.ORGANIZER)
    require_available(db, task)
    if not task.is_active:
        raise HTTPException(409, "Task is inactive")
    query = eligible_query(task)
    normalized, invalid = set(), set()
    if emails is not None:
        entries = [v.strip().lower() for v in re.split(r"[,;\s]+", emails) if v.strip()]
        if len(entries) > 1000:
            raise HTTPException(422, "Paste at most 1000 email addresses per batch")
        for entry in entries:
            try:
                normalized.add(str(TypeAdapter(EmailStr).validate_python(entry)).lower())
            except ValueError:
                invalid.add(entry)
        query = query.where(func.lower(User.email).in_(normalized))
    elif search:
        query = query.where(func.lower(User.email).contains(search.lower()) | func.lower(Profile.display_name).contains(search.lower()) | func.lower(Profile.username).contains(search.lower()))
    rows = db.execute(query.order_by(User.id).limit(5001 if all_members else 1001)).all()
    if len(rows) > (5000 if all_members else 1000):
        raise HTTPException(422, "Selection exceeds batch limit; narrow the search or use pasted email batches")
    resolved = [{"user_id": str(user.id), "email": user.email, "name": profile.display_name if profile else "Community member"} for user, profile in rows]
    fingerprint = hashlib.sha256((str(task.id) + ":" + ",".join(row['user_id'] for row in resolved)).encode()).hexdigest()
    return {"members": resolved, "unresolved": sorted(normalized - {u.email.lower() for u, _ in rows}),
            "invalid": sorted(invalid), "count": len(rows), "selection_version": fingerprint}


def assign_bulk(db, task, actor, selected_ids, all_members=False, selection_version=None):
    task = db.scalar(select(Task).where(Task.id == task.id).with_for_update().execution_options(populate_existing=True))
    require_community_role(db, task.community_id, actor, MembershipRole.ORGANIZER)
    require_available(db, task)
    if not task.is_active:
        raise HTTPException(409, "Task is inactive")
    if all_members:
        result = resolve(db, task, actor, all_members=True)
        if not selection_version or selection_version != result['selection_version']:
            raise HTTPException(409, "Eligible membership changed. Preview and confirm the current selection again.")
        wanted = {UUID(m['user_id']) for m in result['members']}
    else:
        wanted = set(selected_ids)
        if not wanted:
            raise HTTPException(422, "Select at least one eligible member")
        # Re-query the selected IDs; never infer identity outside this community.
        result = db.execute(eligible_query(task).where(User.id.in_(wanted))).all()
        eligible = {user.id for user, _ in result}
        if wanted - eligible:
            raise HTTPException(422, "One or more selected members are no longer eligible in this community")
    existing = set(db.scalars(select(TaskAssignment.assignee_id).where(TaskAssignment.task_id == task.id, TaskAssignment.assignee_id.in_(wanted))))
    additions = [TaskAssignment(task_id=task.id, assignee_id=user_id, assigned_by_id=actor.id) for user_id in sorted(wanted - existing, key=str)]
    db.add_all(additions); db.flush()
    db.add_all([ScheduledNotification(user_id=row.assignee_id, community_id=task.community_id,
        notification_type="task_assigned", title="Task assigned", message=f"You have been assigned: {task.title}",
        payload={"task_id": str(task.id), "assignment_id": str(row.id)}, scheduled_at=datetime.now(UTC),
        idempotency_key=f"task:{row.id}:assigned") for row in additions])
    if additions:
        audit(db, actor_id=actor.id, community_id=task.community_id, action="task.bulk_assigned", target_type="task", target_id=task.id,
              metadata={"assigned": len(additions), "already_assigned": len(existing), "all_eligible": all_members}, commit=False)
    db.commit()
    return {"assigned": len(additions), "already_assigned": len(existing)}

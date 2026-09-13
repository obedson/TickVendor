"""Task lifecycle service."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Event,
    Membership,
    MembershipRole,
    MembershipStatus,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    User,
)
from src.services.availability import require_available
from src.services.event import as_utc
from src.services.impact import award_points
from src.services.notification import audit, notify
from src.services.point_policy import task_award_points, validate_task_reward
from src.services.recognition import evaluate_recognition
from src.services.task_assessment import grade, validate_config


def create_task(db: Session, community_id, creator: User, **values) -> Task:
    require_community_role(db, community_id, creator, MembershipRole.ORGANIZER)
    validate_task_reward(db, community_id, values.get("impact_point_reward", 0))
    try:
        values['task_config'] = validate_config(values.get('task_type', 'general'), values.get('task_config', {}))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    values['attachments'] = [str(url) for url in values.get('attachments', [])]
    values['reward_mode'] = 'explicit'
    event_id = values.get("event_id")
    if event_id:
        event = db.get(Event, event_id)
        if event is None or event.community_id != community_id:
            raise HTTPException(status_code=404, detail="Event not found")
    task = Task(community_id=community_id, created_by_id=creator.id, **values)
    db.add(task); db.flush()
    audit(db, actor_id=creator.id, community_id=community_id, action="task.created", target_type="task", target_id=task.id, commit=False)
    db.commit(); return task


def assign_task(db: Session, task: Task, assignee_id, assigner: User) -> TaskAssignment:
    task = db.scalar(select(Task).where(Task.id == task.id).with_for_update())
    require_available(db, task)
    require_community_role(db, task.community_id, assigner, MembershipRole.ORGANIZER)
    member = db.scalar(select(Membership).where(
        Membership.community_id == task.community_id,
        Membership.user_id == assignee_id,
        Membership.status == MembershipStatus.ACTIVE,
    ))
    if member is None:
        raise HTTPException(status_code=404, detail="Task assignee not found in community")
    existing = db.scalar(select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.assignee_id == assignee_id))
    if existing:
        return existing
    assignment = TaskAssignment(task_id=task.id, assignee_id=assignee_id, assigned_by_id=assigner.id)
    db.add(assignment); db.flush()
    audit(db, actor_id=assigner.id, community_id=task.community_id, action="task.assigned", target_type="task_assignment", target_id=assignment.id, commit=False)
    db.commit(); return assignment


def transition_assignment(db: Session, assignment: TaskAssignment, user: User,
                          target: TaskAssignmentStatus) -> TaskAssignment:
    require_available(db, db.get(Task, assignment.task_id))
    if assignment.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="Task is not assigned to this user")
    require_community_role(db, db.get(Task, assignment.task_id).community_id, user)
    allowed = {
        TaskAssignmentStatus.ASSIGNED: TaskAssignmentStatus.ACCEPTED,
        TaskAssignmentStatus.ACCEPTED: TaskAssignmentStatus.IN_PROGRESS,
    }
    if allowed.get(assignment.status) != target:
        raise HTTPException(status_code=409, detail="Invalid task assignment transition")
    assignment.status = target
    if target == TaskAssignmentStatus.ACCEPTED:
        assignment.accepted_at = datetime.now(UTC)
    db.commit()
    return assignment


def _validate_evidence(task: Task, evidence_text, evidence_url, evidence_attachments) -> None:
    """Enforce required_evidence_types configured on the task."""
    required = set(task.required_evidence_types if task.required_evidence_types is not None else ["text"])
    if "text" in required and (not evidence_text or not evidence_text.strip()):
        raise HTTPException(status_code=422, detail="This task requires a text description of your evidence.")
    if "url" in required and not evidence_url:
        raise HTTPException(status_code=422, detail="This task requires a URL as evidence.")
    if "attachment" in required and not evidence_attachments:
        raise HTTPException(status_code=422, detail="This task requires at least one attachment as evidence.")


def submit_task(db: Session, assignment: TaskAssignment, user: User, evidence_text=None, evidence_url=None, evidence_attachments=None, answers=None, idempotency_key=None):
    assignment = db.scalar(select(TaskAssignment).where(TaskAssignment.id == assignment.id).with_for_update().execution_options(populate_existing=True))
    require_available(db, db.get(Task, assignment.task_id))
    if assignment.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="Task is not assigned to this user")
    require_community_role(db, db.get(Task, assignment.task_id).community_id, user)
    if idempotency_key:
        existing = db.scalar(select(TaskSubmission).where(TaskSubmission.idempotency_key == idempotency_key))
        if existing:
            if existing.assignment_id != assignment.id or existing.answers != (answers or {}) or existing.evidence_text != evidence_text or existing.evidence_url != evidence_url or existing.evidence_attachments != (evidence_attachments or []):
                raise HTTPException(409, "Submission request key conflict")
            if assignment.status == TaskAssignmentStatus.VERIFIED:
                evaluate_recognition(db, assignment.assignee_id, db.get(Task, assignment.task_id).community_id)
            return existing
    if assignment.status not in {TaskAssignmentStatus.ASSIGNED, TaskAssignmentStatus.ACCEPTED, TaskAssignmentStatus.IN_PROGRESS, TaskAssignmentStatus.REJECTED}:
        raise HTTPException(status_code=409, detail="Task cannot be submitted in its current state")
    task = db.get(Task, assignment.task_id)
    _validate_evidence(task, evidence_text, evidence_url, evidence_attachments)
    now = datetime.now(UTC)
    if task.due_at and now > as_utc(task.due_at):
        assignment.status = TaskAssignmentStatus.OVERDUE
        db.commit()
        raise HTTPException(status_code=409, detail="Task is overdue")
    attempt = db.scalar(select(func.count(TaskSubmission.id)).where(TaskSubmission.assignment_id == assignment.id)) + 1
    result = grade(task, answers or {}, attempt)
    submission = TaskSubmission(
        assignment_id=assignment.id, evidence_text=evidence_text,
        evidence_url=evidence_url, submitted_at=now,
        evidence_attachments=[str(item) for item in (evidence_attachments or [])],
        answers=answers or {}, assessment_result=result, idempotency_key=idempotency_key,
    )
    assignment.status = TaskAssignmentStatus.REJECTED if result.get('passed') is False else TaskAssignmentStatus.SUBMITTED if task.verification_required else TaskAssignmentStatus.VERIFIED
    assignment.completed_at = now
    db.add(submission)
    if assignment.status == TaskAssignmentStatus.VERIFIED and task.impact_point_reward:
        award_points(db, user_id=assignment.assignee_id, community_id=task.community_id,
                     source_type="task_completion", source_id=assignment.id,
                     idempotency_key=f"task:{assignment.id}:verified", reason=f"Completed task: {task.title}",
                     task_id=task.id, event_id=task.event_id, points_override=task_award_points(db, task), commit=False)
    db.flush()
    audit(db, actor_id=user.id, community_id=task.community_id, action="task.submitted", target_type="task_submission", target_id=submission.id,
          metadata={"assignment_id": str(assignment.id), "assessment_result": result}, commit=False)
    if assignment.status == TaskAssignmentStatus.VERIFIED:
        _notify_result(db, task, assignment, True, None)
    db.commit()
    if assignment.status == TaskAssignmentStatus.VERIFIED:
        evaluate_recognition(db, assignment.assignee_id, task.community_id)
    return submission


def verify_task(db: Session, assignment: TaskAssignment, verifier: User, approve: bool, reason=None):
    assignment = db.scalar(select(TaskAssignment).where(TaskAssignment.id == assignment.id).with_for_update().execution_options(populate_existing=True))
    require_available(db, db.get(Task, assignment.task_id))
    task = db.get(Task, assignment.task_id)
    require_community_role(db, task.community_id, verifier, MembershipRole.ORGANIZER)
    if assignment.status == TaskAssignmentStatus.VERIFIED and approve:
        evaluate_recognition(db, assignment.assignee_id, task.community_id)
        return assignment
    if assignment.status == TaskAssignmentStatus.REJECTED and not approve:
        return assignment
    if assignment.status != TaskAssignmentStatus.SUBMITTED:
        raise HTTPException(status_code=409, detail="Only submitted tasks can be verified")
    assignment.verified_by_id = verifier.id
    assignment.verified_at = datetime.now(UTC)
    assignment.status = TaskAssignmentStatus.VERIFIED if approve else TaskAssignmentStatus.REJECTED
    assignment.rejection_reason = None if approve else reason
    if approve and task.impact_point_reward:
        award_points(
            db, user_id=assignment.assignee_id, community_id=task.community_id,
            source_type="task_completion", source_id=assignment.id,
            idempotency_key=f"task:{assignment.id}:verified", reason=f"Verified task: {task.title}",
            task_id=task.id, event_id=task.event_id, points_override=task_award_points(db, task), commit=False,
        )
    audit(db, actor_id=verifier.id, community_id=task.community_id,
          action="task.verified" if approve else "task.rejected",
          target_type="task_assignment", target_id=assignment.id,
          metadata={"task_id": str(task.id), "assignee_id": str(assignment.assignee_id), "participant_reason": reason if not approve else None}, commit=False)
    _notify_result(db, task, assignment, approve, reason)
    db.commit()
    if approve:
        evaluate_recognition(db, assignment.assignee_id, task.community_id)
    return assignment


def _notify_result(db, task, assignment, approve, reason):
    from src.models import ImpactTransaction
    transaction = db.scalar(select(ImpactTransaction).where(ImpactTransaction.idempotency_key == f"task:{assignment.id}:verified"))
    points = transaction.points if transaction else 0
    notify(db, assignment.assignee_id, "task_verified" if approve else "task_rejected",
           "Task verified" if approve else "Task needs attention",
           f"{task.title} was verified. You earned {points} Impact Points." if approve else f"{task.title} needs attention: {reason or 'Please review your evidence with the organizer.'}",
           {"task_id": str(task.id), "assignment_id": str(assignment.id), "points_awarded": points},
           community_id=task.community_id, deduplication_key=f"task:{assignment.id}:verified" if approve else None, commit=False)

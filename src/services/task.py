"""Task lifecycle service."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    MembershipRole,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    User,
)
from src.services.impact import award_points
from src.services.notification import audit


def create_task(db: Session, community_id, creator: User, **values) -> Task:
    require_community_role(db, community_id, creator, MembershipRole.ORGANIZER)
    task = Task(community_id=community_id, created_by_id=creator.id, **values)
    db.add(task); db.commit(); return task


def assign_task(db: Session, task: Task, assignee_id, assigner: User) -> TaskAssignment:
    require_community_role(db, task.community_id, assigner, MembershipRole.ORGANIZER)
    assignment = TaskAssignment(task_id=task.id, assignee_id=assignee_id, assigned_by_id=assigner.id)
    db.add(assignment); db.commit(); return assignment


def submit_task(db: Session, assignment: TaskAssignment, user: User, evidence_text=None, evidence_url=None):
    if assignment.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="Task is not assigned to this user")
    if assignment.status not in {TaskAssignmentStatus.ASSIGNED, TaskAssignmentStatus.ACCEPTED, TaskAssignmentStatus.IN_PROGRESS, TaskAssignmentStatus.REJECTED}:
        raise HTTPException(status_code=409, detail="Task cannot be submitted in its current state")
    submission = TaskSubmission(
        assignment_id=assignment.id, evidence_text=evidence_text,
        evidence_url=evidence_url, submitted_at=datetime.now(UTC),
    )
    assignment.status = TaskAssignmentStatus.SUBMITTED
    db.add(submission); db.commit(); return submission


def verify_task(db: Session, assignment: TaskAssignment, verifier: User, approve: bool):
    task = db.get(Task, assignment.task_id)
    require_community_role(db, task.community_id, verifier, MembershipRole.ORGANIZER)
    if assignment.status != TaskAssignmentStatus.SUBMITTED:
        raise HTTPException(status_code=409, detail="Only submitted tasks can be verified")
    assignment.verified_by_id = verifier.id
    assignment.verified_at = datetime.now(UTC)
    assignment.status = TaskAssignmentStatus.VERIFIED if approve else TaskAssignmentStatus.REJECTED
    db.commit()
    audit(db, actor_id=verifier.id, community_id=task.community_id,
          action="task.verified" if approve else "task.rejected",
          target_type="task_assignment", target_id=assignment.id,
          metadata={"task_id": str(task.id), "assignee_id": str(assignment.assignee_id)})
    if approve and task.impact_point_reward:
        award_points(
            db, user_id=assignment.assignee_id, community_id=task.community_id,
            source_type="task_completion", source_id=assignment.id,
            idempotency_key=f"task:{assignment.id}:verified", reason=f"Verified task: {task.title}",
            task_id=task.id, event_id=task.event_id,
        )
    return assignment

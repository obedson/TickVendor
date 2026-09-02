"""Task lifecycle API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    MembershipRole,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    User,
)
from src.schemas.task import (
    AssignmentInput,
    SubmissionInput,
    TaskAssignmentResponse,
    TaskCreateInput,
    TaskResponse,
    VerificationInput,
)
from src.services.task import (
    assign_task,
    create_task,
    submit_task,
    transition_assignment,
    verify_task,
)

router = APIRouter(tags=["tasks"])


@router.get("/communities/{community_id}/task-verification-queue")
def verification_queue(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ORGANIZER)
    rows = db.execute(select(TaskAssignment, Task, TaskSubmission).join(Task, Task.id == TaskAssignment.task_id)
                      .join(TaskSubmission, TaskSubmission.assignment_id == TaskAssignment.id)
                      .where(Task.community_id == community_id, TaskAssignment.status == TaskAssignmentStatus.SUBMITTED)
                      .order_by(TaskSubmission.submitted_at, TaskAssignment.id))
    return [{"assignment_id": str(assignment.id), "task_id": str(task.id), "task_title": task.title,
             "assignee_id": str(assignment.assignee_id), "submitted_at": submission.submitted_at,
             "evidence_text": submission.evidence_text, "evidence_url": submission.evidence_url,
             "evidence_attachments": submission.evidence_attachments} for assignment, task, submission in rows]


@router.get("/communities/{community_id}/tasks", response_model=list[TaskResponse])
def list_tasks(community_id: UUID, db: Annotated[Session, Depends(get_db)],
               user: Annotated[User, Depends(get_current_user)], status_filter: TaskAssignmentStatus | None = None):
    from src.authorization import require_community_role
    require_community_role(db, community_id, user)
    query = select(Task).where(Task.community_id == community_id, Task.is_active.is_(True))
    if status_filter:
        query = query.where(Task.id.in_(select(TaskAssignment.task_id).where(TaskAssignment.status == status_filter)))
    return [{**{field: getattr(task, field) for field in ("id", "community_id", "created_by_id", "title", "description", "event_id", "due_at", "priority", "impact_point_reward", "verification_required")}, "status": "active"} for task in db.scalars(query.order_by(Task.due_at))]


@router.get("/task-assignments/me", response_model=list[TaskAssignmentResponse])
def my_assignments(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return [{"id": item.id, "task_id": item.task_id, "assignee_id": item.assignee_id,
             "status": item.status.value, "due_at": db.get(Task, item.task_id).due_at}
            for item in db.scalars(select(TaskAssignment).where(TaskAssignment.assignee_id == user.id))]


@router.get("/task-assignments/me/details")
def my_assignment_details(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    rows = db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                      .where(TaskAssignment.assignee_id == user.id).order_by(TaskAssignment.created_at))
    return [{"id": str(assignment.id), "task_id": str(task.id), "title": task.title,
             "description": task.description, "due_at": task.due_at,
             "status": assignment.status.value, "verification_required": task.verification_required,
             "impact_point_reward": task.impact_point_reward, "attachments": task.attachments}
            for assignment, task in rows]


@router.post("/task-assignments/{assignment_id}/accept")
def accept(assignment_id: UUID, db: Annotated[Session, Depends(get_db)],
           user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    return {"status": transition_assignment(db, assignment, user, TaskAssignmentStatus.ACCEPTED).status.value}


@router.post("/task-assignments/{assignment_id}/start")
def start(assignment_id: UUID, db: Annotated[Session, Depends(get_db)],
          user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    return {"status": transition_assignment(db, assignment, user, TaskAssignmentStatus.IN_PROGRESS).status.value}


@router.post("/communities/{community_id}/tasks", status_code=201)
def create(community_id: UUID, payload: TaskCreateInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    task = create_task(db, community_id, user, **payload.model_dump())
    return {"id": str(task.id), "status": "active"}


@router.post("/tasks/{task_id}/assignments", status_code=201)
def assign(task_id: UUID, payload: AssignmentInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    task = db.get(Task, task_id)
    if task is None: raise HTTPException(status_code=404, detail="Task not found")
    assignment = assign_task(db, task, payload.assignee_id, user)
    return {"id": str(assignment.id), "status": assignment.status.value}


@router.post("/task-assignments/{assignment_id}/submissions", status_code=201)
def submit(assignment_id: UUID, payload: SubmissionInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    submission = submit_task(db, assignment, user, payload.evidence_text,
                             str(payload.evidence_url) if payload.evidence_url else None,
                             payload.evidence_attachments)
    return {"id": str(submission.id)}


@router.post("/task-assignments/{assignment_id}/verify")
def verify(assignment_id: UUID, payload: VerificationInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    updated = verify_task(db, assignment, user, payload.approve)
    return {"status": updated.status.value}

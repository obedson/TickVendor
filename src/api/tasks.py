"""Task lifecycle API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Task, TaskAssignment, TaskAssignmentStatus, User
from src.schemas.task import AssignmentInput, SubmissionInput, TaskCreateInput, VerificationInput
from src.services.task import (
    assign_task,
    create_task,
    submit_task,
    transition_assignment,
    verify_task,
)

router = APIRouter(tags=["tasks"])


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
                             str(payload.evidence_url) if payload.evidence_url else None)
    return {"id": str(submission.id)}


@router.post("/task-assignments/{assignment_id}/verify")
def verify(assignment_id: UUID, payload: VerificationInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    updated = verify_task(db, assignment, user, payload.approve)
    return {"status": updated.status.value}

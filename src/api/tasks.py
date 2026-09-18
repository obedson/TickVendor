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
    Profile,
    ProfileVisibility,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    User,
)
from src.schemas.task import (
    AssignmentInput,
    BulkAssignInput,
    BulkResolveInput,
    SubmissionInput,
    TaskAssignmentResponse,
    TaskCreateInput,
    TaskResponse,
    TaskUpdateInput,
    VerificationInput,
)
from src.services.point_policy import effective_task_points, task_policy
from src.services.task import (
    assign_task,
    create_task,
    submit_task,
    transition_assignment,
    update_task,
    verify_task,
)
from src.services.task_assessment import participant_config

router = APIRouter(tags=["tasks"])


@router.get("/communities/{community_id}/task-verification-queue")
def verification_queue(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ORGANIZER)
    latest = select(TaskSubmission.id).where(TaskSubmission.assignment_id == TaskAssignment.id).order_by(TaskSubmission.submitted_at.desc(), TaskSubmission.id).limit(1).correlate(TaskAssignment).scalar_subquery()
    rows = db.execute(select(TaskAssignment, Task, TaskSubmission, Profile).join(Task, Task.id == TaskAssignment.task_id)
                      .join(TaskSubmission, TaskSubmission.assignment_id == TaskAssignment.id)
                      .outerjoin(Profile, Profile.user_id == TaskAssignment.assignee_id)
                      .where(Task.community_id == community_id, TaskAssignment.status == TaskAssignmentStatus.SUBMITTED, TaskSubmission.id == latest)
                      .order_by(TaskSubmission.submitted_at, TaskAssignment.id))
    return [{"assignment_id": str(assignment.id), "task_id": str(task.id), "task_title": task.title,
             "assignee_id": str(assignment.assignee_id), "submitted_at": submission.submitted_at,
             "evidence_text": submission.evidence_text, "evidence_url": submission.evidence_url,
             "attachment_ids": submission.attachment_ids, "location_evidence": submission.location_evidence,
             "evidence_attachments": submission.evidence_attachments, "answers": submission.answers,
             "assessment_result": submission.assessment_result,
             "location_verification": {
                 "required": bool((task.task_config or {}).get("geofence", {}).get("required")),
                 "verified": bool((submission.location_evidence or {}).get("verified")),
                 "distance_meters": (submission.location_evidence or {}).get("distance_meters"),
                 "accuracy_meters": (submission.location_evidence or {}).get("accuracy_meters"),
                 "verified_at": (submission.location_evidence or {}).get("verified_at"),
                 "geofence_radius_meters": (task.task_config or {}).get("geofence", {}).get("radius_meters"),
                 "venue_latitude": (task.task_config or {}).get("geofence", {}).get("latitude"),
                 "venue_longitude": (task.task_config or {}).get("geofence", {}).get("longitude"),
             },
             "assignee_name": (f"Private member ({assignment.assignee_id})" if profile.visibility == ProfileVisibility.PRIVATE else f"{profile.display_name} (@{profile.username})") if profile else "Community member"} for assignment, task, submission, profile in rows]


@router.get("/communities/{community_id}/tasks", response_model=list[TaskResponse])
def list_tasks(community_id: UUID, db: Annotated[Session, Depends(get_db)],
               user: Annotated[User, Depends(get_current_user)], status_filter: TaskAssignmentStatus | None = None, management: bool = False):
    from src.authorization import require_community_role
    require_community_role(db, community_id, user)
    if management:
        require_community_role(db, community_id, user, MembershipRole.ORGANIZER)
    query = select(Task).where(Task.community_id == community_id, Task.is_active.is_(True))
    from src.services.availability import visible_content
    query = query.where(visible_content(Task))
    if status_filter:
        query = query.where(Task.id.in_(select(TaskAssignment.task_id).where(TaskAssignment.status == status_filter, *([] if management else [TaskAssignment.assignee_id == user.id]))))
    policy = task_policy(db, community_id)
    return [
        {
            **{field: getattr(task, field) for field in (
                "id", "community_id", "created_by_id", "title", "description",
                "event_id", "due_at", "priority", "impact_point_reward",
                "verification_required", "attachments", "task_type", "task_config",
                "required_evidence_types",
            )},
            "task_config": task.task_config if management else participant_config(task.task_config),
            "impact_point_reward": effective_task_points(db, task, policy),
            "status": "active",
        }
        for task in db.scalars(query.order_by(Task.due_at))
    ]


@router.patch("/tasks/{task_id}")
def update(task_id: UUID, payload: TaskUpdateInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = update_task(db, task, payload.model_dump(exclude_unset=True), user)
    return {"id": str(updated.id), "is_active": updated.is_active, "status": "updated"}


@router.get("/task-assignments/me", response_model=list[TaskAssignmentResponse])
def my_assignments(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    latest = select(TaskSubmission.id).where(TaskSubmission.assignment_id == TaskAssignment.id).order_by(TaskSubmission.submitted_at.desc(), TaskSubmission.id).limit(1).correlate(TaskAssignment).scalar_subquery()
    rows = db.execute(
        select(TaskAssignment, Task, TaskSubmission)
        .join(Task, Task.id == TaskAssignment.task_id)
        .outerjoin(TaskSubmission, TaskSubmission.id == latest)
        .where(TaskAssignment.assignee_id == user.id)
        .order_by(TaskAssignment.created_at)
    )
    return [
        {"id": assignment.id, "task_id": task.id, "assignee_id": assignment.assignee_id,
         "status": assignment.status.value, "due_at": task.due_at,
         "assessment_result": submission.assessment_result if submission else {}}
        for assignment, task, submission in rows
    ]


@router.get("/task-assignments/me/details")
def my_assignment_details(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)], summary_only: bool = False):
    rows = db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                      .where(TaskAssignment.assignee_id == user.id).order_by(TaskAssignment.created_at)).all()
    if summary_only:
        return [{"id": str(assignment.id), "task_id": str(task.id), "title": task.title, "due_at": task.due_at, "status": assignment.status.value} for assignment, task in rows]
    policies = {task.community_id: None for _, task in rows}
    for community_id in policies:
        policies[community_id] = task_policy(db, community_id)
    return [{"id": str(assignment.id), "task_id": str(task.id), "title": task.title,
             "description": task.description, "due_at": task.due_at,
             "status": assignment.status.value, "verification_required": task.verification_required,
             "impact_point_reward": effective_task_points(db, task, policies[task.community_id]), "attachments": task.attachments,
             "task_type": task.task_type, "task_config": participant_config(task.task_config),
             "required_evidence_types": task.required_evidence_types}
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
                             [str(url) for url in payload.evidence_attachments], payload.answers, payload.idempotency_key, payload.attachment_ids, payload.location.model_dump() if payload.location else None)
    return {"id": str(submission.id), "assessment_result": submission.assessment_result, "status": assignment.status.value}


@router.post("/task-assignments/{assignment_id}/verify")
def verify(assignment_id: UUID, payload: VerificationInput,
           db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None: raise HTTPException(status_code=404, detail="Assignment not found")
    updated = verify_task(db, assignment, user, payload.approve, payload.reason)
    return {"status": updated.status.value}


@router.get("/communities/{community_id}/task-point-policy")
def point_policy(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user)
    return task_policy(db, community_id)


@router.get("/task-assignments/{assignment_id}/attempts")
def attempts(assignment_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None or assignment.assignee_id != user.id:
        raise HTTPException(404, "Assignment not found")
    return [{"id": str(row.id), "result": row.assessment_result, "submitted_at": row.submitted_at}
            for row in db.scalars(select(TaskSubmission).where(TaskSubmission.assignment_id == assignment_id).order_by(TaskSubmission.submitted_at))]


@router.post("/tasks/{task_id}/assignment-candidates")
def assignment_candidates(task_id: UUID, payload: BulkResolveInput, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    from src.services.task_bulk import resolve
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return resolve(db, task, user, **payload.model_dump())


@router.post("/tasks/{task_id}/assignments/bulk")
def bulk_assign(task_id: UUID, payload: BulkAssignInput, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    from src.services.task_bulk import assign_bulk
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return assign_bulk(db, task, user, **payload.model_dump())


@router.get("/tasks/{task_id}")
def task_detail(task_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
                management: bool = False):
    from src.services.availability import require_available
    task = require_available(db, db.get(Task, task_id))
    require_community_role(db, task.community_id, user)
    if management:
        # Organizer-only: full configuration, still never cached or shown to participants.
        require_community_role(db, task.community_id, user, MembershipRole.ORGANIZER)
    assignment = db.scalar(select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.assignee_id == user.id))
    submissions = list(db.scalars(select(TaskSubmission).where(TaskSubmission.assignment_id == assignment.id).order_by(TaskSubmission.submitted_at.desc()).limit(20))) if assignment else []
    return {"id": str(task.id), "community_id": str(task.community_id), "title": task.title, "description": task.description,
            "task_type": task.task_type,
            "task_config": task.task_config if management else participant_config(task.task_config), "due_at": task.due_at,
            "priority": task.priority, "verification_required": task.verification_required, "required_evidence_types": task.required_evidence_types,
            "impact_point_reward": effective_task_points(db, task), "attachments": task.attachments,
            "is_active": task.is_active,
            "assignment": {"id": str(assignment.id), "status": assignment.status.value, "rejection_reason": assignment.rejection_reason} if assignment else None,
            "history": [{"id": str(row.id), "submitted_at": row.submitted_at, "result": row.assessment_result,
                         "evidence_text": row.evidence_text, "evidence_url": row.evidence_url, "evidence_attachments": row.evidence_attachments,
                         "attachment_ids": row.attachment_ids, "location_evidence": row.location_evidence} for row in submissions]}

"""Private, authorized device evidence uploads and short-lived delivery."""
import hashlib
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    MembershipRole,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskAttachment,
    User,
)
from src.services.availability import require_available
from src.services.notification import audit
from src.storage import get_object_storage
from src.uploads import validate_image_upload

router = APIRouter(tags=["task evidence"])


@router.post("/task-assignments/{assignment_id}/attachments", status_code=201)
async def upload_attachment(assignment_id: UUID, db: Annotated[Session, Depends(get_db)],
                            user: Annotated[User, Depends(get_current_user)], upload: Annotated[UploadFile, File()]):
    assignment = db.scalar(select(TaskAssignment).where(TaskAssignment.id == assignment_id).with_for_update())
    if assignment is None or assignment.assignee_id != user.id:
        raise HTTPException(404, "Assignment not found")
    task = require_available(db, db.get(Task, assignment.task_id))
    require_community_role(db, task.community_id, user)
    if assignment.status in {TaskAssignmentStatus.SUBMITTED, TaskAssignmentStatus.VERIFIED, TaskAssignmentStatus.OVERDUE}:
        raise HTTPException(409, "Assignment is not accepting evidence")
    if db.scalar(select(func.count()).select_from(TaskAttachment).where(TaskAttachment.assignment_id == assignment_id)) >= 40:
        raise HTTPException(422, "Evidence upload limit reached; contact the organizer")
    if upload.content_type == "application/pdf":
        data = await upload.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "File exceeds 5 MB")
        if not data.startswith(b"%PDF-"):
            raise HTTPException(422, "File content does not match PDF type")
        extension = ".pdf"
    else:
        data = await validate_image_upload(upload)
        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[upload.content_type]
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(TaskAttachment).where(TaskAttachment.assignment_id == assignment_id, TaskAttachment.owner_id == user.id, TaskAttachment.sha256 == digest))
    if existing:
        return {"id": str(existing.id), "filename": existing.filename, "content_type": existing.content_type, "size_bytes": existing.size_bytes}
    file_id = uuid4()
    key = f"communities/{task.community_id}/tasks/{task.id}/evidence/{assignment.id}/{file_id}{extension}"
    filename = Path((upload.filename or "evidence").replace("\\", "/")).name
    filename = "".join(c for c in filename if c.isalnum() or c in " .-_")[:150] or "evidence" + extension
    storage = get_object_storage()
    storage.put(key, data, upload.content_type)
    item = TaskAttachment(id=file_id, assignment_id=assignment.id, owner_id=user.id, object_key=key,
                          filename=filename, content_type=upload.content_type, size_bytes=len(data), sha256=digest)
    db.add(item)
    try:
        audit(db, actor_id=user.id, community_id=task.community_id, action="task.evidence_uploaded", target_type="task_attachment", target_id=file_id,
              metadata={"assignment_id": str(assignment.id), "bytes": len(data), "content_type": upload.content_type}, commit=False)
        db.commit()
    except Exception:
        db.rollback(); storage.delete(key); raise
    return {"id": str(item.id), "filename": item.filename, "content_type": item.content_type, "size_bytes": item.size_bytes}


@router.get("/task-attachments/{attachment_id}")
def attachment(attachment_id: UUID, response: Response, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    response.headers["Cache-Control"] = "private, no-store"
    item = db.get(TaskAttachment, attachment_id)
    if item is None:
        raise HTTPException(404, "Attachment not found")
    assignment = db.get(TaskAssignment, item.assignment_id)
    task = db.get(Task, assignment.task_id)
    if item.owner_id != user.id:
        require_community_role(db, task.community_id, user, MembershipRole.ORGANIZER)
    return {"id": str(item.id), "filename": item.filename, "content_type": item.content_type,
            "size_bytes": item.size_bytes, "url": get_object_storage().get_url(item.object_key)}

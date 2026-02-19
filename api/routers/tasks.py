"""GET /v1/tasks/{id} and DELETE /v1/tasks/{id}"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Task
from api.models.schemas import TaskResponse
from api.auth import get_current_key

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    api_key=Depends(get_current_key),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.api_key_id == api_key.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_orm_task(task)


@router.delete("/{task_id}", status_code=204)
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    api_key=Depends(get_current_key),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.api_key_id == api_key.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in ("PENDING", "THROTTLED"):
        task.status = "FAILED"
        task.error = "Cancelled by user"
        db.commit()
    # If RUNNING: signal Celery to revoke (best-effort)
    return None

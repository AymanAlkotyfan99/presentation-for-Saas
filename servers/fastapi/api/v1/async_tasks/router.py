from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from services.database import get_async_session
from modules.jobs.domain.models import JobStatus
from modules.jobs.persistence.models import JobModel


async def synchronize_durable_task_view(
    task: AsyncTaskModel,
    sql_session: AsyncSession,
) -> AsyncTaskModel:
    """Project a durable job onto the legacy polling shape without rewriting history."""
    if task.durable_job_id is None:
        return task
    job = await sql_session.get(JobModel, task.durable_job_id)
    if job is None:
        return task
    if job.status == JobStatus.SUCCEEDED:
        task.status = AsyncTaskStatus.COMPLETED
    elif job.status in {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}:
        task.status = AsyncTaskStatus.ERROR
    else:
        task.status = AsyncTaskStatus.PENDING
    task.message = job.progress_message or task.message
    task.data = {
        **(task.data or {}),
        "durableJobId": str(job.id),
        "durableStatus": job.status.value,
        "progress": job.progress,
        **({"result": job.result} if job.result is not None else {}),
    }
    if job.safe_error_code:
        task.error = {
            "code": job.safe_error_code,
            "message": job.safe_error_message or "Durable job failed",
        }
    return task


API_V1_ASYNC_TASKS_ROUTER = APIRouter(
    prefix="/api/v1/async-tasks",
    tags=["Async Tasks"],
)


@API_V1_ASYNC_TASKS_ROUTER.get(
    "",
    response_model=list[AsyncTaskModel],
)
async def list_async_tasks(
    task_type: str | None = Query(default=None, alias="type"),
    status: AsyncTaskStatus | None = Query(default=None),
    created_at: datetime | None = Query(
        default=None,
        description=(
            "Only include tasks created at or after this timestamp. "
            "Alias for created_at_from."
        ),
    ),
    created_at_from: datetime | None = Query(
        default=None,
        description="Only include tasks created at or after this timestamp",
    ),
    created_at_to: datetime | None = Query(
        default=None,
        description="Only include tasks created at or before this timestamp",
    ),
    order_by: Literal["created_at", "updated_at"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sql_session: AsyncSession = Depends(get_async_session),
):
    statement = select(AsyncTaskModel)
    if task_type is not None:
        statement = statement.where(AsyncTaskModel.type == task_type)
    if status is not None:
        statement = statement.where(AsyncTaskModel.status == status)
    created_at_start = created_at_from or created_at
    if created_at_start is not None:
        statement = statement.where(AsyncTaskModel.created_at >= created_at_start)
    if created_at_to is not None:
        statement = statement.where(AsyncTaskModel.created_at <= created_at_to)

    order_column = getattr(AsyncTaskModel, order_by)
    statement = statement.order_by(
        order_column.asc() if order == "asc" else order_column.desc()
    )
    statement = statement.offset(offset).limit(limit)

    result = await sql_session.execute(statement)
    tasks = list(result.scalars().all())
    for task in tasks:
        await synchronize_durable_task_view(task, sql_session)
    return tasks


@API_V1_ASYNC_TASKS_ROUTER.get(
    "/status/{id}",
    response_model=AsyncTaskModel,
)
async def check_async_task_status(
    id: str = Path(description="ID of the async task"),
    sql_session: AsyncSession = Depends(get_async_session),
):
    task = await sql_session.get(AsyncTaskModel, id)
    if not task:
        raise HTTPException(status_code=404, detail="No async task found")
    return await synchronize_durable_task_view(task, sql_session)

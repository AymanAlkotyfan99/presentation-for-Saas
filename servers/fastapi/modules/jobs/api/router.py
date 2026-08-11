"""Tenant-scoped durable job status, cancellation, retry, and events API."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.auth.principal import principal_from_request
from modules.jobs.application.submit import append_job_event, enqueue_outbox
from modules.jobs.domain.models import JobStatus, TERMINAL_STATUSES, assert_transition
from modules.jobs.persistence.models import DeadLetterModel, JobEventModel, JobModel, OutboxMessageModel
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import Permission
from services.database import async_session_maker, get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import durable_jobs_enabled
from utils.datetime_utils import get_current_utc_datetime


def _require_enabled() -> None:
    if not durable_jobs_enabled():
        raise StableAPIError(404, "DURABLE_JOBS_DISABLED", "Durable jobs are not enabled")


JOBS_ROUTER = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Jobs"],
    dependencies=[Depends(_require_enabled)],
)


def _job_json(job: JobModel, *, include_result: bool = True) -> dict:
    value = {
        "id": str(job.id),
        "workspaceId": str(job.workspace_id),
        "operation": job.operation,
        "queueClass": job.queue_class.value,
        "status": job.status.value,
        "progress": job.progress,
        "progressMessage": job.progress_message,
        "attemptCount": job.attempt_count,
        "maxAttempts": job.max_attempts,
        "resourceType": job.resource_type,
        "resourceId": job.resource_id,
        "sourceRevision": job.source_revision,
        "safeErrorCode": job.safe_error_code,
        "safeErrorMessage": job.safe_error_message,
        "cancellationRequestedAt": job.cancellation_requested_at,
        "createdAt": job.created_at,
        "startedAt": job.started_at,
        "finishedAt": job.finished_at,
        "updatedAt": job.updated_at,
    }
    if include_result:
        value["result"] = job.result
    return value


async def _authorized_job(
    session: AsyncSession,
    request: Request,
    job_id: UUID,
    permission: Permission,
    *,
    lock: bool = False,
) -> JobModel:
    statement = select(JobModel).where(JobModel.id == job_id)
    if lock:
        statement = statement.with_for_update()
    job = await session.scalar(statement)
    if job is None:
        raise StableAPIError(404, "JOB_NOT_FOUND", "Job not found")
    principal = principal_from_request(request)
    await authorize_workspace(
        session,
        principal=principal,
        workspace_id=job.workspace_id,
        permission=permission,
        resource_workspace_id=job.workspace_id,
    )
    return job


@JOBS_ROUTER.get("")
async def list_jobs(
    request: Request,
    status: JobStatus | None = Query(default=None),
    operation: str | None = Query(default=None, max_length=96),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    principal = principal_from_request(request)
    if principal.workspace_id is None:
        raise StableAPIError(409, "WORKSPACE_CONTEXT_REQUIRED", "Current workspace is unavailable")
    await authorize_workspace(
        session,
        principal=principal,
        workspace_id=principal.workspace_id,
        permission=Permission.JOBS_READ,
    )
    statement = select(JobModel).where(JobModel.workspace_id == principal.workspace_id)
    if status is not None:
        statement = statement.where(JobModel.status == status)
    if operation is not None:
        statement = statement.where(JobModel.operation == operation)
    jobs = list((await session.scalars(statement.order_by(JobModel.created_at.desc()).offset(offset).limit(limit))).all())
    return [_job_json(job, include_result=False) for job in jobs]


@JOBS_ROUTER.get("/metrics")
async def job_metrics(request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = principal_from_request(request)
    if principal.workspace_id is None:
        raise StableAPIError(409, "WORKSPACE_CONTEXT_REQUIRED", "Current workspace is unavailable")
    await authorize_workspace(session, principal=principal, workspace_id=principal.workspace_id, permission=Permission.JOBS_READ)
    status_rows = (
        await session.execute(
            select(JobModel.status, func.count(JobModel.id))
            .where(JobModel.workspace_id == principal.workspace_id)
            .group_by(JobModel.status)
        )
    ).all()
    outbox_backlog = await session.scalar(
        select(func.count(OutboxMessageModel.id)).where(
            OutboxMessageModel.workspace_id == principal.workspace_id,
            OutboxMessageModel.published_at.is_(None),
        )
    )
    dead_letters = await session.scalar(
        select(func.count(DeadLetterModel.id)).where(DeadLetterModel.workspace_id == principal.workspace_id)
    )
    return {
        "statusCounts": {status.value: count for status, count in status_rows},
        "outboxBacklog": outbox_backlog or 0,
        "deadLetters": dead_letters or 0,
    }


@JOBS_ROUTER.get("/{job_id}")
async def get_job(job_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    return _job_json(await _authorized_job(session, request, job_id, Permission.JOBS_READ))


@JOBS_ROUTER.post("/{job_id}/cancel")
async def cancel_job(job_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    job = await _authorized_job(session, request, job_id, Permission.JOBS_WRITE, lock=True)
    now = get_current_utc_datetime()
    if job.status in TERMINAL_STATUSES:
        return _job_json(job)
    if job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
        assert_transition(job.status, JobStatus.CANCELLED)
        job.status = JobStatus.CANCELLED
        job.finished_at = now
        event_type = "cancelled"
    else:
        if job.status == JobStatus.RUNNING:
            assert_transition(job.status, JobStatus.CANCELLATION_REQUESTED)
            job.status = JobStatus.CANCELLATION_REQUESTED
        job.cancellation_requested_at = now
        event_type = "cancellation_requested"
    await append_job_event(session, job, event_type)
    await session.commit()
    await session.refresh(job)
    return _job_json(job)


@JOBS_ROUTER.post("/{job_id}/retry")
async def retry_job(job_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    job = await _authorized_job(session, request, job_id, Permission.JOBS_WRITE, lock=True)
    if job.status != JobStatus.FAILED:
        raise StableAPIError(409, "JOB_NOT_RETRYABLE", "Only a failed job may be explicitly requeued")
    assert_transition(job.status, JobStatus.QUEUED)
    job.status = JobStatus.QUEUED
    job.available_at = get_current_utc_datetime()
    job.finished_at = None
    job.safe_error_code = None
    job.safe_error_message = None
    await enqueue_outbox(session, job)
    await append_job_event(session, job, "manually_requeued", {"attemptsSoFar": job.attempt_count})
    await session.commit()
    await session.refresh(job)
    return _job_json(job)


@JOBS_ROUTER.get("/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    last_event_id_header: int | None = Header(default=None, alias="Last-Event-ID"),
    after: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    job = await _authorized_job(session, request, job_id, Permission.JOBS_READ)
    workspace_id = job.workspace_id
    cursor = max(last_event_id_header or 0, after or 0)

    async def stream():
        nonlocal cursor
        idle = 0
        while idle < 30:
            if await request.is_disconnected():
                return
            async with async_session_maker() as event_session:
                events = list(
                    (
                        await event_session.scalars(
                            select(JobEventModel)
                            .where(
                                JobEventModel.workspace_id == workspace_id,
                                JobEventModel.job_id == job_id,
                                JobEventModel.id > cursor,
                            )
                            .order_by(JobEventModel.id)
                            .limit(100)
                        )
                    ).all()
                )
                current = await event_session.get(JobModel, job_id)
            if events:
                idle = 0
                for event in events:
                    cursor = int(event.id or cursor)
                    body = json.dumps(
                        {"type": event.event_type, "data": event.safe_data, "createdAt": event.created_at.isoformat()},
                        separators=(",", ":"),
                    )
                    yield f"id: {cursor}\nevent: {event.event_type}\ndata: {body}\n\n"
            else:
                idle += 1
                yield ": keepalive\n\n"
            if current is None or (current.status in TERMINAL_STATUSES and not events):
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

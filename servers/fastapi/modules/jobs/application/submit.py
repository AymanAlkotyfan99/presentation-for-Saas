"""Atomic durable job and transactional-outbox submission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.jobs.domain.models import JobStatus, QueueClass
from modules.jobs.persistence.models import JobEventModel, JobModel, OutboxMessageModel
from utils.api_errors import StableAPIError


MAX_JOB_PAYLOAD_BYTES = 64 * 1024
MAX_JOB_RESULT_BYTES = 128 * 1024


@dataclass(frozen=True)
class JobSubmission:
    operation: str
    queue_class: QueueClass
    workspace_id: UUID
    actor_id: UUID | None
    actor_service_account_id: UUID | None
    idempotency_scope: str
    idempotency_key: str
    payload: BaseModel | dict[str, Any]
    max_attempts: int = 3
    payload_schema_version: int = 1
    resource_type: str | None = None
    resource_id: str | None = None
    source_revision: int | None = None
    trace_id: str | None = None


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def bounded_json(value: Any, *, maximum: int, label: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        raise StableAPIError(422, "JOB_PAYLOAD_INVALID", f"{label} must be an object")
    encoded = canonical_json(value)
    if len(encoded) > maximum:
        raise StableAPIError(413, "JOB_PAYLOAD_TOO_LARGE", f"{label} exceeds its durable size limit")
    return value


_SECRET_KEYS = frozenset(
    {
        "apikey", "api_key", "authorization", "cookie", "password",
        "secret", "sessiontoken", "session_token", "access_token", "refresh_token",
    }
)


def assert_secret_free_payload(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SECRET_KEYS or normalized.endswith("_secret"):
                raise StableAPIError(
                    422,
                    "JOB_PAYLOAD_CONTAINS_SECRET",
                    f"Durable job payload contains a forbidden secret field at {path}",
                )
            assert_secret_free_payload(item, f"{path}.{key}")
    elif isinstance(value, list):
        for item in value:
            assert_secret_free_payload(item, path)


async def append_job_event(
    session: AsyncSession,
    job: JobModel,
    event_type: str,
    safe_data: dict[str, Any] | None = None,
) -> JobEventModel:
    event = JobEventModel(
        workspace_id=job.workspace_id,
        job_id=job.id,
        event_type=event_type,
        safe_data=safe_data or {},
    )
    session.add(event)
    await session.flush()
    return event


async def enqueue_outbox(
    session: AsyncSession, job: JobModel, *, available_at=None
) -> OutboxMessageModel:
    message = OutboxMessageModel(
        workspace_id=job.workspace_id,
        job_id=job.id,
        topic="jobs.execute.v1",
        queue_class=job.queue_class,
        payload={"jobId": str(job.id)},
        available_at=available_at or job.available_at,
    )
    session.add(message)
    await session.flush()
    return message


async def submit_job(session: AsyncSession, submission: JobSubmission) -> tuple[JobModel, bool]:
    if not 1 <= submission.max_attempts <= 20:
        raise StableAPIError(422, "JOB_RETRY_POLICY_INVALID", "maxAttempts must be between 1 and 20")
    if not submission.operation or len(submission.operation) > 96:
        raise StableAPIError(422, "JOB_OPERATION_INVALID", "Job operation is invalid")
    if not submission.idempotency_key or len(submission.idempotency_key) > 128:
        raise StableAPIError(422, "IDEMPOTENCY_KEY_INVALID", "Idempotency key is invalid")
    if not submission.idempotency_scope or len(submission.idempotency_scope) > 192:
        raise StableAPIError(422, "IDEMPOTENCY_SCOPE_INVALID", "Idempotency scope is invalid")

    payload = bounded_json(submission.payload, maximum=MAX_JOB_PAYLOAD_BYTES, label="Job payload")
    assert_secret_free_payload(payload)
    request_hash = hashlib.sha256(
        canonical_json(
            {
                "operation": submission.operation,
                "queueClass": submission.queue_class.value,
                "payloadSchemaVersion": submission.payload_schema_version,
                "resourceType": submission.resource_type,
                "resourceId": submission.resource_id,
                "sourceRevision": submission.source_revision,
                "payload": payload,
            }
        )
    ).hexdigest()

    existing = await session.scalar(
        select(JobModel).where(
            JobModel.workspace_id == submission.workspace_id,
            JobModel.idempotency_scope == submission.idempotency_scope,
            JobModel.idempotency_key == submission.idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise StableAPIError(
                409,
                "IDEMPOTENCY_KEY_CONFLICT",
                "The idempotency key was already used for a different request",
            )
        return existing, True

    job = JobModel(
        workspace_id=submission.workspace_id,
        owner_id=submission.actor_id,
        actor_id=submission.actor_id,
        actor_service_account_id=submission.actor_service_account_id,
        operation=submission.operation,
        queue_class=submission.queue_class,
        status=JobStatus.PENDING,
        payload=payload,
        payload_schema_version=submission.payload_schema_version,
        request_hash=request_hash,
        idempotency_scope=submission.idempotency_scope,
        idempotency_key=submission.idempotency_key,
        max_attempts=submission.max_attempts,
        resource_type=submission.resource_type,
        resource_id=submission.resource_id,
        source_revision=submission.source_revision,
        trace_id=submission.trace_id,
    )
    session.add(job)
    await session.flush()
    await enqueue_outbox(session, job)
    await append_job_event(session, job, "submitted", {"status": job.status.value})
    return job, False

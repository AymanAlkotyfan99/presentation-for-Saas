"""Lease-safe durable worker runtime."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
from dataclasses import dataclass
from datetime import timedelta, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_service_account_id,
    reset_current_job_id,
    reset_current_workspace_id,
    set_current_owner_id,
    set_current_service_account_id,
    set_current_job_id,
    set_current_workspace_id,
)
from modules.jobs.application.submit import (
    MAX_JOB_RESULT_BYTES,
    append_job_event,
    bounded_json,
    enqueue_outbox,
)
from modules.jobs.domain.models import JobStatus, RetryClass, assert_transition, retryable
from modules.jobs.outbox import QueueDelivery, QueueTransport
from modules.jobs.persistence.models import (
    ConsumerInboxModel,
    DeadLetterModel,
    JobAttemptModel,
    JobModel,
)
from modules.jobs.workers.registry import JOB_REGISTRY, JobRegistry
from modules.workspaces.domain.models import MembershipStatus
from modules.workspaces.domain.policies import permissions_for_role
from modules.workspaces.persistence.models import (
    ApiCredentialModel,
    ApiCredentialScopeModel,
    MembershipModel,
    ServiceAccountModel,
    WorkspaceModel,
)
from utils.datetime_utils import get_current_utc_datetime


LOGGER = logging.getLogger(__name__)


def _utc(value):
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class JobHandlerError(RuntimeError):
    def __init__(self, classification: RetryClass, code: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification
        self.code = code
        self.safe_message = message[:512]


class JobCancelled(JobHandlerError):
    def __init__(self) -> None:
        super().__init__(RetryClass.CANCELLED, "JOB_CANCELLED", "Job was cancelled")


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    workspace_id: UUID
    lease_token: UUID
    attempt_number: int


class JobExecutionContext:
    def __init__(self, worker: "JobWorker", claim: ClaimedJob) -> None:
        self.worker = worker
        self.claim = claim

    async def heartbeat(self, progress: int | None = None, message: str | None = None) -> None:
        await self.worker.heartbeat(self.claim, progress=progress, message=message)

    async def checkpoint(self) -> None:
        async with self.worker.session_factory() as session:
            job = await session.get(JobModel, self.claim.job_id)
            if job is None or job.cancellation_requested_at is not None:
                raise JobCancelled()


class JobWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        transport: QueueTransport,
        *,
        registry: JobRegistry = JOB_REGISTRY,
        worker_id: str | None = None,
        lease_seconds: int = 60,
    ) -> None:
        self.session_factory = session_factory
        self.transport = transport
        self.registry = registry
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        self.lease_seconds = max(10, min(lease_seconds, 3600))
        self.consumer_id = "jobs.execute.v1"

    async def _authority_is_current(self, session: AsyncSession, job: JobModel) -> bool:
        workspace = await session.get(WorkspaceModel, job.workspace_id)
        if workspace is None:
            return False
        definition = self.registry.get(job.operation)
        required = definition.required_permissions if definition is not None else ()
        if job.actor_service_account_id is not None:
            account = await session.get(ServiceAccountModel, job.actor_service_account_id)
            if not (account and account.workspace_id == job.workspace_id and account.is_active):
                return False
            if not required:
                return True
            now = get_current_utc_datetime()
            active_scopes = set(
                (
                    await session.scalars(
                        select(ApiCredentialScopeModel.scope)
                        .join(
                            ApiCredentialModel,
                            ApiCredentialModel.id == ApiCredentialScopeModel.credential_id,
                        )
                        .where(
                            ApiCredentialModel.workspace_id == job.workspace_id,
                            ApiCredentialModel.service_account_id == account.id,
                            ApiCredentialModel.revoked_at.is_(None),
                            or_(
                                ApiCredentialModel.expires_at.is_(None),
                                ApiCredentialModel.expires_at > now,
                            ),
                        )
                        .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
                    )
                ).all()
            )
            return all(permission.value in active_scopes for permission in required)
        if job.actor_id is None:
            return False
        membership = await session.scalar(
            select(MembershipModel)
            .where(
                MembershipModel.workspace_id == job.workspace_id,
                MembershipModel.user_id == job.actor_id,
                MembershipModel.status == MembershipStatus.ACTIVE,
            )
            .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
        )
        if membership is None:
            return False
        granted = permissions_for_role(membership.role, membership.permission_overrides)
        return all(permission in granted for permission in required)

    async def _inbox(self, session: AsyncSession, delivery: QueueDelivery, workspace_id: UUID) -> ConsumerInboxModel:
        existing = await session.scalar(
            select(ConsumerInboxModel).where(
                ConsumerInboxModel.consumer_id == self.consumer_id,
                ConsumerInboxModel.message_id == delivery.message_id,
            )
        )
        if existing is not None:
            return existing
        receipt = ConsumerInboxModel(
            workspace_id=workspace_id,
            job_id=delivery.job_id,
            consumer_id=self.consumer_id,
            message_id=delivery.message_id,
        )
        session.add(receipt)
        await session.flush()
        return receipt

    async def claim(self, delivery: QueueDelivery) -> ClaimedJob | None:
        now = get_current_utc_datetime()
        lease_until = now + timedelta(seconds=self.lease_seconds)
        async with self.session_factory() as session:
            job = await session.scalar(
                select(JobModel)
                .where(JobModel.id == delivery.job_id)
                .with_for_update()
                .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            if job is None or job.queue_class != delivery.queue_class:
                return None
            receipt = await self._inbox(session, delivery, job.workspace_id)
            if receipt.processed_at is not None:
                await session.commit()
                return None
            if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}:
                receipt.processed_at = now
                await session.commit()
                return None
            if job.cancellation_requested_at is not None and job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
                assert_transition(job.status, JobStatus.CANCELLED)
                job.status = JobStatus.CANCELLED
                job.finished_at = now
                receipt.processed_at = now
                await append_job_event(session, job, "cancelled", {"phase": "before_execution"})
                await session.commit()
                return None
            active_lease = (
                job.status in {JobStatus.RUNNING, JobStatus.CANCELLATION_REQUESTED}
                and job.lease_until is not None
                and _utc(job.lease_until) > now
            )
            if active_lease:
                await session.commit()
                return None
            if job.status == JobStatus.PENDING:
                assert_transition(job.status, JobStatus.QUEUED)
                job.status = JobStatus.QUEUED
            if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                if job.status == JobStatus.QUEUED:
                    assert_transition(job.status, JobStatus.RUNNING)
                    job.status = JobStatus.RUNNING
            elif job.status == JobStatus.CANCELLATION_REQUESTED:
                job.status = JobStatus.CANCELLED
                job.finished_at = now
                receipt.processed_at = now
                await append_job_event(session, job, "cancelled", {"phase": "expired_lease"})
                await session.commit()
                return None
            else:
                return None

            if not await self._authority_is_current(session, job):
                job.status = JobStatus.FAILED
                job.finished_at = now
                job.safe_error_code = "WORKER_AUTHORIZATION_REVOKED"
                job.safe_error_message = "Job authority is no longer valid"
                receipt.processed_at = now
                await append_job_event(session, job, "failed", {"errorCode": job.safe_error_code})
                await session.commit()
                return None

            job.attempt_count += 1
            job.lease_owner = self.worker_id
            job.lease_token = uuid4()
            job.lease_until = lease_until
            job.heartbeat_at = now
            job.started_at = job.started_at or now
            attempt = JobAttemptModel(
                job_id=job.id,
                workspace_id=job.workspace_id,
                attempt_number=job.attempt_count,
                worker_id=self.worker_id,
                lease_token=job.lease_token,
                lease_until=lease_until,
            )
            session.add(attempt)
            await append_job_event(
                session,
                job,
                "started" if job.attempt_count == 1 else "retry_started",
                {"attempt": job.attempt_count},
            )
            await session.commit()
            return ClaimedJob(job.id, job.workspace_id, job.lease_token, job.attempt_count)

    async def heartbeat(self, claim: ClaimedJob, *, progress: int | None = None, message: str | None = None) -> bool:
        now = get_current_utc_datetime()
        async with self.session_factory() as session:
            job = await session.scalar(
                select(JobModel).where(JobModel.id == claim.job_id).with_for_update().execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            if job is None or job.lease_owner != self.worker_id or job.lease_token != claim.lease_token or job.attempt_count != claim.attempt_number:
                return False
            if job.status not in {JobStatus.RUNNING, JobStatus.CANCELLATION_REQUESTED}:
                return False
            job.heartbeat_at = now
            job.lease_until = now + timedelta(seconds=self.lease_seconds)
            if progress is not None:
                job.progress = max(job.progress, min(100, max(0, progress)))
            if message is not None:
                job.progress_message = message[:256]
            attempt = await session.scalar(
                select(JobAttemptModel).where(
                    JobAttemptModel.job_id == claim.job_id,
                    JobAttemptModel.attempt_number == claim.attempt_number,
                )
            )
            if attempt:
                attempt.heartbeat_at = now
                attempt.lease_until = job.lease_until
            await append_job_event(session, job, "progress", {"progress": job.progress})
            await session.commit()
            return True

    @staticmethod
    def retry_delay_seconds(job_id: UUID, attempt_number: int) -> int:
        base = min(900, 2 ** min(attempt_number, 9))
        digest = hashlib.sha256(f"{job_id}:{attempt_number}".encode()).digest()
        jitter = int.from_bytes(digest[:2], "big") % max(1, base // 2 + 1)
        return min(900, base + jitter)

    async def _finish(
        self,
        claim: ClaimedJob,
        *,
        result: dict | None = None,
        error: JobHandlerError | None = None,
        message_id: UUID,
    ) -> bool:
        now = get_current_utc_datetime()
        async with self.session_factory() as session:
            job = await session.scalar(
                select(JobModel).where(JobModel.id == claim.job_id).with_for_update().execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            if job is None or job.lease_owner != self.worker_id or job.lease_token != claim.lease_token or job.attempt_count != claim.attempt_number:
                return False
            receipt = await session.scalar(
                select(ConsumerInboxModel).where(
                    ConsumerInboxModel.consumer_id == self.consumer_id,
                    ConsumerInboxModel.message_id == message_id,
                )
            )
            attempt = await session.scalar(
                select(JobAttemptModel).where(
                    JobAttemptModel.job_id == claim.job_id,
                    JobAttemptModel.attempt_number == claim.attempt_number,
                )
            )
            if attempt:
                attempt.finished_at = now
            if job.cancellation_requested_at is not None or isinstance(error, JobCancelled):
                if job.status == JobStatus.RUNNING:
                    assert_transition(job.status, JobStatus.CANCELLED)
                elif job.status == JobStatus.CANCELLATION_REQUESTED:
                    assert_transition(job.status, JobStatus.CANCELLED)
                job.status = JobStatus.CANCELLED
                job.finished_at = now
                if attempt:
                    attempt.retry_class = RetryClass.CANCELLED
                await append_job_event(session, job, "cancelled", {"phase": "checkpoint"})
            elif error is None:
                assert_transition(job.status, JobStatus.SUCCEEDED)
                job.status = JobStatus.SUCCEEDED
                job.progress = 100
                job.result = bounded_json(result or {}, maximum=MAX_JOB_RESULT_BYTES, label="Job result")
                job.finished_at = now
                await append_job_event(session, job, "succeeded", {"progress": 100})
            else:
                if attempt:
                    attempt.retry_class = error.classification
                    attempt.safe_error_code = error.code
                    attempt.safe_error_message = error.safe_message
                job.safe_error_code = error.code
                job.safe_error_message = error.safe_message
                if retryable(error.classification) and job.attempt_count < job.max_attempts:
                    assert_transition(job.status, JobStatus.QUEUED)
                    job.status = JobStatus.QUEUED
                    delay = self.retry_delay_seconds(job.id, job.attempt_count)
                    job.available_at = now + timedelta(seconds=delay)
                    await enqueue_outbox(session, job, available_at=job.available_at)
                    await append_job_event(
                        session, job, "retry_scheduled",
                        {"attempt": job.attempt_count, "delaySeconds": delay, "errorCode": error.code},
                    )
                else:
                    target = JobStatus.DEAD_LETTER if retryable(error.classification) or error.code == "UNKNOWN_JOB_OPERATION" else JobStatus.FAILED
                    assert_transition(job.status, target)
                    job.status = target
                    job.finished_at = now
                    if target == JobStatus.DEAD_LETTER:
                        session.add(
                            DeadLetterModel(
                                workspace_id=job.workspace_id,
                                job_id=job.id,
                                operation=job.operation,
                                attempt_number=job.attempt_count,
                                safe_error_code=error.code,
                                safe_error_message=error.safe_message,
                                retry_class=error.classification,
                            )
                        )
                    await append_job_event(session, job, target.value.lower(), {"errorCode": error.code})
            job.lease_owner = None
            job.lease_token = None
            job.lease_until = None
            if receipt:
                receipt.processed_at = now
            await session.commit()
            return True

    async def process_delivery(self, delivery: QueueDelivery) -> bool:
        claim = await self.claim(delivery)
        if claim is None:
            return False
        async with self.session_factory() as session:
            job = await session.scalar(
                select(JobModel).where(JobModel.id == claim.job_id).execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            if job is None:
                return False
            definition = self.registry.get(job.operation)
            if definition is None or definition.queue_class != job.queue_class:
                await self._finish(
                    claim,
                    error=JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "UNKNOWN_JOB_OPERATION", "The job operation is not registered"),
                    message_id=delivery.message_id,
                )
                return False
            try:
                payload = definition.payload_model.model_validate(job.payload)
            except ValidationError:
                await self._finish(
                    claim,
                    error=JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "JOB_PAYLOAD_INVALID", "The durable job payload is invalid"),
                    message_id=delivery.message_id,
                )
                return False
            owner_token = set_current_owner_id(job.actor_id)
            workspace_token = set_current_workspace_id(job.workspace_id)
            service_token = set_current_service_account_id(job.actor_service_account_id)
            job_token = set_current_job_id(job.id)
        heartbeat_stop = asyncio.Event()

        async def automatic_heartbeat() -> None:
            interval = max(3, self.lease_seconds // 3)
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.wait_for(heartbeat_stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    if not await self.heartbeat(claim):
                        return

        heartbeat_task = asyncio.create_task(automatic_heartbeat())
        try:
            context = JobExecutionContext(self, claim)
            await context.checkpoint()
            result = await definition.handler(context, payload)
            await self._finish(claim, result=result, message_id=delivery.message_id)
            return True
        except JobHandlerError as exc:
            await self._finish(claim, error=exc, message_id=delivery.message_id)
            return False
        except asyncio.TimeoutError:
            await self._finish(
                claim,
                error=JobHandlerError(RetryClass.PROVIDER_TIMEOUT, "DEPENDENCY_TIMEOUT", "A dependency timed out"),
                message_id=delivery.message_id,
            )
            return False
        except Exception:
            LOGGER.exception("[jobs.worker] handler failed job_id=%s operation=%s", claim.job_id, job.operation)
            await self._finish(
                claim,
                error=JobHandlerError(RetryClass.UNKNOWN, "JOB_EXECUTION_FAILED", "Job execution failed"),
                message_id=delivery.message_id,
            )
            return False
        finally:
            heartbeat_stop.set()
            await asyncio.gather(heartbeat_task, return_exceptions=True)
            reset_current_service_account_id(service_token)
            reset_current_job_id(job_token)
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)

    async def _delivery_acknowledgeable(self, delivery: QueueDelivery) -> bool:
        """Ack only poison/terminal/transactionally processed deliveries.

        An unprocessed inbox receipt paired with a live or expired job lease is
        deliberately left pending in Redis. That is the worker-crash recovery
        path: Streams can reclaim it after the visibility interval, while SQL
        decides whether the lease is still authoritative.
        """
        async with self.session_factory() as session:
            receipt = await session.scalar(
                select(ConsumerInboxModel)
                .where(
                    ConsumerInboxModel.consumer_id == self.consumer_id,
                    ConsumerInboxModel.message_id == delivery.message_id,
                )
                .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            if receipt is not None and receipt.processed_at is not None:
                return True
            job = await session.scalar(
                select(JobModel)
                .where(JobModel.id == delivery.job_id)
                .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
            )
            return bool(
                job is None
                or job.queue_class != delivery.queue_class
                or job.status
                in {
                    JobStatus.SUCCEEDED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                    JobStatus.DEAD_LETTER,
                }
            )

    async def handle_delivery(self, delivery: QueueDelivery) -> bool:
        processed = await self.process_delivery(delivery)
        if await self._delivery_acknowledgeable(delivery):
            acknowledge = getattr(self.transport, "ack", None)
            if acknowledge is not None:
                await acknowledge(delivery)
        return processed

    async def run_queue(self, queue_class, *, stop_event) -> None:
        while not stop_event.is_set():
            try:
                delivery = await self.transport.consume(queue_class, timeout=5)
                if delivery is not None:
                    await self.handle_delivery(delivery)
            except Exception:
                LOGGER.exception("[jobs.worker] queue receive failed queue=%s", queue_class.value)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

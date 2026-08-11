"""Real PostgreSQL/Redis durable-job integration coverage.

These tests intentionally skip unless disposable integration endpoints are
provided; they never fall back to SQLite or an in-memory broker while claiming
to validate database locks or Redis delivery.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

from models.sql.user import User
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import JobStatus, QueueClass, RetryClass
from modules.jobs.outbox import QueueDelivery, RedisQueueTransport, dispatch_outbox_batch
from modules.jobs.persistence.models import ConsumerInboxModel, DeadLetterModel, JobAttemptModel, JobModel, OutboxMessageModel
from modules.jobs.workers.registry import JobRegistry, OperationDefinition
from modules.jobs.workers.runtime import JobHandlerError, JobWorker
from modules.workspaces.domain.models import MembershipStatus, Permission, Role
from modules.workspaces.persistence.models import (
    ApiCredentialModel,
    ApiCredentialScopeModel,
    MembershipModel,
    ServiceAccountModel,
    WorkspaceModel,
)
from utils.datetime_utils import get_current_utc_datetime


class NoopTransport:
    async def publish(self, _delivery): return None
    async def consume(self, _queue_class, timeout=5): return None
    async def health(self): return True
    async def close(self): return None


def _run(coro):
    if sys.platform != "win32":
        return asyncio.run(coro)
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _postgres_url() -> str:
    url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL")
    return url


def _redis_url() -> str:
    url = os.getenv("JOB_TEST_REDIS_URL", "")
    if not url.startswith(("redis://", "rediss://")):
        pytest.skip("JOB_TEST_REDIS_URL does not identify disposable Redis")
    return url


class EchoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


async def _identity(sessions, label: str):
    suffix = uuid4()
    async with sessions() as session:
        user = User(username=f"{label}-{suffix}", hashed_password="test")
        session.add(user)
        await session.flush()
        workspace = WorkspaceModel(name=f"{label} {suffix}", created_by=user.id)
        session.add(workspace)
        await session.flush()
        membership = MembershipModel(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        session.add(membership)
        await session.commit()
        return user.id, workspace.id


def _submission(workspace_id, user_id, *, key: str, operation: str, max_attempts: int = 3):
    return JobSubmission(
        operation=operation,
        queue_class=QueueClass.MAINTENANCE,
        workspace_id=workspace_id,
        actor_id=user_id,
        actor_service_account_id=None,
        idempotency_scope=f"real-infrastructure:{operation}",
        idempotency_key=key,
        payload={"value": key},
        max_attempts=max_attempts,
    )


def test_postgresql_lock_allows_one_active_claim():
    async def scenario():
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        suffix = uuid4()
        async with sessions() as session:
            user = User(username=f"job-pg-{suffix}", hashed_password="test")
            session.add(user)
            await session.flush()
            workspace = WorkspaceModel(name=f"Job PG {suffix}", created_by=user.id)
            session.add(workspace)
            await session.flush()
            session.add(MembershipModel(workspace_id=workspace.id, user_id=user.id, role=Role.OWNER, status=MembershipStatus.ACTIVE))
            job, _ = await submit_job(
                session,
                JobSubmission(
                    operation="integration.noop", queue_class=QueueClass.MAINTENANCE,
                    workspace_id=workspace.id, actor_id=user.id, actor_service_account_id=None,
                    idempotency_scope=f"pg:{suffix}", idempotency_key="one", payload={},
                ),
            )
            await session.commit()
        transport = NoopTransport()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        delivery = QueueDelivery(message_id=uuid4(), job_id=job.id, queue_class=QueueClass.MAINTENANCE)
        workers = [
            JobWorker(sessions, transport, worker_id="pg-worker-a", lease_seconds=30),
            JobWorker(sessions, transport, worker_id="pg-worker-b", lease_seconds=30),
        ]
        claims = await asyncio.gather(*(worker.claim(delivery) for worker in workers))
        assert sum(claim is not None for claim in claims) == 1
        await engine.dispose()

    _run(scenario())


def test_real_redis_queue_contract_and_redelivery():
    async def scenario():
        url = os.getenv("JOB_TEST_REDIS_URL", "")
        if not url.startswith(("redis://", "rediss://")):
            pytest.skip("JOB_TEST_REDIS_URL does not identify disposable Redis")
        from redis.asyncio import Redis

        namespace = f"bayanly:test:{uuid4().hex}"
        client = Redis.from_url(url, encoding="utf-8", decode_responses=True)
        transport = RedisQueueTransport(client, namespace, visibility_seconds=1)
        delivery = QueueDelivery(uuid4(), uuid4(), QueueClass.EXPORT)
        try:
            assert await transport.health()
            await transport.publish(delivery)
            received = await transport.consume(QueueClass.EXPORT, timeout=1)
            assert received is not None
            assert (received.message_id, received.job_id, received.queue_class) == (
                delivery.message_id, delivery.job_id, delivery.queue_class,
            )
            # An unacknowledged delivery is reclaimed after visibility expiry.
            await asyncio.sleep(1.05)
            reclaimed = await transport.consume(QueueClass.EXPORT, timeout=1)
            assert reclaimed is not None
            assert reclaimed.message_id == delivery.message_id
            await transport.ack(reclaimed)
            await transport.publish(delivery)
            received_again = await transport.consume(QueueClass.EXPORT, timeout=1)
            assert received_again is not None and received_again.message_id == delivery.message_id
            await transport.ack(received_again)
        finally:
            await client.delete(transport.queue_name(QueueClass.EXPORT))
            await transport.close()

    _run(scenario())


def test_real_postgresql_redis_worker_crash_recovery_is_exactly_once():
    async def scenario():
        from redis.asyncio import Redis

        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions, "job-crash")
        namespace = f"bayanly:test:{uuid4().hex}"
        first_transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
            consumer_name="crashed-worker",
        )
        replacement_transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
            consumer_name="replacement-worker",
        )
        effects: list[str] = []

        async def echo(_context, payload):
            effects.append(payload.value)
            return {"echo": payload.value}

        registry = JobRegistry()
        registry.register(
            OperationDefinition(
                "integration.crash",
                QueueClass.MAINTENANCE,
                EchoPayload,
                echo,
            )
        )
        try:
            async with sessions() as session:
                job, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=uuid4().hex,
                        operation="integration.crash",
                    ),
                )
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, first_transport) == 1
            delivery = await first_transport.consume(QueueClass.MAINTENANCE, timeout=1)
            assert delivery is not None
            crashed_worker = JobWorker(
                sessions,
                first_transport,
                registry=registry,
                worker_id="crashed-worker",
                lease_seconds=10,
            )
            stale_claim = await crashed_worker.claim(delivery)
            assert stale_claim is not None
            # Closing the connection before execution/ACK models an abrupt
            # process exit after the SQL lease was committed.
            await first_transport.close()
            async with sessions() as session:
                current = await session.get(JobModel, job.id)
                assert current is not None and current.status == JobStatus.RUNNING
                current.lease_until = get_current_utc_datetime() - timedelta(seconds=1)
                await session.commit()
            await asyncio.sleep(1.05)
            reclaimed = await replacement_transport.consume(
                QueueClass.MAINTENANCE,
                timeout=1,
            )
            assert reclaimed is not None
            assert reclaimed.message_id == delivery.message_id
            replacement_worker = JobWorker(
                sessions,
                replacement_transport,
                registry=registry,
                worker_id="replacement-worker",
                lease_seconds=10,
            )
            assert await replacement_worker.handle_delivery(reclaimed)
            assert not await crashed_worker._finish(
                stale_claim,
                result={"wrong": True},
                message_id=delivery.message_id,
            )
            assert effects == [job.idempotency_key]
            async with sessions() as session:
                current = await session.get(JobModel, job.id)
                attempts = list(
                    (
                        await session.scalars(
                            select(JobAttemptModel)
                            .where(JobAttemptModel.job_id == job.id)
                            .order_by(JobAttemptModel.attempt_number)
                        )
                    ).all()
                )
                receipt = await session.scalar(
                    select(ConsumerInboxModel).where(
                        ConsumerInboxModel.message_id == delivery.message_id
                    )
                )
                assert current is not None and current.status == JobStatus.SUCCEEDED
                assert current.result == {"echo": job.idempotency_key}
                assert [attempt.worker_id for attempt in attempts] == [
                    "crashed-worker",
                    "replacement-worker",
                ]
                assert receipt is not None and receipt.processed_at is not None
            pending = await replacement_transport.client.xpending(
                replacement_transport.queue_name(QueueClass.MAINTENANCE),
                replacement_transport.group_name,
            )
            assert pending["pending"] == 0
        finally:
            try:
                await replacement_transport.client.delete(
                    replacement_transport.queue_name(QueueClass.MAINTENANCE)
                )
            finally:
                await replacement_transport.close()
                await engine.dispose()

    _run(scenario())


def test_real_postgresql_redis_authority_cancellation_and_finite_retry():
    async def scenario():
        from redis.asyncio import Redis

        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions, "job-policy")
        namespace = f"bayanly:test:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        registry = JobRegistry()

        async def echo(_context, payload):
            return {"echo": payload.value}

        async def unavailable(_context, _payload):
            raise JobHandlerError(
                RetryClass.DEPENDENCY_UNAVAILABLE,
                "TEST_DEPENDENCY_DOWN",
                "Controlled dependency outage",
            )

        registry.register(
            OperationDefinition(
                "integration.authorized",
                QueueClass.MAINTENANCE,
                EchoPayload,
                echo,
                required_permissions=(Permission.PRESENTATIONS_WRITE,),
            )
        )
        registry.register(
            OperationDefinition(
                "integration.retry",
                QueueClass.MAINTENANCE,
                EchoPayload,
                unavailable,
            )
        )
        worker = JobWorker(
            sessions,
            transport,
            registry=registry,
            worker_id="policy-worker",
            lease_seconds=10,
        )
        try:
            async with sessions() as session:
                revoked, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"revoked-{uuid4().hex}",
                        operation="integration.authorized",
                    ),
                )
                cancelled, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"cancelled-{uuid4().hex}",
                        operation="integration.authorized",
                    ),
                )
                cancelled.cancellation_requested_at = get_current_utc_datetime()
                retrying, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"retry-{uuid4().hex}",
                        operation="integration.retry",
                        max_attempts=2,
                    ),
                )
                await session.commit()
            async with sessions() as session:
                membership = await session.scalar(
                    select(MembershipModel).where(
                        MembershipModel.workspace_id == workspace_id,
                        MembershipModel.user_id == user_id,
                    )
                )
                assert membership is not None
                membership.role = Role.VIEWER
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 3
            deliveries = []
            for _ in range(3):
                delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=1)
                assert delivery is not None
                deliveries.append(delivery)
                await worker.handle_delivery(delivery)
            async with sessions() as session:
                revoked_row = await session.get(JobModel, revoked.id)
                cancelled_row = await session.get(JobModel, cancelled.id)
                retry_row = await session.get(JobModel, retrying.id)
                assert revoked_row is not None
                assert revoked_row.status == JobStatus.FAILED
                assert revoked_row.safe_error_code == "WORKER_AUTHORIZATION_REVOKED"
                assert cancelled_row is not None
                assert cancelled_row.status == JobStatus.CANCELLED
                assert retry_row is not None and retry_row.status == JobStatus.QUEUED
                pending_retry = await session.scalar(
                    select(OutboxMessageModel).where(
                        OutboxMessageModel.job_id == retrying.id,
                        OutboxMessageModel.published_at.is_(None),
                    )
                )
                assert pending_retry is not None
                pending_retry.available_at = get_current_utc_datetime()
                retry_row.available_at = get_current_utc_datetime()
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            retry_delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=1)
            assert retry_delivery is not None
            await worker.handle_delivery(retry_delivery)
            async with sessions() as session:
                retry_row = await session.get(JobModel, retrying.id)
                dead = await session.scalar(
                    select(DeadLetterModel).where(DeadLetterModel.job_id == retrying.id)
                )
                assert retry_row is not None
                assert retry_row.status == JobStatus.DEAD_LETTER
                assert retry_row.attempt_count == 2
                assert dead is not None
                assert dead.safe_error_code == "TEST_DEPENDENCY_DOWN"
        finally:
            try:
                await transport.client.delete(
                    transport.queue_name(QueueClass.MAINTENANCE)
                )
            finally:
                await transport.close()
                await engine.dispose()

    _run(scenario())


def test_real_postgresql_redis_running_cancel_nonretryable_and_timeout():
    async def scenario():
        from redis.asyncio import Redis

        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions, "job-terminal")
        namespace = f"bayanly:test:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        started = asyncio.Event()
        release = asyncio.Event()

        async def cancellable(context, payload):
            started.set()
            await release.wait()
            await context.checkpoint()
            return {"echo": payload.value}

        async def invalid(_context, _payload):
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_VALIDATION,
                "CONTROLLED_INVALID",
                "Controlled validation failure",
            )

        async def timed_out(_context, _payload):
            raise asyncio.TimeoutError

        registry = JobRegistry()
        for operation, handler in (
            ("integration.running-cancel", cancellable),
            ("integration.nonretryable", invalid),
            ("integration.timeout", timed_out),
        ):
            registry.register(
                OperationDefinition(
                    operation,
                    QueueClass.MAINTENANCE,
                    EchoPayload,
                    handler,
                )
            )
        worker = JobWorker(
            sessions,
            transport,
            registry=registry,
            worker_id="terminal-worker",
            lease_seconds=10,
        )
        try:
            async with sessions() as session:
                running, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"running-{uuid4().hex}",
                        operation="integration.running-cancel",
                    ),
                )
                nonretryable, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"invalid-{uuid4().hex}",
                        operation="integration.nonretryable",
                        max_attempts=3,
                    ),
                )
                timeout_job, _ = await submit_job(
                    session,
                    _submission(
                        workspace_id,
                        user_id,
                        key=f"timeout-{uuid4().hex}",
                        operation="integration.timeout",
                        max_attempts=1,
                    ),
                )
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 3
            deliveries = {}
            for _ in range(3):
                delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=1)
                assert delivery is not None
                deliveries[delivery.job_id] = delivery

            running_task = asyncio.create_task(
                worker.handle_delivery(deliveries[running.id])
            )
            await asyncio.wait_for(started.wait(), timeout=2)
            async with sessions() as session:
                current = await session.scalar(
                    select(JobModel)
                    .where(JobModel.id == running.id)
                    .with_for_update()
                )
                assert current is not None and current.status == JobStatus.RUNNING
                current.status = JobStatus.CANCELLATION_REQUESTED
                current.cancellation_requested_at = get_current_utc_datetime()
                await session.commit()
            release.set()
            assert not await running_task
            assert not await worker.handle_delivery(deliveries[nonretryable.id])
            assert not await worker.handle_delivery(deliveries[timeout_job.id])
            async with sessions() as session:
                running_row = await session.get(JobModel, running.id)
                invalid_row = await session.get(JobModel, nonretryable.id)
                timeout_row = await session.get(JobModel, timeout_job.id)
                timeout_dead = await session.scalar(
                    select(DeadLetterModel).where(
                        DeadLetterModel.job_id == timeout_job.id
                    )
                )
                assert running_row is not None
                assert running_row.status == JobStatus.CANCELLED
                assert invalid_row is not None
                assert invalid_row.status == JobStatus.FAILED
                assert invalid_row.attempt_count == 1
                assert invalid_row.safe_error_code == "CONTROLLED_INVALID"
                assert timeout_row is not None
                assert timeout_row.status == JobStatus.DEAD_LETTER
                assert timeout_row.attempt_count == 1
                assert timeout_dead is not None
                assert timeout_dead.safe_error_code == "DEPENDENCY_TIMEOUT"
        finally:
            await transport.client.delete(
                transport.queue_name(QueueClass.MAINTENANCE)
            )
            await transport.close()
            await engine.dispose()

    _run(scenario())


def test_real_postgresql_redis_revalidates_revoked_service_scope():
    async def scenario():
        from redis.asyncio import Redis

        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions, "job-service")
        namespace = f"bayanly:test:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        registry = JobRegistry()

        async def echo(_context, payload):
            return {"echo": payload.value}

        registry.register(
            OperationDefinition(
                "integration.service-scope",
                QueueClass.MAINTENANCE,
                EchoPayload,
                echo,
                required_permissions=(Permission.PRESENTATIONS_WRITE,),
            )
        )
        try:
            async with sessions() as session:
                account = ServiceAccountModel(
                    workspace_id=workspace_id,
                    name=f"Job Service {uuid4().hex}",
                    created_by=user_id,
                )
                session.add(account)
                await session.flush()
                credential = ApiCredentialModel(
                    workspace_id=workspace_id,
                    service_account_id=account.id,
                    key_prefix=f"bws_{uuid4().hex}",
                    secret_digest="a" * 64,
                    created_by=user_id,
                )
                session.add(credential)
                await session.flush()
                session.add(
                    ApiCredentialScopeModel(
                        credential_id=credential.id,
                        scope=Permission.PRESENTATIONS_WRITE.value,
                    )
                )
                job, _ = await submit_job(
                    session,
                    JobSubmission(
                        operation="integration.service-scope",
                        queue_class=QueueClass.MAINTENANCE,
                        workspace_id=workspace_id,
                        actor_id=None,
                        actor_service_account_id=account.id,
                        idempotency_scope="integration.service-scope",
                        idempotency_key=uuid4().hex,
                        payload={"value": "scope"},
                    ),
                )
                await session.commit()
                credential.revoked_at = get_current_utc_datetime()
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=1)
            assert delivery is not None
            worker = JobWorker(
                sessions,
                transport,
                registry=registry,
                worker_id="service-scope-worker",
            )
            assert not await worker.handle_delivery(delivery)
            async with sessions() as session:
                current = await session.get(JobModel, job.id)
                assert current is not None and current.status == JobStatus.FAILED
                assert current.safe_error_code == "WORKER_AUTHORIZATION_REVOKED"
        finally:
            await transport.client.delete(
                transport.queue_name(QueueClass.MAINTENANCE)
            )
            await transport.close()
            await engine.dispose()

    _run(scenario())

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from models.sql.user import User
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import JobStatus, QueueClass, RetryClass, assert_transition
from modules.jobs.outbox import QueueDelivery, dispatch_outbox_batch
from modules.jobs.persistence.models import (
    ConsumerInboxModel,
    DeadLetterModel,
    JobAttemptModel,
    JobEventModel,
    JobModel,
    OutboxMessageModel,
)
from modules.jobs.workers.registry import JobRegistry, OperationDefinition
from modules.jobs.workers.runtime import JobHandlerError, JobWorker
from modules.workspaces.domain.models import MembershipStatus, Permission, Role
from modules.workspaces.persistence.models import MembershipModel, ServiceAccountModel, WorkspaceModel
from utils.api_errors import StableAPIError
from utils.architecture_flags import (
    durable_exports_enabled,
    durable_generation_enabled,
    durable_webhooks_enabled,
)
from utils.datetime_utils import get_current_utc_datetime


JOB_TABLES = (
    User.__table__,
    WorkspaceModel.__table__,
    MembershipModel.__table__,
    ServiceAccountModel.__table__,
    JobModel.__table__,
    JobAttemptModel.__table__,
    OutboxMessageModel.__table__,
    ConsumerInboxModel.__table__,
    DeadLetterModel.__table__,
    JobEventModel.__table__,
)


def test_operation_flags_cannot_enable_durable_work_without_global_worker(monkeypatch):
    monkeypatch.setenv("DURABLE_GENERATION_ENABLED", "true")
    monkeypatch.setenv("DURABLE_EXPORTS_ENABLED", "true")
    monkeypatch.setenv("DURABLE_WEBHOOKS_ENABLED", "true")
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "false")
    assert not durable_generation_enabled()
    assert not durable_exports_enabled()
    assert not durable_webhooks_enabled()
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "true")
    assert durable_generation_enabled()
    assert durable_exports_enabled()
    assert durable_webhooks_enabled()


class FakeTransport:
    def __init__(self, *, unavailable=False):
        self.unavailable = unavailable
        self.deliveries = []
        self.acked = []

    async def publish(self, delivery):
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        self.deliveries.append(delivery)

    async def consume(self, _queue_class, timeout=5):
        return self.deliveries.pop(0) if self.deliveries else None

    async def ack(self, delivery):
        self.acked.append(delivery)

    async def health(self):
        return not self.unavailable

    async def close(self):
        return None


class EchoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


async def database(tmp_path, name="jobs.db"):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=JOB_TABLES))
    async with sessions() as session:
        user = User(username=f"worker-{name}", hashed_password="not-a-secret-hash")
        session.add(user)
        await session.flush()
        workspace = WorkspaceModel(name="Jobs", created_by=user.id)
        session.add(workspace)
        await session.flush()
        session.add(
            MembershipModel(
                workspace_id=workspace.id,
                user_id=user.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        await session.commit()
    return engine, sessions, user.id, workspace.id


def submission(workspace_id, user_id, *, key="idem-1", operation="test.echo", max_attempts=3, payload=None):
    return JobSubmission(
        operation=operation,
        queue_class=QueueClass.MAINTENANCE,
        workspace_id=workspace_id,
        actor_id=user_id,
        actor_service_account_id=None,
        idempotency_scope="test.echo:actor",
        idempotency_key=key,
        payload=payload or {"value": "hello"},
        max_attempts=max_attempts,
        resource_type="test",
        resource_id="one",
    )


def test_authoritative_state_machine_keeps_terminal_states_stable():
    assert_transition(JobStatus.PENDING, JobStatus.QUEUED)
    assert_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    assert_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
    with pytest.raises(ValueError):
        assert_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
    with pytest.raises(ValueError):
        assert_transition(JobStatus.CANCELLED, JobStatus.RUNNING)
    with pytest.raises(ValueError):
        assert_transition(JobStatus.DEAD_LETTER, JobStatus.RUNNING)


def test_submit_is_atomic_deduplicated_conflict_safe_and_secret_free(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path)
        async with sessions() as session:
            job, duplicate = await submit_job(session, submission(workspace_id, user_id))
            assert not duplicate
            await session.rollback()
        async with sessions() as session:
            assert not list((await session.scalars(select(JobModel))).all())
            assert not list((await session.scalars(select(OutboxMessageModel))).all())
            job, duplicate = await submit_job(session, submission(workspace_id, user_id))
            await session.commit()
            assert not duplicate
            first_id = job.id
        async with sessions() as session:
            same, duplicate = await submit_job(session, submission(workspace_id, user_id))
            assert duplicate and same.id == first_id
            with pytest.raises(StableAPIError) as conflict:
                await submit_job(
                    session,
                    submission(workspace_id, user_id, payload={"value": "changed"}),
                )
            assert conflict.value.code == "IDEMPOTENCY_KEY_CONFLICT"
            with pytest.raises(StableAPIError) as secret:
                await submit_job(
                    session,
                    submission(workspace_id, user_id, key="secret", payload={"api_key": "forbidden"}),
                )
            assert secret.value.code == "JOB_PAYLOAD_CONTAINS_SECRET"
        await engine.dispose()

    asyncio.run(scenario())


def test_redis_outage_keeps_outbox_durable_then_recovers(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, "outbox.db")
        async with sessions() as session:
            job, _ = await submit_job(session, submission(workspace_id, user_id))
            await session.commit()
        unavailable = FakeTransport(unavailable=True)
        async with sessions() as session:
            assert await dispatch_outbox_batch(session, unavailable) == 0
        async with sessions() as session:
            outbox = await session.scalar(select(OutboxMessageModel))
            current = await session.get(JobModel, job.id)
            assert outbox.published_at is None
            assert outbox.publish_attempts == 1
            assert current.status == JobStatus.PENDING
        recovered = FakeTransport()
        async with sessions() as session:
            assert await dispatch_outbox_batch(session, recovered) == 1
        async with sessions() as session:
            outbox = await session.scalar(select(OutboxMessageModel))
            current = await session.get(JobModel, job.id)
            assert outbox.published_at is not None
            assert current.status == JobStatus.QUEUED
            assert len(recovered.deliveries) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_worker_success_redelivery_dedupe_and_restart(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, "worker.db")
        calls = []

        async def echo(context, payload):
            calls.append(payload.value)
            await context.heartbeat(50, "halfway")
            return {"echo": payload.value}

        registry = JobRegistry()
        registry.register(OperationDefinition("test.echo", QueueClass.MAINTENANCE, EchoPayload, echo))
        transport = FakeTransport()
        async with sessions() as session:
            job, _ = await submit_job(session, submission(workspace_id, user_id))
            await session.commit()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        delivery = transport.deliveries[0]
        first_worker = JobWorker(sessions, transport, registry=registry, worker_id="worker-one", lease_seconds=10)
        assert await first_worker.process_delivery(delivery)
        restarted_worker = JobWorker(sessions, transport, registry=registry, worker_id="worker-two", lease_seconds=10)
        assert not await restarted_worker.process_delivery(delivery)
        assert calls == ["hello"]
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            receipts = list((await session.scalars(select(ConsumerInboxModel))).all())
            assert current.status == JobStatus.SUCCEEDED
            assert current.result == {"echo": "hello"}
            assert current.progress == 100
            assert len(receipts) == 1 and receipts[0].processed_at is not None
        await engine.dispose()

    asyncio.run(scenario())


def test_expired_lease_is_stolen_and_stale_worker_cannot_complete(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, "lease.db")
        registry = JobRegistry()

        async def echo(_context, payload):
            return {"echo": payload.value}

        registry.register(OperationDefinition("test.echo", QueueClass.MAINTENANCE, EchoPayload, echo))
        transport = FakeTransport()
        async with sessions() as session:
            job, _ = await submit_job(session, submission(workspace_id, user_id))
            await session.commit()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        delivery = transport.deliveries[0]
        first = JobWorker(sessions, transport, registry=registry, worker_id="stale", lease_seconds=10)
        first_claim = await first.claim(delivery)
        assert first_claim is not None
        second = JobWorker(sessions, transport, registry=registry, worker_id="current", lease_seconds=10)
        assert not await second.handle_delivery(delivery)
        assert transport.acked == []
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            current.lease_until = get_current_utc_datetime() - timedelta(seconds=1)
            await session.commit()
        assert await second.handle_delivery(delivery)
        assert transport.acked == [delivery]
        assert not await first._finish(first_claim, result={"wrong": True}, message_id=delivery.message_id)
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            attempts = list((await session.scalars(select(JobAttemptModel).order_by(JobAttemptModel.attempt_number))).all())
            assert current.status == JobStatus.SUCCEEDED
            assert current.result == {"echo": "hello"}
            assert [attempt.worker_id for attempt in attempts] == ["stale", "current"]
        await engine.dispose()

    asyncio.run(scenario())


def test_worker_revalidates_current_operation_permission(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, "authority.db")

        async def echo(_context, payload):
            return {"echo": payload.value}

        registry = JobRegistry()
        registry.register(
            OperationDefinition(
                "test.echo",
                QueueClass.MAINTENANCE,
                EchoPayload,
                echo,
                required_permissions=(Permission.PRESENTATIONS_WRITE,),
            )
        )
        transport = FakeTransport()
        async with sessions() as session:
            job, _ = await submit_job(session, submission(workspace_id, user_id))
            await session.commit()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
            membership = await session.scalar(
                select(MembershipModel).where(
                    MembershipModel.workspace_id == workspace_id,
                    MembershipModel.user_id == user_id,
                )
            )
            membership.role = Role.VIEWER
            await session.commit()

        delivery = transport.deliveries[0]
        worker = JobWorker(sessions, transport, registry=registry, worker_id="authority", lease_seconds=10)
        assert not await worker.handle_delivery(delivery)
        assert transport.acked == [delivery]
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            assert current.status == JobStatus.FAILED
            assert current.safe_error_code == "WORKER_AUTHORIZATION_REVOKED"
        await engine.dispose()

    asyncio.run(scenario())


def test_cancellation_and_finite_retry_dead_letter(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, "cancel-retry.db")
        transport = FakeTransport()
        registry = JobRegistry()

        async def unavailable(_context, _payload):
            raise JobHandlerError(RetryClass.DEPENDENCY_UNAVAILABLE, "TEST_DOWN", "Dependency unavailable")

        registry.register(OperationDefinition("test.echo", QueueClass.MAINTENANCE, EchoPayload, unavailable))
        async with sessions() as session:
            cancelled, _ = await submit_job(session, submission(workspace_id, user_id, key="cancel"))
            cancelled.cancellation_requested_at = get_current_utc_datetime()
            retrying, _ = await submit_job(session, submission(workspace_id, user_id, key="retry", max_attempts=2))
            await session.commit()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        worker = JobWorker(sessions, transport, registry=registry, worker_id="retry-worker", lease_seconds=10)
        deliveries = list(transport.deliveries)
        for delivery in deliveries:
            await worker.process_delivery(delivery)
        async with sessions() as session:
            cancelled_row = await session.get(JobModel, cancelled.id)
            retry_row = await session.get(JobModel, retrying.id)
            assert cancelled_row.status == JobStatus.CANCELLED
            assert retry_row.status == JobStatus.QUEUED
            pending = await session.scalar(
                select(OutboxMessageModel).where(
                    OutboxMessageModel.job_id == retrying.id,
                    OutboxMessageModel.published_at.is_(None),
                )
            )
            pending.available_at = get_current_utc_datetime()
            retry_row.available_at = get_current_utc_datetime()
            await session.commit()
        transport.deliveries.clear()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        assert len(transport.deliveries) == 1
        await worker.process_delivery(transport.deliveries[0])
        async with sessions() as session:
            retry_row = await session.get(JobModel, retrying.id)
            dead = list((await session.scalars(select(DeadLetterModel))).all())
            assert retry_row.status == JobStatus.DEAD_LETTER
            assert retry_row.attempt_count == 2
            assert len(dead) == 1 and dead[0].safe_error_code == "TEST_DOWN"
        await engine.dispose()

    asyncio.run(scenario())

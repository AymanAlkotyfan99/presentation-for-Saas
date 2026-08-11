"""Two-phase real Redis outage validation against a disposable PostgreSQL DB.

Run ``submit`` while the dedicated Redis container is stopped, then run
``recover`` after it has restarted. The first phase proves accepted work stays
durable in SQL; the second proves the same outbox message reaches Redis.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

from models.sql.user import User
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import JobStatus, QueueClass
from modules.jobs.outbox import RedisQueueTransport, dispatch_outbox_batch
from modules.jobs.persistence.models import JobModel, OutboxMessageModel
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel


OPERATION = "integration.redis-outage"
NAMESPACE = "bayanly:test:redis-outage"


def _required_url(name: str, prefixes: tuple[str, ...]) -> str:
    value = os.getenv(name, "").strip()
    if not value.startswith(prefixes):
        raise RuntimeError(f"{name} must identify a disposable integration service")
    return value


def _transport() -> RedisQueueTransport:
    client = Redis.from_url(
        _required_url("JOB_TEST_REDIS_URL", ("redis://", "rediss://")),
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    return RedisQueueTransport(client, NAMESPACE, visibility_seconds=1)


async def submit_during_outage(sessions) -> None:
    suffix = uuid4()
    async with sessions() as session:
        user = User(username=f"redis-outage-{suffix}", hashed_password="test")
        session.add(user)
        await session.flush()
        workspace = WorkspaceModel(name=f"Redis outage {suffix}", created_by=user.id)
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
        job, duplicate = await submit_job(
            session,
            JobSubmission(
                operation=OPERATION,
                queue_class=QueueClass.MAINTENANCE,
                workspace_id=workspace.id,
                actor_id=user.id,
                actor_service_account_id=None,
                idempotency_scope=OPERATION,
                idempotency_key=suffix.hex,
                payload={"value": "durable"},
            ),
        )
        assert not duplicate
        await session.commit()

    transport = _transport()
    try:
        async with sessions() as session:
            assert await dispatch_outbox_batch(session, transport) == 0
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            outbox = await session.scalar(
                select(OutboxMessageModel).where(OutboxMessageModel.job_id == job.id)
            )
            assert current is not None and current.status == JobStatus.PENDING
            assert outbox is not None and outbox.published_at is None
            assert outbox.publish_attempts == 1
            assert outbox.last_error_code == "QUEUE_UNAVAILABLE"
        print(f"outage persistence passed job={job.id}")
    finally:
        await transport.close()


async def recover_after_restart(sessions) -> None:
    async with sessions() as session:
        row = await session.scalar(
            select(OutboxMessageModel)
            .join(JobModel, JobModel.id == OutboxMessageModel.job_id)
            .where(
                JobModel.operation == OPERATION,
                OutboxMessageModel.published_at.is_(None),
                OutboxMessageModel.last_error_code == "QUEUE_UNAVAILABLE",
            )
            .order_by(OutboxMessageModel.created_at.desc())
        )
        if row is None:
            raise RuntimeError("No pending outage-validation outbox message was found")
        message_id = row.message_id
        job_id = row.job_id

    transport = _transport()
    try:
        assert await transport.health()
        async with sessions() as session:
            assert await dispatch_outbox_batch(session, transport) >= 1
        delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
        assert delivery is not None
        assert delivery.message_id == message_id
        assert delivery.job_id == job_id
        async with sessions() as session:
            current = await session.get(JobModel, job_id)
            outbox = await session.scalar(
                select(OutboxMessageModel).where(
                    OutboxMessageModel.message_id == message_id
                )
            )
            assert current is not None and current.status == JobStatus.QUEUED
            assert outbox is not None and outbox.published_at is not None
            assert outbox.last_error_code is None
        await transport.ack(delivery)
        print(f"outage recovery passed job={job_id}")
    finally:
        await transport.client.delete(transport.queue_name(QueueClass.MAINTENANCE))
        await transport.close()


async def main(mode: str) -> None:
    engine = create_async_engine(
        _required_url(
            "MIGRATION_TEST_DATABASE_URL",
            ("postgresql://", "postgresql+psycopg://"),
        )
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        if mode == "submit":
            await submit_during_outage(sessions)
        else:
            await recover_after_restart(sessions)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("submit", "recover"))
    args = parser.parse_args()
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        try:
            loop.run_until_complete(main(args.mode))
        finally:
            loop.close()
    else:
        asyncio.run(main(args.mode))

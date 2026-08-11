"""Transactional-outbox dispatcher and Redis queue transport.

PostgreSQL owns job truth. A Redis publish failure leaves the outbox row pending;
a crash after publish can redeliver, which is handled by the consumer inbox.
"""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from modules.jobs.application.submit import append_job_event
from modules.jobs.domain.models import JobStatus, QueueClass, assert_transition
from modules.jobs.persistence.models import JobModel, OutboxMessageModel
from utils.datetime_utils import get_current_utc_datetime


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueueDelivery:
    message_id: UUID
    job_id: UUID
    queue_class: QueueClass
    receipt_id: str | None = None


class QueueTransport(Protocol):
    async def publish(self, delivery: QueueDelivery) -> None: ...

    async def consume(self, queue_class: QueueClass, timeout: int = 5) -> QueueDelivery | None: ...

    async def ack(self, delivery: QueueDelivery) -> None: ...

    async def health(self) -> bool: ...

    async def close(self) -> None: ...


class RedisQueueTransport:
    """Redis Streams transport with explicit ack and stale-delivery reclaim.

    Stream entries remain pending until PostgreSQL records the consumer-inbox
    receipt as processed. If a worker dies after claiming a job, another worker
    reclaims the unacknowledged entry after the visibility interval. Redis is
    still delivery-only; the job, lease, result, and retry truth remain in SQL.
    """

    def __init__(
        self,
        client,
        namespace: str = "bayanly:jobs:v1",
        *,
        visibility_seconds: int = 90,
        consumer_name: str | None = None,
    ) -> None:
        self.client = client
        self.namespace = namespace.strip(":")
        self.group_name = f"{self.namespace}:workers:v1"
        self.visibility_seconds = max(1, min(visibility_seconds, 7200))
        self.consumer_name = consumer_name or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self._groups_ready: set[str] = set()

    @classmethod
    def from_environment(cls) -> "RedisQueueTransport":
        from redis.asyncio import Redis

        url = (
            os.getenv("JOB_REDIS_URL")
            or os.getenv("SECURITY_CONTROL_REDIS_URL")
            or os.getenv("REDIS_URL")
            or ""
        ).strip()
        if not url:
            raise RuntimeError("JOB_REDIS_URL is required for the durable job transport")
        client = Redis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=float(os.getenv("JOB_REDIS_CONNECT_TIMEOUT_SECONDS", "2")),
            # The worker uses a five-second blocking XREADGROUP. The socket
            # timeout must exceed that block window or an idle queue is
            # misreported as a broker failure.
            socket_timeout=max(
                6.0,
                float(os.getenv("JOB_REDIS_SOCKET_TIMEOUT_SECONDS", "10")),
            ),
            health_check_interval=30,
        )
        lease_seconds = int(os.getenv("JOB_LEASE_SECONDS", "60"))
        visibility_seconds = int(
            os.getenv("JOB_QUEUE_VISIBILITY_SECONDS", str(max(90, lease_seconds + 30)))
        )
        return cls(
            client,
            os.getenv("JOB_QUEUE_NAMESPACE", "bayanly:jobs:v1"),
            visibility_seconds=visibility_seconds,
        )

    def queue_name(self, queue_class: QueueClass) -> str:
        return f"{self.namespace}:queue:{queue_class.value}"

    async def publish(self, delivery: QueueDelivery) -> None:
        await self.client.xadd(
            self.queue_name(delivery.queue_class),
            {
                "messageId": str(delivery.message_id),
                "jobId": str(delivery.job_id),
                "queueClass": delivery.queue_class.value,
            },
        )

    async def _ensure_group(self, queue_name: str) -> None:
        if queue_name in self._groups_ready:
            return
        from redis.exceptions import ResponseError

        try:
            await self.client.xgroup_create(
                queue_name,
                self.group_name,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._groups_ready.add(queue_name)

    @staticmethod
    def _field(fields: dict, name: str) -> str:
        value = fields.get(name)
        if value is None:
            value = fields.get(name.encode("utf-8"))
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if not isinstance(value, str):
            raise ValueError(f"Redis job delivery is missing {name}")
        return value

    def _delivery(self, receipt_id, fields: dict) -> QueueDelivery:
        if isinstance(receipt_id, bytes):
            receipt_id = receipt_id.decode("ascii")
        return QueueDelivery(
            message_id=UUID(self._field(fields, "messageId")),
            job_id=UUID(self._field(fields, "jobId")),
            queue_class=QueueClass(self._field(fields, "queueClass")),
            receipt_id=str(receipt_id),
        )

    async def consume(self, queue_class: QueueClass, timeout: int = 5) -> QueueDelivery | None:
        queue_name = self.queue_name(queue_class)
        await self._ensure_group(queue_name)

        reclaimed = await self.client.xautoclaim(
            queue_name,
            self.group_name,
            self.consumer_name,
            min_idle_time=self.visibility_seconds * 1000,
            start_id="0-0",
            count=1,
        )
        reclaimed_messages = reclaimed[1] if len(reclaimed) > 1 else []
        if reclaimed_messages:
            receipt_id, fields = reclaimed_messages[0]
            return self._delivery(receipt_id, fields)

        streams = await self.client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {queue_name: ">"},
            count=1,
            block=max(1, min(timeout, 30)) * 1000,
        )
        if not streams:
            return None
        _, messages = streams[0]
        if not messages:
            return None
        receipt_id, fields = messages[0]
        return self._delivery(receipt_id, fields)

    async def ack(self, delivery: QueueDelivery) -> None:
        if not delivery.receipt_id:
            return
        queue_name = self.queue_name(delivery.queue_class)
        await self.client.xack(queue_name, self.group_name, delivery.receipt_id)
        # This deployment owns the only consumer group. Removing acknowledged
        # entries keeps stream storage bounded without trimming pending work.
        await self.client.xdel(queue_name, delivery.receipt_id)

    async def depth(self, queue_class: QueueClass) -> int:
        return int(await self.client.xlen(self.queue_name(queue_class)))

    async def health(self) -> bool:
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.aclose()


async def dispatch_outbox_batch(
    session: AsyncSession,
    transport: QueueTransport,
    *,
    limit: int = 100,
) -> int:
    """Publish a bounded batch. Publish-before-mark deliberately permits redelivery."""
    now = get_current_utc_datetime()
    rows = list(
        (
            await session.scalars(
                select(OutboxMessageModel)
                .where(
                    OutboxMessageModel.published_at.is_(None),
                    OutboxMessageModel.available_at <= now,
                )
                .order_by(OutboxMessageModel.created_at, OutboxMessageModel.id)
                .limit(max(1, min(limit, 500)))
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    published = 0
    for row in rows:
        row.publish_attempts += 1
        try:
            await transport.publish(
                QueueDelivery(
                    message_id=row.message_id,
                    job_id=row.job_id,
                    queue_class=row.queue_class,
                )
            )
        except Exception as exc:
            row.last_error_code = "QUEUE_UNAVAILABLE"
            LOGGER.warning(
                "[jobs.outbox] publish deferred message_id=%s job_id=%s error=%s",
                row.message_id,
                row.job_id,
                type(exc).__name__,
            )
            await session.commit()
            continue
        row.published_at = now
        row.last_error_code = None
        job = await session.get(JobModel, row.job_id)
        if job is not None and job.status == JobStatus.PENDING:
            assert_transition(job.status, JobStatus.QUEUED)
            job.status = JobStatus.QUEUED
            await append_job_event(session, job, "queued", {"queueClass": job.queue_class.value})
        await session.commit()
        published += 1
    return published


async def run_dispatcher_forever(
    session_factory: async_sessionmaker[AsyncSession],
    transport: QueueTransport,
    *,
    stop_event,
    idle_seconds: float = 0.5,
) -> None:
    import asyncio

    while not stop_event.is_set():
        async with session_factory() as session:
            count = await dispatch_outbox_batch(session, transport)
        if count == 0:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=idle_seconds)
            except asyncio.TimeoutError:
                pass

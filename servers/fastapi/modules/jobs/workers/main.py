"""Standalone durable dispatcher/worker entrypoint.

Run with: ``python -m modules.jobs.workers.main``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from modules.jobs.domain.models import QueueClass
from modules.jobs.outbox import RedisQueueTransport, run_dispatcher_forever
from modules.jobs.workers.handlers import register_core_handlers
from modules.jobs.workers.registry import JOB_REGISTRY
from modules.jobs.workers.runtime import JobWorker
from modules.assets.workers import register_asset_handlers
from modules.providers.workers import register_provider_handlers
from services.database import async_session_maker, dispose_engines


LOGGER = logging.getLogger(__name__)


def _concurrency(queue: QueueClass) -> int:
    raw = os.getenv(f"JOB_{queue.value.upper()}_CONCURRENCY", "1")
    try:
        return max(0, min(int(raw), 64))
    except ValueError:
        return 1


async def run() -> None:
    logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    register_core_handlers(JOB_REGISTRY)
    register_asset_handlers(JOB_REGISTRY)
    register_provider_handlers(JOB_REGISTRY)
    transport = RedisQueueTransport.from_environment()
    if not await transport.health():
        raise RuntimeError("Durable job Redis transport is unavailable")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, name, None)
        if signum is not None:
            try:
                loop.add_signal_handler(signum, stop_event.set)
            except (NotImplementedError, RuntimeError):
                pass

    tasks = [
        asyncio.create_task(
            run_dispatcher_forever(async_session_maker, transport, stop_event=stop_event),
            name="job-outbox-dispatcher",
        )
    ]
    for queue in QueueClass:
        for index in range(_concurrency(queue)):
            worker = JobWorker(
                async_session_maker,
                transport,
                worker_id=f"{os.getenv('HOSTNAME', 'worker')}:{queue.value}:{index}",
                lease_seconds=int(os.getenv("JOB_LEASE_SECONDS", "60")),
            )
            tasks.append(
                asyncio.create_task(
                    worker.run_queue(queue, stop_event=stop_event),
                    name=f"job-worker-{queue.value}-{index}",
                )
            )
    try:
        await stop_event.wait()
    finally:
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await transport.close()
        await dispose_engines()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run())

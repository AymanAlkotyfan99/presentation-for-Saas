"""Authoritative job states and retry classifications.

Delivery is intentionally described as at-least-once. Durable inbox records and
operation-level idempotency make application effects safe under redelivery.
"""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class QueueClass(str, Enum):
    GENERATION = "generation"
    IMAGE = "image"
    EXPORT = "export"
    WEBHOOK = "webhook"
    NOTIFICATION = "notification"
    MAINTENANCE = "maintenance"


class JobAuthorityKind(str, Enum):
    WORKSPACE = "WORKSPACE"
    SYSTEM_ACCOUNT_LIFECYCLE = "SYSTEM_ACCOUNT_LIFECYCLE"


class RetryClass(str, Enum):
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    NON_RETRYABLE_VALIDATION = "NON_RETRYABLE_VALIDATION"
    NON_RETRYABLE_AUTHORIZATION = "NON_RETRYABLE_AUTHORIZATION"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}
)

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.CANCELLATION_REQUESTED,
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.QUEUED,
            JobStatus.CANCELLED,
            JobStatus.DEAD_LETTER,
        }
    ),
    JobStatus.CANCELLATION_REQUESTED: frozenset(
        {JobStatus.SUCCEEDED, JobStatus.CANCELLED, JobStatus.FAILED, JobStatus.DEAD_LETTER}
    ),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.CANCELLED: frozenset(),
    JobStatus.DEAD_LETTER: frozenset(),
}


def assert_transition(current: JobStatus, target: JobStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid job state transition: {current.value} -> {target.value}")


def retryable(classification: RetryClass) -> bool:
    return classification in {
        RetryClass.TRANSIENT_NETWORK,
        RetryClass.RATE_LIMIT,
        RetryClass.PROVIDER_TIMEOUT,
        RetryClass.DEPENDENCY_UNAVAILABLE,
        RetryClass.UNKNOWN,
    }

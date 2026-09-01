"""Deterministic, process-local fixtures for account-lifecycle tests.

These helpers deliberately have no HTTP, filesystem, logging, or console
integration. They model test inputs only; production identity and notification
boundaries remain owned by the application modules introduced in later phases.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid5


ACCOUNT_LIFECYCLE_TEST_KEY_ID = "k1"
ACCOUNT_LIFECYCLE_TEST_KEY = bytes(range(32))
DEFAULT_ACCOUNT_LIFECYCLE_TIME = datetime(
    2030,
    1,
    2,
    3,
    4,
    5,
    tzinfo=timezone.utc,
)
_IDENTITY_NAMESPACE = UUID("c9725fd7-26f2-4a43-9cb5-4f0c0f3ee344")


@dataclass
class DeterministicAccountLifecycleClock:
    """A mutable UTC clock scoped to one test invocation."""

    value: datetime = DEFAULT_ACCOUNT_LIFECYCLE_TIME

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("account lifecycle test clocks require a UTC timestamp")
        self.value = self.value.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self.value

    def __call__(self) -> datetime:
        return self.now()

    def advance(self, *, seconds: int = 0, hours: int = 0, days: int = 0) -> datetime:
        self.value += timedelta(seconds=seconds, hours=hours, days=days)
        return self.value


@dataclass(frozen=True)
class DisposableAccountIdentity:
    email: str
    normalized_email: str
    locale: str
    pending_registration_id: UUID
    user_id: UUID
    opaque_test_token: str


class DisposableAccountIdentityBuilder:
    """Build reserved, deterministic identities without shared mutable state."""

    def __init__(self, seed: str):
        if not seed:
            raise ValueError("a non-empty per-test seed is required")
        self._seed = seed
        self._counter = 0

    @property
    def count(self) -> int:
        return self._counter

    def build(self, *, locale: str = "en") -> DisposableAccountIdentity:
        if locale not in {"en", "ar"}:
            raise ValueError("account lifecycle fixtures support only en or ar")

        self._counter += 1
        label = f"{self._seed}:{self._counter}:{locale}"
        safe_seed = sha256(label.encode("utf-8")).hexdigest()[:16]
        token_bytes = sha256(f"token:{label}".encode("utf-8")).digest()
        opaque_test_token = base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")
        email = f"account-{locale}-{safe_seed}@example.test"
        return DisposableAccountIdentity(
            email=email,
            normalized_email=email,
            locale=locale,
            pending_registration_id=uuid5(_IDENTITY_NAMESPACE, f"pending:{label}"),
            user_id=uuid5(_IDENTITY_NAMESPACE, f"user:{label}"),
            opaque_test_token=opaque_test_token,
        )


@dataclass(frozen=True)
class CapturedAccountLifecycleMessage:
    recipient: str
    purpose: str
    locale: str
    opaque_test_token: str


class InMemoryAccountLifecycleMailbox:
    """An injectable mailbox with no durable or externally visible sink."""

    def __init__(self) -> None:
        self._messages: list[CapturedAccountLifecycleMessage] = []

    @property
    def messages(self) -> tuple[CapturedAccountLifecycleMessage, ...]:
        return tuple(self._messages)

    def deliver(
        self,
        *,
        recipient: str,
        purpose: str,
        locale: str,
        opaque_test_token: str,
    ) -> CapturedAccountLifecycleMessage:
        if not recipient.lower().endswith("@example.test"):
            raise ValueError("test mailbox recipients must use the reserved example.test domain")
        if locale not in {"en", "ar"}:
            raise ValueError("test mailbox locale must be en or ar")
        if not opaque_test_token:
            raise ValueError("a non-empty in-memory test token is required")

        message = CapturedAccountLifecycleMessage(
            recipient=recipient,
            purpose=purpose,
            locale=locale,
            opaque_test_token=opaque_test_token,
        )
        self._messages.append(message)
        return message

    def clear(self) -> None:
        self._messages.clear()


def account_lifecycle_test_keyring() -> dict[str, bytes]:
    """Return a fresh mapping so tests cannot mutate another test's key ring."""

    return {ACCOUNT_LIFECYCLE_TEST_KEY_ID: ACCOUNT_LIFECYCLE_TEST_KEY}

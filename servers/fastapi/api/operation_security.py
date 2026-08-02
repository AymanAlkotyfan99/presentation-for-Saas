"""Distributed request-rate, concurrency, and emergency-operation controls.

The middleware in this module is intentionally independent from authentication.
Install it *inside* ``SessionAuthMiddleware`` so ``scope['state']`` contains the
resolved principal.  Direct service calls can use ``operation_guard`` and share
the same controls, which covers HTTP, background work, and MCP-originated calls.

Production configuration:

* ``PRESENTON_ENV=production`` (``APP_ENV``/``ENVIRONMENT`` are also accepted)
* ``SECURITY_CONTROL_BACKEND=redis``
* ``SECURITY_CONTROL_REDIS_URL=redis://...`` (``REDIS_URL`` is a fallback)
* ``SECURITY_CONTROL_NAMESPACE=presenton:security:v1``

Memory mode is allowed only outside production. Redis keys have bounded names
and expirations. Concurrency leases are renewed while work is active and expire
after a crashed worker. Production refuses to execute a protected operation if
Redis is missing or unhealthy.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
import time
import uuid
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)
_SAFE_NAMESPACE_RE = re.compile(r"^[a-zA-Z0-9:_-]{1,80}$")
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in _TRUTHY)


def _positive_int(name: str, default: int, maximum: int = 1_000_000) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, min(int(raw), maximum))
    except ValueError:
        LOGGER.warning("Ignoring invalid positive integer configuration for %s", name)
        return default


def is_production_environment() -> bool:
    return any(
        (os.getenv(name) or "").strip().lower() in {"production", "prod"}
        for name in ("PRESENTON_ENV", "APP_ENV", "ENVIRONMENT")
    )


class OperationControlError(Exception):
    code = "OPERATION_CONTROL_ERROR"
    status_code = 503

    def __init__(self, operation: str, retry_after: int | None = None) -> None:
        self.operation = operation
        self.retry_after = retry_after
        super().__init__(self.code)


class OperationRateLimited(OperationControlError):
    code = "RATE_LIMITED"
    status_code = 429


class OperationConcurrencyLimited(OperationControlError):
    code = "CONCURRENCY_LIMITED"
    status_code = 429


class OperationDisabled(OperationControlError):
    code = "OPERATION_DISABLED"
    status_code = 503


class OperationControlUnavailable(OperationControlError):
    code = "OPERATION_CONTROL_UNAVAILABLE"
    status_code = 503


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after: int = 0


@dataclass(frozen=True)
class BackendLease:
    key: str
    lease_id: str
    ttl_seconds: int


class OperationControlBackend(Protocol):
    async def consume_rate(
        self,
        key: str,
        *,
        rate: int,
        window_seconds: int,
        burst: int,
    ) -> RateDecision: ...

    async def acquire(
        self,
        key: str,
        *,
        limit: int,
        lease_seconds: int,
    ) -> tuple[BackendLease | None, int]: ...

    async def renew(self, lease: BackendLease) -> bool: ...

    async def release(self, lease: BackendLease) -> None: ...

    async def healthcheck(self) -> bool: ...

    async def close(self) -> None: ...


@dataclass
class _MemoryBucket:
    tokens: float
    updated_at: float
    expires_at: float


class InMemoryOperationControlBackend:
    """Bounded local-development backend; never accepted in production."""

    def __init__(
        self,
        *,
        time_source: Callable[[], float] = time.monotonic,
        max_keys: int = 20_000,
    ) -> None:
        self._time = time_source
        self._max_keys = max_keys
        self._rates: dict[str, _MemoryBucket] = {}
        self._leases: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    async def consume_rate(
        self,
        key: str,
        *,
        rate: int,
        window_seconds: int,
        burst: int,
    ) -> RateDecision:
        async with self._lock:
            now = self._time()
            self._prune(now)
            capacity = float(max(1, burst))
            refill_per_second = float(rate) / float(window_seconds)
            bucket = self._rates.get(key)
            if bucket is None:
                tokens = capacity
            else:
                tokens = min(
                    capacity,
                    bucket.tokens + max(0.0, now - bucket.updated_at) * refill_per_second,
                )
            if tokens >= 1.0:
                tokens -= 1.0
                allowed = True
                retry_after = 0
            else:
                allowed = False
                retry_after = max(1, math.ceil((1.0 - tokens) / refill_per_second))
            self._rates[key] = _MemoryBucket(
                tokens=tokens,
                updated_at=now,
                expires_at=now + max(window_seconds * 2, 60),
            )
            self._bound_keys(now)
            return RateDecision(allowed, retry_after)

    async def acquire(
        self,
        key: str,
        *,
        limit: int,
        lease_seconds: int,
    ) -> tuple[BackendLease | None, int]:
        async with self._lock:
            now = self._time()
            self._prune(now)
            active = self._leases.setdefault(key, {})
            if len(active) >= limit:
                retry_after = max(1, math.ceil(min(active.values()) - now))
                return None, retry_after
            lease = BackendLease(key, uuid.uuid4().hex, lease_seconds)
            active[lease.lease_id] = now + lease_seconds
            self._bound_keys(now)
            return lease, 0

    async def renew(self, lease: BackendLease) -> bool:
        async with self._lock:
            now = self._time()
            active = self._leases.get(lease.key)
            if not active or active.get(lease.lease_id, 0) <= now:
                if active:
                    active.pop(lease.lease_id, None)
                return False
            active[lease.lease_id] = now + lease.ttl_seconds
            return True

    async def release(self, lease: BackendLease) -> None:
        async with self._lock:
            active = self._leases.get(lease.key)
            if not active:
                return
            active.pop(lease.lease_id, None)
            if not active:
                self._leases.pop(lease.key, None)

    async def healthcheck(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def _prune(self, now: float) -> None:
        for key in [key for key, bucket in self._rates.items() if bucket.expires_at <= now]:
            self._rates.pop(key, None)
        for key, leases in list(self._leases.items()):
            for lease_id, expiry in list(leases.items()):
                if expiry <= now:
                    leases.pop(lease_id, None)
            if not leases:
                self._leases.pop(key, None)

    def _bound_keys(self, now: float) -> None:
        if len(self._rates) + len(self._leases) <= self._max_keys:
            return
        self._prune(now)
        if len(self._rates) + len(self._leases) <= self._max_keys:
            return
        # Memory mode is development-only. Drop the stalest rate buckets first;
        # active concurrency leases are never evicted early.
        overflow = len(self._rates) + len(self._leases) - self._max_keys
        for key, _ in sorted(
            self._rates.items(), key=lambda item: item[1].updated_at
        )[:overflow]:
            self._rates.pop(key, None)


_REDIS_RATE_SCRIPT = """
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local rate = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])
local values = redis.call('HMGET', KEYS[1], 'tokens', 'updated_at')
local tokens = tonumber(values[1]) or capacity
local updated_at = tonumber(values[2]) or now_ms
local refill = math.max(0, now_ms - updated_at) * rate / window_ms
tokens = math.min(capacity, tokens + refill)
local allowed = 0
local retry_ms = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
else
  retry_ms = math.ceil((1 - tokens) * window_ms / rate)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_at', now_ms)
redis.call('PEXPIRE', KEYS[1], ttl_ms)
return {allowed, retry_ms}
"""

_REDIS_ACQUIRE_SCRIPT = """
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local limit = tonumber(ARGV[1])
local lease_id = ARGV[2]
local lease_ms = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
  local earliest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_ms = lease_ms
  if earliest[2] then retry_ms = math.max(1, tonumber(earliest[2]) - now_ms) end
  return {0, retry_ms}
end
redis.call('ZADD', KEYS[1], now_ms + lease_ms, lease_id)
redis.call('PEXPIRE', KEYS[1], lease_ms * 2)
return {1, 0}
"""

_REDIS_RENEW_SCRIPT = """
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local lease_id = ARGV[1]
local lease_ms = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
if redis.call('ZSCORE', KEYS[1], lease_id) == false then return 0 end
redis.call('ZADD', KEYS[1], now_ms + lease_ms, lease_id)
redis.call('PEXPIRE', KEYS[1], lease_ms * 2)
return 1
"""


class RedisOperationControlBackend:
    def __init__(self, client: Any, namespace: str) -> None:
        self._client = client
        self._namespace = namespace

    @classmethod
    def from_url(cls, url: str, namespace: str) -> "RedisOperationControlBackend":
        try:
            from redis.asyncio import Redis
        except ImportError as error:
            raise OperationControlUnavailable("backend") from error
        client = Redis.from_url(
            url,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        return cls(client, namespace)

    def _key(self, category: str, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{self._namespace}:{category}:{digest}"

    async def consume_rate(
        self,
        key: str,
        *,
        rate: int,
        window_seconds: int,
        burst: int,
    ) -> RateDecision:
        try:
            result = await self._client.eval(
                _REDIS_RATE_SCRIPT,
                1,
                self._key("rate", key),
                rate,
                window_seconds * 1000,
                burst,
                max(window_seconds * 2000, 60_000),
            )
            return RateDecision(bool(int(result[0])), max(0, math.ceil(int(result[1]) / 1000)))
        except Exception as error:
            raise OperationControlUnavailable("backend") from error

    async def acquire(
        self,
        key: str,
        *,
        limit: int,
        lease_seconds: int,
    ) -> tuple[BackendLease | None, int]:
        lease = BackendLease(key, uuid.uuid4().hex, lease_seconds)
        try:
            result = await self._client.eval(
                _REDIS_ACQUIRE_SCRIPT,
                1,
                self._key("concurrency", key),
                limit,
                lease.lease_id,
                lease_seconds * 1000,
            )
        except Exception as error:
            raise OperationControlUnavailable("backend") from error
        if int(result[0]) == 1:
            return lease, 0
        return None, max(1, math.ceil(int(result[1]) / 1000))

    async def renew(self, lease: BackendLease) -> bool:
        try:
            result = await self._client.eval(
                _REDIS_RENEW_SCRIPT,
                1,
                self._key("concurrency", lease.key),
                lease.lease_id,
                lease.ttl_seconds * 1000,
            )
            return bool(int(result))
        except Exception as error:
            raise OperationControlUnavailable("backend") from error

    async def release(self, lease: BackendLease) -> None:
        try:
            await self._client.zrem(
                self._key("concurrency", lease.key), lease.lease_id
            )
        except Exception as error:
            raise OperationControlUnavailable("backend") from error

    async def healthcheck(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


@dataclass(frozen=True)
class OperationPolicy:
    rate: int
    window_seconds: int
    burst: int
    global_rate: int
    per_subject_concurrency: int | None = None
    global_concurrency: int | None = None
    lease_seconds: int = 120
    disable_envs: tuple[str, ...] = ()


def _policy(
    name: str,
    *,
    rate: int,
    burst: int,
    per_subject: int | None = None,
    global_limit: int | None = None,
    lease: int = 120,
    disable_envs: tuple[str, ...] = (),
) -> OperationPolicy:
    prefix = f"OPERATION_{name.upper()}"
    return OperationPolicy(
        rate=_positive_int(f"{prefix}_RATE_PER_MINUTE", rate),
        window_seconds=60,
        burst=_positive_int(f"{prefix}_BURST", burst),
        global_rate=_positive_int(f"{prefix}_GLOBAL_RATE_PER_MINUTE", rate * 100),
        per_subject_concurrency=(
            _positive_int(f"{prefix}_CONCURRENCY", per_subject)
            if per_subject is not None
            else None
        ),
        global_concurrency=(
            _positive_int(f"{prefix}_GLOBAL_CONCURRENCY", global_limit)
            if global_limit is not None
            else None
        ),
        lease_seconds=_positive_int(f"{prefix}_LEASE_SECONDS", lease, 3600),
        disable_envs=disable_envs,
    )


def default_operation_policies() -> dict[str, OperationPolicy]:
    return {
        "login": _policy("login", rate=10, burst=5),
        "password": _policy("password", rate=5, burst=3),
        "token_create": _policy("token_create", rate=10, burst=4),
        "presentation_generation": _policy(
            "presentation_generation",
            rate=6,
            burst=2,
            per_subject=1,
            global_limit=50,
            lease=300,
            disable_envs=("DISABLE_PRESENTATION_GENERATION",),
        ),
        "outline_generation": _policy(
            "outline_generation",
            rate=10,
            burst=2,
            per_subject=1,
            global_limit=50,
            lease=180,
            disable_envs=("DISABLE_PRESENTATION_GENERATION",),
        ),
        "slide_regeneration": _policy(
            "slide_regeneration",
            rate=20,
            burst=4,
            per_subject=2,
            global_limit=100,
            lease=180,
            disable_envs=("DISABLE_PRESENTATION_GENERATION",),
        ),
        "ai_chat": _policy(
            "ai_chat",
            rate=30,
            burst=5,
            per_subject=2,
            global_limit=100,
            lease=180,
            disable_envs=("DISABLE_AI_CHAT",),
        ),
        "image_generation": _policy(
            "image_generation",
            rate=20,
            burst=4,
            per_subject=2,
            global_limit=50,
            lease=300,
            disable_envs=("DISABLE_IMAGE_GENERATION", "DISABLE_AI_IMAGE_GENERATION"),
        ),
        "image_search": _policy(
            "image_search", rate=30, burst=6, per_subject=3, global_limit=100
        ),
        "provider_discovery": _policy(
            "provider_discovery",
            rate=20,
            burst=5,
            per_subject=2,
            global_limit=50,
            disable_envs=("DISABLE_PROVIDER_DISCOVERY",),
        ),
        "web_search": _policy(
            "web_search",
            rate=20,
            burst=4,
            per_subject=2,
            global_limit=50,
            disable_envs=("DISABLE_WEB_SEARCH",),
        ),
        "file_upload": _policy(
            "file_upload", rate=30, burst=6, per_subject=2, global_limit=100
        ),
        "document_parsing": _policy(
            "document_parsing",
            rate=10,
            burst=2,
            per_subject=1,
            global_limit=30,
            lease=600,
            disable_envs=("DISABLE_FILE_PROCESSING",),
        ),
        "export": _policy(
            "export",
            rate=10,
            burst=2,
            per_subject=1,
            global_limit=20,
            lease=600,
            disable_envs=("DISABLE_EXPORT",),
        ),
        "webhook_registration": _policy(
            "webhook_registration", rate=10, burst=3
        ),
        "webhook_delivery": _policy(
            "webhook_delivery",
            rate=60,
            burst=10,
            per_subject=5,
            global_limit=100,
            disable_envs=("DISABLE_WEBHOOK_DELIVERY",),
        ),
        "admin": _policy("admin", rate=60, burst=10, per_subject=5, global_limit=50),
    }


@dataclass(frozen=True)
class OperationIdentity:
    subject: str
    client_ip: str
    user_id: str | None = None
    workspace_id: str | None = None
    is_admin: bool = False

    @property
    def scope(self) -> str:
        # Workspace is deliberately ready for the future membership migration;
        # authenticated users remain the authoritative Phase 0 boundary.
        if self.workspace_id:
            return f"workspace:{self.workspace_id}:user:{self.user_id or self.subject}"
        if self.user_id:
            return f"user:{self.user_id}"
        return f"ip:{self.client_ip}"


class PolicyResolver(Protocol):
    def resolve(self, operation: str, identity: OperationIdentity) -> OperationPolicy: ...


class DefaultPolicyResolver:
    def __init__(self, policies: Mapping[str, OperationPolicy] | None = None) -> None:
        self._policies = dict(policies or default_operation_policies())

    def resolve(self, operation: str, identity: OperationIdentity) -> OperationPolicy:
        del identity
        try:
            return self._policies[operation]
        except KeyError as error:
            raise OperationControlUnavailable(operation) from error


_ACTIVE_OPERATIONS: ContextVar[frozenset[str]] = ContextVar(
    "active_operation_security_guards", default=frozenset()
)


class OperationController:
    def __init__(
        self,
        backend: OperationControlBackend,
        *,
        policy_resolver: PolicyResolver | None = None,
    ) -> None:
        self.backend = backend
        self.policy_resolver = policy_resolver or DefaultPolicyResolver()

    @asynccontextmanager
    async def guard(
        self, operation: str, identity: OperationIdentity
    ) -> AsyncIterator[None]:
        active = _ACTIVE_OPERATIONS.get()
        if operation in active:
            yield
            return

        policy = self.policy_resolver.resolve(operation, identity)
        disabled = {
            item.strip()
            for item in (os.getenv("PRESENTON_DISABLED_OPERATIONS") or "").split(",")
            if item.strip()
        }
        if operation in disabled or any(_truthy(os.getenv(name)) for name in policy.disable_envs):
            raise OperationDisabled(operation)

        admin_bypass = identity.is_admin and _truthy(
            os.getenv("SECURITY_ADMIN_BYPASS_LIMITS")
        )
        if not admin_bypass:
            subject_rate = await self.backend.consume_rate(
                f"{operation}:subject:{identity.scope}",
                rate=policy.rate,
                window_seconds=policy.window_seconds,
                burst=policy.burst,
            )
            if not subject_rate.allowed:
                raise OperationRateLimited(operation, subject_rate.retry_after)

        global_rate = await self.backend.consume_rate(
            f"{operation}:global",
            rate=policy.global_rate,
            window_seconds=policy.window_seconds,
            burst=max(policy.burst, min(policy.global_rate, policy.burst * 20)),
        )
        if not global_rate.allowed:
            raise OperationRateLimited(operation, global_rate.retry_after)

        leases: list[BackendLease] = []
        try:
            if policy.global_concurrency is not None:
                lease, retry_after = await self.backend.acquire(
                    f"{operation}:global",
                    limit=policy.global_concurrency,
                    lease_seconds=policy.lease_seconds,
                )
                if lease is None:
                    raise OperationConcurrencyLimited(operation, retry_after)
                leases.append(lease)
            if policy.per_subject_concurrency is not None and not admin_bypass:
                lease, retry_after = await self.backend.acquire(
                    f"{operation}:subject:{identity.scope}",
                    limit=policy.per_subject_concurrency,
                    lease_seconds=policy.lease_seconds,
                )
                if lease is None:
                    raise OperationConcurrencyLimited(operation, retry_after)
                leases.append(lease)

            stop_renewal = asyncio.Event()
            renewer = asyncio.create_task(
                self._renew_leases(leases, stop_renewal),
                name=f"operation-lease-renewal:{operation}",
            ) if leases else None
            token = _ACTIVE_OPERATIONS.set(active | {operation})
            try:
                yield
            finally:
                _ACTIVE_OPERATIONS.reset(token)
                stop_renewal.set()
                if renewer is not None:
                    renewer.cancel()
                    try:
                        await renewer
                    except asyncio.CancelledError:
                        pass
        finally:
            for lease in reversed(leases):
                try:
                    await self.backend.release(lease)
                except OperationControlUnavailable:
                    LOGGER.exception(
                        "Failed to release operation lease: operation=%s", operation
                    )

    async def _renew_leases(
        self, leases: list[BackendLease], stop: asyncio.Event
    ) -> None:
        interval = max(1.0, min(lease.ttl_seconds for lease in leases) / 3)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                for lease in leases:
                    if not await self.backend.renew(lease):
                        LOGGER.error("Operation concurrency lease expired before renewal")

    @asynccontextmanager
    async def guard_many(
        self, operations: Iterable[str], identity: OperationIdentity
    ) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for operation in dict.fromkeys(operations):
                await stack.enter_async_context(self.guard(operation, identity))
            yield


_BACKEND: OperationControlBackend | None = None
_BACKEND_SIGNATURE: tuple[str, str, str, bool] | None = None
_BACKEND_LOCK = asyncio.Lock()


def _backend_configuration() -> tuple[str, str, str, bool]:
    mode = (os.getenv("SECURITY_CONTROL_BACKEND") or "auto").strip().lower()
    url = (os.getenv("SECURITY_CONTROL_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
    namespace = (os.getenv("SECURITY_CONTROL_NAMESPACE") or "presenton:security:v1").strip()
    if not _SAFE_NAMESPACE_RE.fullmatch(namespace):
        raise OperationControlUnavailable("backend")
    return mode, url, namespace, is_production_environment()


async def get_operation_control_backend() -> OperationControlBackend:
    global _BACKEND, _BACKEND_SIGNATURE
    config = _backend_configuration()
    async with _BACKEND_LOCK:
        if _BACKEND is not None and _BACKEND_SIGNATURE == config:
            return _BACKEND
        if _BACKEND is not None:
            await _BACKEND.close()
            _BACKEND = None
        mode, url, namespace, production = config
        if mode not in {"auto", "memory", "redis"}:
            raise OperationControlUnavailable("backend")
        if production and mode != "redis":
            raise OperationControlUnavailable("backend")
        if mode == "memory" or (mode == "auto" and not url):
            if production:
                raise OperationControlUnavailable("backend")
            backend: OperationControlBackend = InMemoryOperationControlBackend()
        else:
            if not url:
                raise OperationControlUnavailable("backend")
            backend = RedisOperationControlBackend.from_url(url, namespace)
            if not await backend.healthcheck():
                await backend.close()
                if production or mode == "redis":
                    raise OperationControlUnavailable("backend")
                LOGGER.warning("Redis unavailable; using development-only memory controls")
                backend = InMemoryOperationControlBackend()
        _BACKEND = backend
        _BACKEND_SIGNATURE = config
        return backend


async def reset_operation_control_backend() -> None:
    """Test/lifespan helper; closes the cached Redis client when present."""
    global _BACKEND, _BACKEND_SIGNATURE
    async with _BACKEND_LOCK:
        if _BACKEND is not None:
            await _BACKEND.close()
        _BACKEND = None
        _BACKEND_SIGNATURE = None


async def healthcheck_operation_controls() -> bool:
    try:
        return await (await get_operation_control_backend()).healthcheck()
    except OperationControlUnavailable:
        return False


async def operation_controller() -> OperationController:
    return OperationController(await get_operation_control_backend())


def identity_for_current_owner(*, operation: str = "operation") -> OperationIdentity:
    try:
        from api.v1.auth.context import get_current_owner_id

        owner_id = get_current_owner_id()
    except Exception:
        owner_id = None
    value = str(owner_id) if owner_id else f"internal:{operation}:{uuid.uuid4().hex}"
    return OperationIdentity(
        subject=value,
        client_ip=value,
        user_id=str(owner_id) if owner_id else None,
    )


@asynccontextmanager
async def operation_guard(
    operation: str,
    identity: OperationIdentity | None = None,
) -> AsyncIterator[None]:
    controller = await operation_controller()
    async with controller.guard(
        operation, identity or identity_for_current_owner(operation=operation)
    ):
        yield


def guarded_operation(operation: str):
    """Protect a normal async service method before it starts costly work."""
    def decorator(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            async with operation_guard(operation):
                return await function(*args, **kwargs)

        return wrapped

    return decorator


def _trusted_proxy_networks() -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for value in (os.getenv("SECURITY_TRUSTED_PROXY_CIDRS") or "").split(","):
        if not value.strip():
            continue
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError:
            LOGGER.warning("Ignoring invalid SECURITY_TRUSTED_PROXY_CIDRS entry")
    return tuple(networks)


def _client_ip(scope: Mapping[str, Any]) -> str:
    client = scope.get("client") or ("unknown", 0)
    peer = str(client[0])
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return "unknown"
    if not any(peer_address in network for network in _trusted_proxy_networks()):
        return peer
    headers = {
        key.decode("latin1").lower(): value.decode("latin1")
        for key, value in scope.get("headers", [])
    }
    forwarded = headers.get("x-forwarded-for", "").split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return peer


def identity_from_scope(scope: Mapping[str, Any]) -> OperationIdentity:
    state = scope.get("state") or {}
    principal = state.get("auth_principal") if isinstance(state, dict) else None
    client_ip = _client_ip(scope)
    if principal is None:
        return OperationIdentity(subject=client_ip, client_ip=client_ip)
    user_id = str(getattr(principal, "user_id", "") or "") or None
    workspace_id = str(state.get("workspace_id") or "") or None
    return OperationIdentity(
        subject=user_id or client_ip,
        client_ip=client_ip,
        user_id=user_id,
        workspace_id=workspace_id,
        is_admin=bool(getattr(principal, "is_admin", False)),
    )


@dataclass(frozen=True)
class OperationRouteRule:
    operation: str
    methods: frozenset[str]
    pattern: re.Pattern[str]

    def matches(self, method: str, path: str) -> bool:
        return method in self.methods and bool(self.pattern.fullmatch(path))


def _rule(operation: str, methods: Iterable[str], pattern: str) -> OperationRouteRule:
    return OperationRouteRule(operation, frozenset(method.upper() for method in methods), re.compile(pattern))


DEFAULT_OPERATION_ROUTE_RULES = (
    _rule("login", {"POST"}, r"/api/v1/auth/login"),
    _rule("password", {"POST", "PUT"}, r"/api/v1/(?:auth|admin)/.*password.*"),
    _rule("token_create", {"POST"}, r"/api/v1/auth/token(?:/.*)?"),
    _rule("provider_discovery", {"GET", "POST"}, r"/api/v1/ppt/(?:openai|anthropic|google|ollama)/models/(?:available|supported|pull)"),
    _rule("outline_generation", {"GET"}, r"/api/v1/ppt/outlines/stream/[^/]+"),
    _rule("presentation_generation", {"GET"}, r"/api/v1/ppt/presentation/stream/[^/]+"),
    _rule("presentation_generation", {"POST"}, r"/api/v1/ppt/presentation/(?:generate(?:/async)?|prepare|create)"),
    _rule("slide_regeneration", {"POST"}, r"/api/v1/ppt/slide/edit(?:-html)?"),
    _rule("ai_chat", {"POST"}, r"/api/v1/ppt/chat/message(?:/stream)?"),
    _rule("image_generation", {"GET", "POST"}, r"/api/v1/ppt/images/generate"),
    _rule("image_search", {"GET"}, r"/api/v1/ppt/images/search"),
    _rule("file_upload", {"POST"}, r"/api/v1/ppt/files/upload"),
    _rule("document_parsing", {"POST"}, r"/api/v1/ppt/files/(?:decompose|update)"),
    _rule("export", {"POST"}, r"/api/v1/ppt/presentation/(?:generate(?:/async)?|edit|derive)"),
    _rule("webhook_registration", {"POST", "DELETE"}, r"/api/v1/webhook/(?:subscribe|unsubscribe)"),
    _rule("admin", {"POST", "PUT", "PATCH", "DELETE"}, r"/api/v1/admin/.*"),
)


def match_operations(
    method: str,
    path: str,
    rules: Iterable[OperationRouteRule] = DEFAULT_OPERATION_ROUTE_RULES,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule.operation for rule in rules if rule.matches(method.upper(), path)))


class OperationErrorResponse:
    """Minimal ASGI JSON response so the control backend has no web dependency."""

    def __init__(self, status_code: int, content: dict[str, Any], headers: Mapping[str, str] | None = None) -> None:
        self.status_code = status_code
        self.body = json.dumps(content, separators=(",", ":")).encode("utf-8")
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}
        self.headers.setdefault("content-type", "application/json")
        self.headers.setdefault("content-length", str(len(self.body)))

    async def __call__(self, _scope: Any, _receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    (key.encode("latin1"), value.encode("latin1"))
                    for key, value in self.headers.items()
                ],
            }
        )
        await send({"type": "http.response.body", "body": self.body})


def operation_error_response(error: OperationControlError) -> OperationErrorResponse:
    messages = {
        OperationRateLimited.code: "Too many requests for this operation",
        OperationConcurrencyLimited.code: "Too many concurrent requests for this operation",
        OperationDisabled.code: "This operation is temporarily disabled",
        OperationControlUnavailable.code: "Operation controls are unavailable",
    }
    headers = (
        {"Retry-After": str(max(1, error.retry_after))}
        if error.retry_after is not None
        else None
    )
    return OperationErrorResponse(
        error.status_code,
        {
            "detail": {
                "code": error.code,
                "message": messages.get(error.code, "Operation unavailable"),
                "operation": error.operation,
                **(
                    {"retry_after": max(1, error.retry_after)}
                    if error.retry_after is not None
                    else {}
                ),
            },
        },
        headers,
    )


class OperationSecurityMiddleware:
    """ASGI guard; release occurs after streaming/background work completes."""

    def __init__(
        self,
        app: Any,
        *,
        rules: Iterable[OperationRouteRule] = DEFAULT_OPERATION_ROUTE_RULES,
        controller_factory: Callable[[], Any] = operation_controller,
    ) -> None:
        self.app = app
        self.rules = tuple(rules)
        self.controller_factory = controller_factory

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        operations = match_operations(
            scope.get("method", "GET"), scope.get("path", ""), self.rules
        )
        if not operations:
            await self.app(scope, receive, send)
            return
        try:
            controller = await self.controller_factory()
            async with controller.guard_many(operations, identity_from_scope(scope)):
                await self.app(scope, receive, send)
        except OperationControlError as error:
            await operation_error_response(error)(scope, receive, send)

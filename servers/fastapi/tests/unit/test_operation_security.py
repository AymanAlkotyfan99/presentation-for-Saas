import asyncio
import contextvars
from dataclasses import dataclass
import json

import pytest

from api.operation_security import (
    DefaultPolicyResolver,
    InMemoryOperationControlBackend,
    OperationConcurrencyLimited,
    OperationController,
    OperationDisabled,
    OperationIdentity,
    OperationPolicy,
    OperationRateLimited,
    RedisOperationControlBackend,
    OperationSecurityMiddleware,
    get_operation_control_backend,
    match_operations,
    operation_error_response,
    reset_operation_control_backend,
)


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeClock:
    value: float = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def identity(name="user-1", *, admin=False, ip="198.51.100.2"):
    return OperationIdentity(
        subject=name,
        client_ip=ip,
        user_id=name if name else None,
        is_admin=admin,
    )


def policy(*, rate=60, burst=10, per_subject=None, global_limit=None, lease=30):
    return OperationPolicy(
        rate=rate,
        window_seconds=60,
        burst=burst,
        global_rate=1000,
        per_subject_concurrency=per_subject,
        global_concurrency=global_limit,
        lease_seconds=lease,
    )


def controller(backend, operation_policy):
    return OperationController(
        backend,
        policy_resolver=DefaultPolicyResolver({"test": operation_policy}),
    )


def test_burst_and_retry_after_then_refill():
    clock = FakeClock()
    backend = InMemoryOperationControlBackend(time_source=clock)

    async def scenario():
        subject = identity()
        guard = controller(backend, policy(rate=60, burst=2))
        async with guard.guard("test", subject):
            pass
        async with guard.guard("test", subject):
            pass
        with pytest.raises(OperationRateLimited) as exc:
            async with guard.guard("test", subject):
                pass
        assert exc.value.retry_after == 1
        clock.advance(1)
        async with guard.guard("test", subject):
            pass

    run(scenario())


def test_per_user_keys_are_independent_and_unauthenticated_identity_is_per_ip():
    backend = InMemoryOperationControlBackend()

    async def scenario():
        guard = controller(backend, policy(rate=1, burst=1))
        async with guard.guard("test", identity("alice")):
            pass
        async with guard.guard("test", identity("bob")):
            pass
        anonymous_a = OperationIdentity("198.51.100.10", "198.51.100.10")
        anonymous_b = OperationIdentity("198.51.100.11", "198.51.100.11")
        async with guard.guard("test", anonymous_a):
            pass
        async with guard.guard("test", anonymous_b):
            pass
        with pytest.raises(OperationRateLimited):
            async with guard.guard("test", anonymous_a):
                pass

    run(scenario())


def test_concurrency_is_shared_across_simulated_instances_and_released():
    backend = InMemoryOperationControlBackend()

    async def scenario():
        first = controller(backend, policy(per_subject=1))
        second = controller(backend, policy(per_subject=1))
        subject = identity()

        async def invoke_second():
            with pytest.raises(OperationConcurrencyLimited):
                async with second.guard("test", subject):
                    pass

        async with first.guard("test", subject):
            # A separate task has a separate request context, as another web
            # instance/request would, while sharing the same backend.
            await asyncio.create_task(invoke_second(), context=contextvars.Context())
        async with second.guard("test", subject):
            pass

    run(scenario())


def test_concurrency_releases_after_failure():
    backend = InMemoryOperationControlBackend()

    async def scenario():
        guard = controller(backend, policy(per_subject=1))
        subject = identity()
        with pytest.raises(RuntimeError):
            async with guard.guard("test", subject):
                raise RuntimeError("provider failed")
        async with guard.guard("test", subject):
            pass

    run(scenario())


def test_stale_lease_expires_after_worker_crash():
    clock = FakeClock()
    backend = InMemoryOperationControlBackend(time_source=clock)

    async def scenario():
        first, _ = await backend.acquire("shared", limit=1, lease_seconds=5)
        assert first is not None
        denied, retry_after = await backend.acquire("shared", limit=1, lease_seconds=5)
        assert denied is None
        assert retry_after == 5
        clock.advance(6)
        replacement, _ = await backend.acquire("shared", limit=1, lease_seconds=5)
        assert replacement is not None

    run(scenario())


def test_admin_override_is_explicit_and_never_bypasses_emergency_switch(monkeypatch):
    backend = InMemoryOperationControlBackend()

    async def scenario():
        guard = controller(backend, policy(rate=1, burst=1))
        admin = identity("admin", admin=True)
        monkeypatch.setenv("SECURITY_ADMIN_BYPASS_LIMITS", "true")
        async with guard.guard("test", admin):
            pass
        async with guard.guard("test", admin):
            pass
        monkeypatch.setenv("PRESENTON_DISABLED_OPERATIONS", "test")
        with pytest.raises(OperationDisabled):
            async with guard.guard("test", admin):
                pass

    run(scenario())


def test_nested_same_operation_does_not_double_charge_or_deadlock():
    backend = InMemoryOperationControlBackend()

    async def scenario():
        guard = controller(backend, policy(rate=1, burst=1, per_subject=1))
        subject = identity()
        async with guard.guard("test", subject):
            async with guard.guard("test", subject):
                pass
        with pytest.raises(OperationRateLimited):
            async with guard.guard("test", subject):
                pass

    run(scenario())


def test_route_policy_points_cover_expensive_surfaces():
    assert match_operations("POST", "/api/v1/auth/login") == ("login",)
    assert match_operations("GET", "/api/v1/ppt/outlines/stream/deck") == (
        "outline_generation",
    )
    assert match_operations("POST", "/api/v1/ppt/chat/message/stream") == (
        "ai_chat",
    )
    assert match_operations("POST", "/api/v1/ppt/presentation/generate") == (
        "presentation_generation",
        "export",
    )
    assert match_operations("POST", "/api/v1/ppt/files/decompose") == (
        "document_parsing",
    )
    assert match_operations("POST", "/api/v1/admin/users") == ("admin",)


def test_stable_error_body_and_retry_after_header():
    response = operation_error_response(OperationRateLimited("ai_chat", 7))
    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    body = json.loads(response.body)
    assert body["detail"] == {
        "code": "RATE_LIMITED",
        "message": "Too many requests for this operation",
        "operation": "ai_chat",
        "retry_after": 7,
    }


def test_production_fails_closed_without_redis(monkeypatch):
    async def scenario():
        await reset_operation_control_backend()
        monkeypatch.setenv("PRESENTON_ENV", "production")
        monkeypatch.setenv("SECURITY_CONTROL_BACKEND", "memory")
        with pytest.raises(Exception) as exc:
            await get_operation_control_backend()
        assert getattr(exc.value, "code", None) == "OPERATION_CONTROL_UNAVAILABLE"
        await reset_operation_control_backend()

    run(scenario())


def test_middleware_holds_concurrency_until_streaming_app_finishes():
    backend = InMemoryOperationControlBackend()
    operation_policy = policy(per_subject=1)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def app(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        started.set()
        await finish.wait()
        await send({"type": "http.response.body", "body": b"ok"})

    async def factory():
        return controller(backend, operation_policy)

    middleware = OperationSecurityMiddleware(
        app,
        rules=(
            # Reuse the built-in outline rule by exercising its exact path.
            *(),
        ),
        controller_factory=factory,
    )
    # Use a tiny custom rule without importing private helpers.
    from api.operation_security import OperationRouteRule
    import re

    middleware.rules = (
        OperationRouteRule("test", frozenset({"GET"}), re.compile(r"/stream")),
    )

    async def invoke(messages):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/stream",
            "headers": [],
            "client": ("198.51.100.8", 1234),
            "state": {},
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await middleware(scope, receive, send)

    async def scenario():
        first_messages = []
        first = asyncio.create_task(invoke(first_messages))
        await started.wait()
        second_messages = []
        await invoke(second_messages)
        assert second_messages[0]["status"] == 429
        finish.set()
        await first
        third_messages = []
        await invoke(third_messages)
        assert third_messages[0]["status"] == 200

    run(scenario())


class FakeRedis:
    """Small shared Redis stand-in for wrapper/multi-instance behavior tests."""

    def __init__(self):
        self.leases = {}
        self.keys = []

    async def eval(self, script, _number_of_keys, key, *args):
        self.keys.append(key)
        if "ZREMRANGEBYSCORE" in script and "ZSCORE" not in script:
            limit, lease_id, _lease_ms = args
            active = self.leases.setdefault(key, set())
            if len(active) >= int(limit):
                return [0, 1000]
            active.add(lease_id)
            return [1, 0]
        if "ZSCORE" in script:
            lease_id = args[0]
            return int(lease_id in self.leases.get(key, set()))
        # Rate script: allow for this focused wrapper test.
        return [1, 0]

    async def zrem(self, key, lease_id):
        self.leases.get(key, set()).discard(lease_id)

    async def ping(self):
        return True

    async def aclose(self):
        return None


def test_redis_backend_instances_share_namespaced_hashed_concurrency_keys():
    fake = FakeRedis()
    first = RedisOperationControlBackend(fake, "presenton:test")
    second = RedisOperationControlBackend(fake, "presenton:test")

    async def scenario():
        lease, _ = await first.acquire("image:user:alice", limit=1, lease_seconds=30)
        assert lease is not None
        denied, retry_after = await second.acquire(
            "image:user:alice", limit=1, lease_seconds=30
        )
        assert denied is None
        assert retry_after == 1
        assert all(key.startswith("presenton:test:concurrency:") for key in fake.keys)
        assert all("alice" not in key for key in fake.keys)
        await first.release(lease)
        replacement, _ = await second.acquire(
            "image:user:alice", limit=1, lease_seconds=30
        )
        assert replacement is not None

    run(scenario())

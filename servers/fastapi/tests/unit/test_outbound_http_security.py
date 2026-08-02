import asyncio
from dataclasses import replace

import pytest

from utils.outbound_http import (
    AiohttpPinnedTransport,
    AllowedOrigin,
    OutboundDNSBlocked,
    OutboundRedirectBlocked,
    OutboundRequestPolicy,
    OutboundRequestTimeout,
    OutboundResponseTooLarge,
    OutboundURLBlocked,
    SecureHTTPResponse,
    SecureOutboundClient,
    read_limited_response_body,
    validate_outbound_url,
)


PUBLIC_IPV4 = "93.184.216.34"


async def public_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
    return (PUBLIC_IPV4,)


def run(coro):
    return asyncio.run(coro)


def policy(**changes) -> OutboundRequestPolicy:
    return replace(OutboundRequestPolicy(), **changes)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://10.1.2.3",
        "http://172.16.1.1",
        "http://192.168.1.2",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "http://169.254.1.1",
        "http://[fe80::1]",
        "http://169.254.169.254/latest/meta-data",
        "http://[fd00:ec2::254]",
        "http://0.0.0.0",
        "http://[::]",
    ],
)
def test_blocks_non_public_literal_addresses(url):
    with pytest.raises((OutboundDNSBlocked, OutboundURLBlocked)):
        run(validate_outbound_url(url))


@pytest.mark.parametrize(
    "hostname",
    [
        "localhost",
        "service.localhost",
        "printer.local",
        "internal-service",
        "metadata.google.internal",
    ],
)
def test_blocks_local_and_metadata_hostnames_without_dns(hostname):
    calls = 0

    async def resolver(_host: str, _port: int) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return (PUBLIC_IPV4,)

    with pytest.raises(OutboundURLBlocked):
        run(validate_outbound_url(f"http://{hostname}", resolver=resolver))
    assert calls == 0


def test_blocks_mixed_public_and_private_dns_answers():
    async def mixed_resolver(_host: str, _port: int) -> tuple[str, ...]:
        return (PUBLIC_IPV4, "10.0.0.8", "2001:4860:4860::8888")

    with pytest.raises(OutboundDNSBlocked):
        run(validate_outbound_url("https://provider.example", resolver=mixed_resolver))


def test_approved_exact_origin_allows_private_self_hosted_endpoint():
    configured = policy(
        allowlist=(AllowedOrigin("http", "ollama", 11434),),
    )

    async def private_resolver(_host: str, _port: int) -> tuple[str, ...]:
        return ("10.10.0.20",)

    result = run(
        validate_outbound_url(
            "http://ollama:11434/api/tags",
            policy=configured,
            resolver=private_resolver,
        )
    )
    assert result.allowlisted is True
    assert result.addresses == ("10.10.0.20",)


def test_allowlist_does_not_override_metadata_or_link_local():
    configured = policy(
        allowlist=(AllowedOrigin("http", "metadata-proxy", 8080),),
    )

    async def metadata_resolver(_host: str, _port: int) -> tuple[str, ...]:
        return ("169.254.169.254",)

    with pytest.raises(OutboundDNSBlocked):
        run(
            validate_outbound_url(
                "http://metadata-proxy:8080/latest",
                policy=configured,
                resolver=metadata_resolver,
            )
        )


def test_accepts_public_https_provider_and_normalizes_idn():
    result = run(
        validate_outbound_url(
            "https://BÜCHER.example/v1/models",
            resolver=public_resolver,
        )
    )
    assert result.hostname == "xn--bcher-kva.example"
    assert result.port == 443
    assert result.addresses == (PUBLIC_IPV4,)


def test_rejects_url_credentials_and_invalid_ports():
    with pytest.raises(OutboundURLBlocked):
        run(
            validate_outbound_url(
                "https://user:secret@provider.example/v1",
                resolver=public_resolver,
            )
        )
    with pytest.raises(OutboundURLBlocked):
        run(
            validate_outbound_url(
                "https://provider.example:70000/v1",
                resolver=public_resolver,
            )
        )
    with pytest.raises(OutboundURLBlocked):
        run(
            validate_outbound_url(
                "https://provider.example:8443/v1",
                resolver=public_resolver,
            )
        )


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.validated = []
        self.requests = []

    async def request(self, validated, method, **kwargs):
        self.validated.append(validated)
        self.requests.append((method, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def response(status=200, headers=None, body=b"{}"):
    return SecureHTTPResponse(status, "", headers or {}, body, "https://provider.example")


def test_redirect_to_blocked_destination_is_revalidated_before_second_request():
    transport = FakeTransport(
        [response(302, {"Location": "http://127.0.0.1/admin"})]
    )
    client = SecureOutboundClient(resolver=public_resolver, transport=transport)
    with pytest.raises((OutboundDNSBlocked, OutboundURLBlocked)):
        run(client.request("GET", "https://provider.example/start"))
    assert len(transport.validated) == 1


def test_dns_answer_is_pinned_and_not_resolved_again_for_the_connection():
    answers = [(PUBLIC_IPV4,), ("127.0.0.1",)]
    calls = 0

    async def changing_resolver(_host: str, _port: int) -> tuple[str, ...]:
        nonlocal calls
        answer = answers[min(calls, len(answers) - 1)]
        calls += 1
        return answer

    transport = FakeTransport([response()])
    client = SecureOutboundClient(resolver=changing_resolver, transport=transport)
    result = run(client.request("GET", "https://provider.example/data"))
    assert result.status == 200
    assert calls == 1
    assert transport.validated[0].addresses == (PUBLIC_IPV4,)


def test_redirect_limit_is_enforced():
    transport = FakeTransport(
        [response(302, {"Location": "/again"}) for _ in range(4)]
    )
    client = SecureOutboundClient(
        policy=policy(max_redirects=2),
        resolver=public_resolver,
        transport=transport,
    )
    with pytest.raises(OutboundRedirectBlocked):
        run(client.request("GET", "https://provider.example/start"))
    assert len(transport.validated) == 3


def test_cross_origin_redirect_drops_credentials():
    transport = FakeTransport(
        [
            response(302, {"Location": "https://cdn.example.net/result"}),
            response(),
        ]
    )
    client = SecureOutboundClient(resolver=public_resolver, transport=transport)
    run(
        client.request(
            "GET",
            "https://provider.example/start",
            headers={"Authorization": "Bearer secret", "X-Request-ID": "safe"},
        )
    )
    first_headers = transport.requests[0][1]["headers"]
    second_headers = transport.requests[1][1]["headers"]
    assert first_headers["Authorization"] == "Bearer secret"
    assert "Authorization" not in second_headers
    assert second_headers["X-Request-ID"] == "safe"


class FakeContent:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, _size):
        for chunk in self.chunks:
            yield chunk


class FakeBodyResponse:
    def __init__(self, chunks):
        self.content = FakeContent(chunks)


def test_oversized_response_is_rejected_even_without_content_length():
    with pytest.raises(OutboundResponseTooLarge):
        run(read_limited_response_body(FakeBodyResponse([b"1234", b"5678"]), 7))


def test_timeout_is_a_stable_outbound_error():
    transport = FakeTransport([OutboundRequestTimeout()])
    client = SecureOutboundClient(resolver=public_resolver, transport=transport)
    with pytest.raises(OutboundRequestTimeout) as exc:
        run(client.request("GET", "https://provider.example/data"))
    assert exc.value.code == "OUTBOUND_REQUEST_TIMEOUT"


def test_transport_ignores_proxy_environment(monkeypatch):
    captured = {}

    class EmptyContent:
        async def iter_chunked(self, _size):
            if False:
                yield b""

    class FakeResponse:
        status = 200
        reason = "OK"
        headers = {}
        url = "https://provider.example/data"
        content = EmptyContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class FakeSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def request(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "utils.outbound_http.aiohttp.ClientSession", FakeSession
    )
    validated = run(
        validate_outbound_url(
            "https://provider.example/data", resolver=public_resolver
        )
    )
    result = run(
        AiohttpPinnedTransport().request(
            validated,
            "GET",
            policy=policy(),
        )
    )
    assert result.status == 200
    assert captured["trust_env"] is False

"""Central, DNS-pinned outbound HTTP policy.

All server-side requests whose destination can be configured or influenced by a
user should pass through this module.  Validation and connection use the same
resolved addresses: the custom aiohttp resolver pins each connection to the
addresses that were checked, so a second DNS answer cannot bypass the policy.

Configuration (environment variables are read for each policy construction):

* ``OUTBOUND_HTTP_ALLOWLIST``: comma-separated exact origins approved by an
  administrator, for example ``http://ollama:11434``.  An allowlisted origin may
  resolve to loopback/private space, but never to metadata, link-local,
  unspecified, multicast, or reserved addresses.
* ``OUTBOUND_HTTP_ALLOWED_PORTS``: comma-separated public destination ports;
  defaults to ``80,443``.  An exact allowlist origin may use another valid port.
* ``OUTBOUND_HTTP_MAX_REDIRECTS``: defaults to 3 (hard-capped at 10).
* ``OUTBOUND_HTTP_CONNECT_TIMEOUT_SECONDS`` and
  ``OUTBOUND_HTTP_READ_TIMEOUT_SECONDS``: default to 5 and 15 seconds.
* ``OUTBOUND_HTTP_MAX_RESPONSE_BYTES``: defaults to 10 MiB.

Proxy environment variables are deliberately ignored (``trust_env=False``).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import ipaddress
import json
import logging
import os
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp


LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
ABSOLUTE_MAX_RESPONSE_BYTES = 100 * 1024 * 1024
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CREDENTIAL_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-api-key",
        "x-subscription-token",
    }
)
_METADATA_HOSTNAMES = frozenset(
    {
        "instance-data",
        "metadata",
        "metadata.google",
        "metadata.google.internal",
        "metadata.azure.internal",
    }
)
_METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("fd00:ec2::254"),
    }
)


class OutboundSecurityError(Exception):
    """Base exception with a stable, non-sensitive public error code."""

    code = "OUTBOUND_REQUEST_BLOCKED"


class OutboundURLBlocked(OutboundSecurityError):
    code = "OUTBOUND_URL_BLOCKED"


class OutboundDNSBlocked(OutboundSecurityError):
    code = "OUTBOUND_DNS_BLOCKED"


class OutboundRedirectBlocked(OutboundSecurityError):
    code = "OUTBOUND_REDIRECT_BLOCKED"


class OutboundRequestTimeout(OutboundSecurityError):
    code = "OUTBOUND_REQUEST_TIMEOUT"


class OutboundResponseTooLarge(OutboundSecurityError):
    code = "OUTBOUND_RESPONSE_TOO_LARGE"


class OutboundTransportError(OutboundSecurityError):
    code = "OUTBOUND_TRANSPORT_ERROR"


def public_outbound_error(error: BaseException) -> dict[str, str]:
    code = (
        error.code
        if isinstance(error, OutboundSecurityError)
        else OutboundTransportError.code
    )
    messages = {
        OutboundURLBlocked.code: "The outbound destination is not permitted",
        OutboundDNSBlocked.code: "The outbound destination did not resolve safely",
        OutboundRedirectBlocked.code: "The outbound redirect is not permitted",
        OutboundRequestTimeout.code: "The outbound request timed out",
        OutboundResponseTooLarge.code: "The outbound response exceeded the size limit",
        OutboundTransportError.code: "The outbound service could not be reached",
    }
    return {"code": code, "message": messages.get(code, messages[OutboundTransportError.code])}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        LOGGER.warning("Ignoring invalid integer configuration for %s", name)
        return default
    return max(minimum, min(value, maximum))


def _normalize_hostname(hostname: str) -> str:
    value = hostname.strip().rstrip(".")
    if not value or any(ord(character) < 33 for character in value):
        raise OutboundURLBlocked("Invalid hostname")
    try:
        return value.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise OutboundURLBlocked("Invalid internationalized hostname") from error


@dataclass(frozen=True)
class AllowedOrigin:
    scheme: str
    hostname: str
    port: int

    def matches(self, scheme: str, hostname: str, port: int) -> bool:
        return (
            self.scheme == scheme
            and self.hostname == hostname
            and self.port == port
        )


def _parse_allowlist(value: str) -> tuple[AllowedOrigin, ...]:
    origins: list[AllowedOrigin] = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            parsed = urlsplit(entry)
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError
            scheme = parsed.scheme.lower()
            port = parsed.port or (443 if scheme == "https" else 80)
            origins.append(
                AllowedOrigin(scheme, _normalize_hostname(parsed.hostname), port)
            )
        except (OutboundSecurityError, ValueError):
            LOGGER.warning("Ignoring invalid OUTBOUND_HTTP_ALLOWLIST origin")
    return tuple(origins)


def _parse_allowed_ports(value: str) -> frozenset[int]:
    ports: set[int] = set()
    for raw_port in value.split(","):
        try:
            port = int(raw_port.strip())
        except ValueError:
            continue
        if 1 <= port <= 65535:
            ports.add(port)
    return frozenset(ports or {80, 443})


@dataclass(frozen=True)
class OutboundRequestPolicy:
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    allowed_ports: frozenset[int] = frozenset({80, 443})
    allowlist: tuple[AllowedOrigin, ...] = ()
    max_redirects: int = 3
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES

    @classmethod
    def from_environment(cls) -> "OutboundRequestPolicy":
        return cls(
            allowed_ports=_parse_allowed_ports(
                os.getenv("OUTBOUND_HTTP_ALLOWED_PORTS", "80,443")
            ),
            allowlist=_parse_allowlist(os.getenv("OUTBOUND_HTTP_ALLOWLIST", "")),
            max_redirects=_bounded_int(
                "OUTBOUND_HTTP_MAX_REDIRECTS", 3, 0, 10
            ),
            connect_timeout_seconds=float(
                _bounded_int("OUTBOUND_HTTP_CONNECT_TIMEOUT_SECONDS", 5, 1, 60)
            ),
            read_timeout_seconds=float(
                _bounded_int("OUTBOUND_HTTP_READ_TIMEOUT_SECONDS", 15, 1, 300)
            ),
            max_response_bytes=_bounded_int(
                "OUTBOUND_HTTP_MAX_RESPONSE_BYTES",
                DEFAULT_MAX_RESPONSE_BYTES,
                1024,
                ABSOLUTE_MAX_RESPONSE_BYTES,
            ),
        )


@dataclass(frozen=True)
class ValidatedOutboundURL:
    url: str
    scheme: str
    hostname: str
    port: int
    addresses: tuple[str, ...]
    allowlisted: bool


DNSResolver = Callable[[str, int], Awaitable[tuple[str, ...]]]


async def resolve_hostname(hostname: str, port: int) -> tuple[str, ...]:
    try:
        records = await asyncio.get_running_loop().getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise OutboundDNSBlocked("Hostname resolution failed") from error
    addresses = tuple(dict.fromkeys(record[4][0] for record in records))
    if not addresses:
        raise OutboundDNSBlocked("Hostname did not resolve")
    return addresses


def _coerce_address(raw_address: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(raw_address.split("%", 1)[0])
    except ValueError as error:
        raise OutboundDNSBlocked("DNS returned an invalid address") from error
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _is_non_overridable_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return (
        address in _METADATA_ADDRESSES
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


async def validate_outbound_url(
    url: str,
    *,
    policy: OutboundRequestPolicy | None = None,
    resolver: DNSResolver = resolve_hostname,
) -> ValidatedOutboundURL:
    active_policy = policy or OutboundRequestPolicy.from_environment()
    if not isinstance(url, str) or not url.strip() or len(url) > 4096:
        raise OutboundURLBlocked("Invalid URL")
    if any(ord(character) < 32 for character in url):
        raise OutboundURLBlocked("Control characters are not allowed")

    try:
        parsed = urlsplit(url.strip())
        scheme = parsed.scheme.lower()
        if scheme not in active_policy.allowed_schemes:
            raise OutboundURLBlocked("URL scheme is not allowed")
        if parsed.username is not None or parsed.password is not None:
            raise OutboundURLBlocked("URL credentials are not allowed")
        if not parsed.hostname:
            raise OutboundURLBlocked("URL hostname is required")
        hostname = _normalize_hostname(parsed.hostname)
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as error:
        raise OutboundURLBlocked("Invalid URL port") from error

    allowlisted = any(
        origin.matches(scheme, hostname, port) for origin in active_policy.allowlist
    )
    if port not in active_policy.allowed_ports and not allowlisted:
        raise OutboundURLBlocked("URL port is not allowed")

    local_hostname = (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname in _METADATA_HOSTNAMES
        or "." not in hostname
    )
    if hostname in _METADATA_HOSTNAMES:
        raise OutboundURLBlocked("Cloud metadata hostname is not allowed")
    if local_hostname and not allowlisted:
        raise OutboundURLBlocked("Local hostname is not allowed")

    try:
        literal_address = _coerce_address(hostname)
    except OutboundDNSBlocked:
        addresses = await resolver(hostname, port)
    else:
        addresses = (str(literal_address),)

    normalized_addresses: list[str] = []
    for raw_address in addresses:
        address = _coerce_address(raw_address)
        if _is_non_overridable_address(address):
            raise OutboundDNSBlocked("Destination address is never permitted")
        if not address.is_global and not allowlisted:
            raise OutboundDNSBlocked("Destination address is not public")
        normalized_addresses.append(str(address))

    if not normalized_addresses:
        raise OutboundDNSBlocked("Hostname did not resolve")

    canonical_netloc = hostname
    if ":" in hostname:
        canonical_netloc = f"[{hostname}]"
    default_port = 443 if scheme == "https" else 80
    if port != default_port:
        canonical_netloc = f"{canonical_netloc}:{port}"
    canonical_url = urlunsplit(
        (scheme, canonical_netloc, parsed.path or "/", parsed.query, "")
    )
    return ValidatedOutboundURL(
        url=canonical_url,
        scheme=scheme,
        hostname=hostname,
        port=port,
        addresses=tuple(dict.fromkeys(normalized_addresses)),
        allowlisted=allowlisted,
    )


class _PinnedResolver(aiohttp.abc.AbstractResolver):
    def __init__(self, validated: ValidatedOutboundURL) -> None:
        self._validated = validated

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[dict[str, Any]]:
        if _normalize_hostname(host) != self._validated.hostname:
            raise OSError("Attempted to resolve an unvalidated hostname")
        results: list[dict[str, Any]] = []
        for address in self._validated.addresses:
            parsed_address = ipaddress.ip_address(address)
            results.append(
                {
                    "hostname": host,
                    "host": address,
                    "port": port,
                    "family": (
                        socket.AF_INET6
                        if isinstance(parsed_address, ipaddress.IPv6Address)
                        else socket.AF_INET
                    ),
                    "proto": socket.IPPROTO_TCP,
                    "flags": 0,
                }
            )
        return results

    async def close(self) -> None:
        return None


@dataclass(frozen=True)
class SecureHTTPResponse:
    status: int
    reason: str
    headers: Mapping[str, str]
    body: bytes
    url: str

    async def read(self) -> bytes:
        return self.body

    async def text(self, encoding: str | None = None) -> str:
        return self.body.decode(encoding or "utf-8", errors="replace")

    async def json(self, **_: Any) -> Any:
        return json.loads(self.body.decode("utf-8"))


def safe_url_for_log(url: str) -> str:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or "invalid"
        port = parsed.port
        netloc = hostname if port is None else f"{hostname}:{port}"
        return urlunsplit((parsed.scheme, netloc, "", "", ""))
    except ValueError:
        return "invalid-url"


def _url_origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port


class AiohttpPinnedTransport:
    async def request(
        self,
        validated: ValidatedOutboundURL,
        method: str,
        *,
        policy: OutboundRequestPolicy,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
    ) -> SecureHTTPResponse:
        timeout = aiohttp.ClientTimeout(
            total=policy.connect_timeout_seconds + policy.read_timeout_seconds,
            connect=policy.connect_timeout_seconds,
            sock_connect=policy.connect_timeout_seconds,
            sock_read=policy.read_timeout_seconds,
        )
        connector = aiohttp.TCPConnector(
            resolver=_PinnedResolver(validated),
            use_dns_cache=False,
            ttl_dns_cache=0,
        )
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=False,
            ) as session:
                async with session.request(
                    method,
                    validated.url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    data=data,
                    allow_redirects=False,
                ) as response:
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            if int(content_length) > policy.max_response_bytes:
                                raise OutboundResponseTooLarge()
                        except ValueError:
                            pass
                    body = await read_limited_response_body(
                        response, policy.max_response_bytes
                    )
                    return SecureHTTPResponse(
                        status=response.status,
                        reason=response.reason or "",
                        headers=dict(response.headers),
                        body=body,
                        url=str(response.url),
                    )
        except OutboundSecurityError:
            raise
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as error:
            raise OutboundRequestTimeout() from error
        except aiohttp.ClientError as error:
            raise OutboundTransportError() from error


async def read_limited_response_body(response: Any, maximum_bytes: int) -> bytes:
    """Read an aiohttp-compatible response without trusting Content-Length."""
    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > maximum_bytes:
            raise OutboundResponseTooLarge()
    return bytes(body)


class SecureOutboundClient:
    def __init__(
        self,
        *,
        policy: OutboundRequestPolicy | None = None,
        resolver: DNSResolver = resolve_hostname,
        transport: AiohttpPinnedTransport | None = None,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.policy = policy or OutboundRequestPolicy.from_environment()
        self.resolver = resolver
        self.transport = transport or AiohttpPinnedTransport()
        self.default_headers = dict(default_headers or {})

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        allow_redirects: bool = True,
        timeout: float | aiohttp.ClientTimeout | None = None,
        max_response_bytes: int | None = None,
    ) -> SecureHTTPResponse:
        policy = self.policy
        if max_response_bytes is not None:
            policy = replace(
                policy,
                max_response_bytes=max(
                    1, min(int(max_response_bytes), ABSOLUTE_MAX_RESPONSE_BYTES)
                ),
            )
        if timeout is not None:
            total = timeout.total if isinstance(timeout, aiohttp.ClientTimeout) else timeout
            if total is not None:
                policy = replace(
                    policy,
                    read_timeout_seconds=max(1.0, min(float(total), 3600.0)),
                )

        current_url = url
        current_method = method.upper()
        current_json = json_body
        current_data = data
        merged_headers = {**self.default_headers, **dict(headers or {})}
        for redirect_count in range(policy.max_redirects + 1):
            validated = await validate_outbound_url(
                current_url,
                policy=policy,
                resolver=self.resolver,
            )
            LOGGER.debug(
                "Outbound request allowed: method=%s origin=%s",
                current_method,
                safe_url_for_log(validated.url),
            )
            response = await self.transport.request(
                validated,
                current_method,
                policy=policy,
                headers=merged_headers,
                params=params,
                json_body=current_json,
                data=current_data,
            )
            if not allow_redirects or response.status not in _REDIRECT_STATUSES:
                return response
            location = response.headers.get("Location") or response.headers.get("location")
            if not location:
                return response
            if redirect_count >= policy.max_redirects:
                raise OutboundRedirectBlocked("Too many redirects")
            next_url = urljoin(validated.url, location)
            if _url_origin(next_url) != _url_origin(validated.url):
                merged_headers = {
                    key: value
                    for key, value in merged_headers.items()
                    if key.lower() not in _CREDENTIAL_HEADERS
                }
            current_url = next_url
            params = None
            if response.status == 303 or (
                response.status in {301, 302} and current_method == "POST"
            ):
                current_method = "GET"
                current_json = None
                current_data = None
        raise OutboundRedirectBlocked("Too many redirects")


async def secure_http_request(
    method: str,
    url: str,
    **kwargs: Any,
) -> SecureHTTPResponse:
    return await SecureOutboundClient().request(method, url, **kwargs)


class _SecureRequestContext:
    def __init__(self, request: Awaitable[SecureHTTPResponse]) -> None:
        self._request = request
        self._response: SecureHTTPResponse | None = None

    def __await__(self):
        return self._get().__await__()

    async def _get(self) -> SecureHTTPResponse:
        if self._response is None:
            self._response = await self._request
        return self._response

    async def __aenter__(self) -> SecureHTTPResponse:
        return await self._get()

    async def __aexit__(self, *_: Any) -> None:
        return None


class SecureClientSession:
    """Small aiohttp-like adapter used to migrate existing callers safely."""

    def __init__(
        self,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
        policy: OutboundRequestPolicy | None = None,
    ) -> None:
        self._client = SecureOutboundClient(
            policy=policy,
            default_headers=headers,
        )
        self._timeout = timeout

    async def __aenter__(self) -> "SecureClientSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    def request(self, method: str, url: str, **kwargs: Any) -> _SecureRequestContext:
        json_body = kwargs.pop("json", None)
        timeout = kwargs.pop("timeout", self._timeout)
        max_response_bytes = kwargs.pop("max_response_bytes", None)
        return _SecureRequestContext(
            self._client.request(
                method,
                url,
                json_body=json_body,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
                **kwargs,
            )
        )

    def get(self, url: str, **kwargs: Any) -> _SecureRequestContext:
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> _SecureRequestContext:
        return self.request("HEAD", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> _SecureRequestContext:
        return self.request("POST", url, **kwargs)


@asynccontextmanager
async def secure_stream_request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    json_body: Any = None,
    policy: OutboundRequestPolicy | None = None,
    resolver: DNSResolver = resolve_hostname,
    timeout_seconds: float = 300.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> AsyncIterator[tuple[aiohttp.ClientResponse, AsyncIterator[bytes]]]:
    """Open a pinned streaming response and expose a size-limited byte iterator."""

    active_policy = policy or OutboundRequestPolicy.from_environment()
    active_policy = replace(
        active_policy,
        read_timeout_seconds=max(1.0, min(timeout_seconds, 3600.0)),
        max_response_bytes=max(1, min(max_response_bytes, ABSOLUTE_MAX_RESPONSE_BYTES)),
    )
    current_url = url
    current_method = method.upper()
    current_json = json_body
    current_headers = dict(headers or {})
    session: aiohttp.ClientSession | None = None
    response: aiohttp.ClientResponse | None = None
    try:
        for redirect_count in range(active_policy.max_redirects + 1):
            validated = await validate_outbound_url(
                current_url, policy=active_policy, resolver=resolver
            )
            connector = aiohttp.TCPConnector(
                resolver=_PinnedResolver(validated),
                use_dns_cache=False,
                ttl_dns_cache=0,
            )
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=active_policy.connect_timeout_seconds + timeout_seconds,
                    connect=active_policy.connect_timeout_seconds,
                    sock_connect=active_policy.connect_timeout_seconds,
                    sock_read=active_policy.read_timeout_seconds,
                ),
                trust_env=False,
            )
            response = await session.request(
                current_method,
                validated.url,
                headers=current_headers,
                json=current_json,
                allow_redirects=False,
            )
            location = response.headers.get("Location")
            if response.status not in _REDIRECT_STATUSES or not location:
                async def limited_bytes() -> AsyncIterator[bytes]:
                    consumed = 0
                    assert response is not None
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        consumed += len(chunk)
                        if consumed > active_policy.max_response_bytes:
                            raise OutboundResponseTooLarge()
                        yield chunk

                yield response, limited_bytes()
                return
            redirect_status = response.status
            response.release()
            await session.close()
            response = None
            session = None
            if redirect_count >= active_policy.max_redirects:
                raise OutboundRedirectBlocked("Too many redirects")
            next_url = urljoin(validated.url, location)
            if _url_origin(next_url) != _url_origin(validated.url):
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if key.lower() not in _CREDENTIAL_HEADERS
                }
            current_url = next_url
            if redirect_status == 303 or (
                redirect_status in {301, 302} and current_method == "POST"
            ):
                current_method = "GET"
                current_json = None
    except OutboundSecurityError:
        raise
    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as error:
        raise OutboundRequestTimeout() from error
    except aiohttp.ClientError as error:
        raise OutboundTransportError() from error
    finally:
        if response is not None:
            response.release()
        if session is not None:
            await session.close()

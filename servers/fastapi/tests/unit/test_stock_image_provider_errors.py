import asyncio
from unittest.mock import patch

import pytest

from services.image_generation_service import ImageGenerationService
from utils.api_errors import StableAPIError
from utils.outbound_http import OutboundDNSUnavailable, SecureHTTPResponse


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, *_args, **_kwargs):
        if self.error:
            raise self.error
        return self.response


def service():
    return ImageGenerationService.__new__(ImageGenerationService)


def response(status: int, body: bytes) -> SecureHTTPResponse:
    return SecureHTTPResponse(status, "", {}, body, "https://api.pexels.com")


def test_pexels_dns_failure_has_stable_non_secret_contract(caplog):
    session = FakeSession(error=OutboundDNSUnavailable("resolver unavailable"))
    with patch("services.image_generation_service.SecureClientSession", return_value=session):
        with pytest.raises(StableAPIError) as exc:
            run(service().get_image_from_pexels("business", api_key="top-secret"))

    assert exc.value.status_code == 503
    assert exc.value.code == "IMAGE_PROVIDER_DNS_UNAVAILABLE"
    assert "top-secret" not in str(exc.value.response_body())
    assert "top-secret" not in caplog.text


def test_pexels_upstream_payload_is_not_reflected_to_clients(caplog):
    secret_payload = b'upstream diagnostic containing top-secret-key'
    session = FakeSession(response=response(502, secret_payload))
    with patch("services.image_generation_service.SecureClientSession", return_value=session):
        with pytest.raises(StableAPIError) as exc:
            run(service().get_image_from_pexels("business", api_key="top-secret-key"))

    assert exc.value.status_code == 502
    assert exc.value.code == "IMAGE_PROVIDER_UPSTREAM_ERROR"
    assert "top-secret" not in str(exc.value.response_body())
    assert "top-secret" not in caplog.text


def test_pexels_invalid_json_is_a_stable_response_error():
    session = FakeSession(response=response(200, b"not-json"))
    with patch("services.image_generation_service.SecureClientSession", return_value=session):
        with pytest.raises(StableAPIError) as exc:
            run(service().get_image_from_pexels("business", api_key="configured"))

    assert exc.value.code == "IMAGE_PROVIDER_RESPONSE_INVALID"
    assert exc.value.status_code == 502


def test_pixabay_rejected_key_has_stable_credentials_error():
    session = FakeSession(response=response(400, b"Invalid API key value"))
    with patch("services.image_generation_service.SecureClientSession", return_value=session):
        with pytest.raises(StableAPIError) as exc:
            run(service().get_image_from_pixabay("business", api_key="invalid"))

    assert exc.value.code == "IMAGE_PROVIDER_CREDENTIALS_REJECTED"
    assert exc.value.status_code == 401

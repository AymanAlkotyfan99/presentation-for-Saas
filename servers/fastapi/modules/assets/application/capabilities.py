from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from uuid import UUID


_DEVELOPMENT_KEY = secrets.token_bytes(32)


def _key() -> bytes:
    configured = os.getenv("ASSET_CAPABILITY_SIGNING_KEY", "").encode("utf-8")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("ASSET_CAPABILITY_SIGNING_KEY must be at least 32 bytes")
        return configured
    if os.getenv("PRESENTON_ENV", "development").lower() == "production":
        raise RuntimeError("ASSET_CAPABILITY_SIGNING_KEY is required in production")
    return _DEVELOPMENT_KEY


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_download_capability(asset_id: UUID, workspace_id: UUID, expires_seconds: int = 300) -> tuple[str, int]:
    expires_at = int(time.time()) + max(1, min(expires_seconds, 900))
    body = json.dumps(
        {"assetId": str(asset_id), "workspaceId": str(workspace_id), "method": "GET", "exp": expires_at},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(_key(), body, hashlib.sha256).digest()
    return f"{_encode(body)}.{_encode(signature)}", expires_at


def verify_download_capability(token: str, asset_id: UUID, workspace_id: UUID) -> bool:
    try:
        encoded, supplied = token.split(".", 1)
        body = _decode(encoded)
        expected = hmac.new(_key(), body, hashlib.sha256).digest()
        payload = json.loads(body)
        return (
            hmac.compare_digest(expected, _decode(supplied))
            and payload == {
                "assetId": str(asset_id),
                "workspaceId": str(workspace_id),
                "method": "GET",
                "exp": payload.get("exp"),
            }
            and isinstance(payload["exp"], int)
            and payload["exp"] >= int(time.time())
        )
    except Exception:
        return False

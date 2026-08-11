"""Provider-neutral envelope encryption for outbound provider credentials."""

from __future__ import annotations

import base64
import os
import secrets
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.providers.persistence.models import EncryptedProviderSecretModel
from utils.datetime_utils import get_current_utc_datetime


class SecretDecryptionError(RuntimeError):
    pass


class MasterKeyProvider(Protocol):
    def active_key(self) -> tuple[str, bytes]: ...
    def key(self, version: str) -> bytes: ...


def _decode_key(value: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise RuntimeError("PROVIDER_MASTER_KEY is not valid base64") from exc
    if len(decoded) != 32:
        raise RuntimeError("PROVIDER_MASTER_KEY must decode to exactly 32 bytes")
    return decoded


class EnvironmentMasterKeyProvider:
    """Deployment-secret boundary. This is not represented as a production KMS."""

    def active_key(self) -> tuple[str, bytes]:
        version = (os.getenv("PROVIDER_MASTER_KEY_VERSION") or "local-v1").strip()
        encoded = (os.getenv("PROVIDER_MASTER_KEY") or "").strip()
        if not encoded:
            raise RuntimeError("PROVIDER_MASTER_KEY is required for encrypted provider configuration")
        return version, _decode_key(encoded)

    def key(self, version: str) -> bytes:
        active_version, key = self.active_key()
        if version != active_version:
            legacy = (os.getenv(f"PROVIDER_MASTER_KEY_{version.upper().replace('-', '_')}") or "").strip()
            if not legacy:
                raise SecretDecryptionError("Provider master-key version is unavailable")
            return _decode_key(legacy)
        return key


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


@dataclass(frozen=True)
class EncryptedEnvelope:
    ciphertext: str
    nonce: str
    encrypted_data_key: str
    data_key_nonce: str
    master_key_version: str


def encrypt_secret(
    plaintext: str,
    *,
    account_id: UUID,
    name: str,
    version: int,
    keys: MasterKeyProvider,
) -> EncryptedEnvelope:
    if not plaintext or len(plaintext.encode("utf-8")) > 16 * 1024:
        raise ValueError("Provider secret is empty or exceeds its size limit")
    key_version, master_key = keys.active_key()
    data_key = secrets.token_bytes(32)
    data_nonce = secrets.token_bytes(12)
    key_nonce = secrets.token_bytes(12)
    associated = f"bayanly-provider-secret:{account_id}:{name}:{version}".encode()
    ciphertext = AESGCM(data_key).encrypt(data_nonce, plaintext.encode("utf-8"), associated)
    encrypted_key = AESGCM(master_key).encrypt(key_nonce, data_key, associated)
    return EncryptedEnvelope(
        ciphertext=_encode(ciphertext), nonce=_encode(data_nonce),
        encrypted_data_key=_encode(encrypted_key), data_key_nonce=_encode(key_nonce),
        master_key_version=key_version,
    )


def decrypt_secret(row: EncryptedProviderSecretModel, keys: MasterKeyProvider) -> str:
    associated = f"bayanly-provider-secret:{row.provider_account_id}:{row.name}:{row.version}".encode()
    try:
        if (
            len(row.ciphertext) > 24 * 1024
            or len(row.encrypted_data_key) > 256
            or len(row.nonce) > 64
            or len(row.data_key_nonce) > 64
        ):
            raise ValueError("Encrypted provider secret exceeds its bounds")
        master_key = keys.key(row.master_key_version)
        data_key = AESGCM(master_key).decrypt(_decode(row.data_key_nonce), _decode(row.encrypted_data_key), associated)
        plaintext = AESGCM(data_key).decrypt(_decode(row.nonce), _decode(row.ciphertext), associated)
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError, SecretDecryptionError) as exc:
        raise SecretDecryptionError("Provider secret could not be decrypted") from exc


async def rotate_provider_secret(
    session: AsyncSession,
    *,
    account_id: UUID,
    workspace_id: UUID,
    name: str,
    plaintext: str,
    keys: MasterKeyProvider | None = None,
) -> EncryptedProviderSecretModel:
    keys = keys or EnvironmentMasterKeyProvider()
    current = await session.scalar(
        select(EncryptedProviderSecretModel)
        .where(
            EncryptedProviderSecretModel.provider_account_id == account_id,
            EncryptedProviderSecretModel.name == name,
            EncryptedProviderSecretModel.deleted_at.is_(None),
        )
        .order_by(EncryptedProviderSecretModel.version.desc())
        .limit(1)
        .with_for_update()
    )
    version = (current.version + 1) if current else 1
    envelope = encrypt_secret(plaintext, account_id=account_id, name=name, version=version, keys=keys)
    if current:
        current.rotated_at = get_current_utc_datetime()
    row = EncryptedProviderSecretModel(
        provider_account_id=account_id,
        workspace_id=workspace_id,
        name=name[:64],
        version=version,
        ciphertext=envelope.ciphertext,
        nonce=envelope.nonce,
        encrypted_data_key=envelope.encrypted_data_key,
        data_key_nonce=envelope.data_key_nonce,
        master_key_version=envelope.master_key_version,
    )
    session.add(row)
    await session.flush()
    return row


async def resolve_provider_secret(
    session: AsyncSession,
    *,
    account_id: UUID,
    name: str = "api_key",
    keys: MasterKeyProvider | None = None,
) -> str | None:
    row = await session.scalar(
        select(EncryptedProviderSecretModel)
        .where(
            EncryptedProviderSecretModel.provider_account_id == account_id,
            EncryptedProviderSecretModel.name == name,
            EncryptedProviderSecretModel.deleted_at.is_(None),
        )
        .order_by(EncryptedProviderSecretModel.version.desc())
        .limit(1)
    )
    return decrypt_secret(row, keys or EnvironmentMasterKeyProvider()) if row else None


async def delete_provider_secret(session: AsyncSession, *, account_id: UUID, name: str = "api_key") -> int:
    rows = list(
        (
            await session.scalars(
                select(EncryptedProviderSecretModel).where(
                    EncryptedProviderSecretModel.provider_account_id == account_id,
                    EncryptedProviderSecretModel.name == name,
                )
            )
        ).all()
    )
    for row in rows:
        await session.delete(row)
    await session.flush()
    return len(rows)

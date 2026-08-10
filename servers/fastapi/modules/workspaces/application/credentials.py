from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.workspaces.application.audit import append_audit_event
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import Permission
from modules.workspaces.domain.policies import SERVICE_ACCOUNT_SCOPES
from modules.workspaces.persistence.models import ApiCredentialModel, ApiCredentialScopeModel, ServiceAccountModel
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerifiedServiceCredential:
    credential_id: UUID
    workspace_id: UUID
    service_account_id: UUID
    service_account_name: str
    scopes: frozenset[str]


def _digest(token: str) -> str:
    pepper = os.getenv("WORKSPACE_TOKEN_PEPPER", "").encode()
    return hmac.new(pepper, token.encode(), hashlib.sha256).hexdigest()


def _validate_scopes(scopes: list[str]) -> list[str]:
    normalized = sorted(set(scopes))
    unknown = set(normalized) - SERVICE_ACCOUNT_SCOPES
    if not normalized or unknown:
        raise StableAPIError(422, "CREDENTIAL_SCOPE_INVALID", "Credential contains an unknown or empty scope set")
    return normalized


async def create_service_account(
    session: AsyncSession, *, actor, workspace_id: UUID, name: str,
) -> ServiceAccountModel:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.CREDENTIALS_MANAGE)
    candidate = name.strip()
    if not 1 <= len(candidate) <= 128:
        raise StableAPIError(422, "SERVICE_ACCOUNT_NAME_INVALID", "Service account name is invalid")
    account = ServiceAccountModel(workspace_id=workspace_id, name=candidate, created_by=actor.user_id)
    session.add(account); await session.flush()
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="service_account.created", subject_type="service_account", subject_id=account.id,
    )
    await session.commit(); await session.refresh(account)
    return account


async def issue_credential(
    session: AsyncSession, *, actor, workspace_id: UUID,
    service_account_id: UUID, scopes: list[str], rotate_credential_id: UUID | None = None,
) -> tuple[ApiCredentialModel, str]:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.CREDENTIALS_MANAGE)
    account = await session.scalar(select(ServiceAccountModel).where(
        ServiceAccountModel.id == service_account_id,
        ServiceAccountModel.workspace_id == workspace_id,
        ServiceAccountModel.is_active.is_(True),
    ).with_for_update())
    if not account:
        raise StableAPIError(404, "SERVICE_ACCOUNT_NOT_FOUND", "Service account not found")
    normalized = _validate_scopes(scopes)
    credential_id = UUID(bytes=secrets.token_bytes(16), version=4)
    secret = secrets.token_urlsafe(32)
    prefix = f"bws_{credential_id.hex}"
    token = f"{prefix}.{secret}"
    credential = ApiCredentialModel(
        id=credential_id, workspace_id=workspace_id, service_account_id=account.id,
        key_prefix=prefix, secret_digest=_digest(token), created_by=actor.user_id,
    )
    session.add(credential); await session.flush()
    session.add_all(ApiCredentialScopeModel(credential_id=credential.id, scope=scope) for scope in normalized)
    if rotate_credential_id is not None:
        previous = await session.scalar(select(ApiCredentialModel).where(
            ApiCredentialModel.id == rotate_credential_id,
            ApiCredentialModel.workspace_id == workspace_id,
            ApiCredentialModel.service_account_id == account.id,
        ).with_for_update())
        if not previous:
            raise StableAPIError(404, "CREDENTIAL_NOT_FOUND", "Credential not found")
        previous.revoked_at = get_current_utc_datetime()
        append_audit_event(
            session, workspace_id=workspace_id, actor_id=actor.user_id,
            event_type="credential.revoked", subject_type="credential", subject_id=previous.id,
            metadata={"reason": "rotation"},
        )
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="credential.created", subject_type="credential", subject_id=credential.id,
        metadata={"scopeCount": len(normalized)},
    )
    await session.commit(); await session.refresh(credential)
    return credential, token


async def revoke_credential(session: AsyncSession, *, actor, workspace_id: UUID, credential_id: UUID) -> None:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.CREDENTIALS_MANAGE)
    credential = await session.scalar(select(ApiCredentialModel).where(
        ApiCredentialModel.id == credential_id,
        ApiCredentialModel.workspace_id == workspace_id,
    ).with_for_update())
    if not credential:
        raise StableAPIError(404, "CREDENTIAL_NOT_FOUND", "Credential not found")
    if credential.revoked_at is None:
        credential.revoked_at = get_current_utc_datetime()
        append_audit_event(
            session, workspace_id=workspace_id, actor_id=actor.user_id,
            event_type="credential.revoked", subject_type="credential", subject_id=credential.id,
        )
        await session.commit()


async def set_service_account_active(
    session: AsyncSession, *, actor, workspace_id: UUID,
    service_account_id: UUID, is_active: bool,
) -> ServiceAccountModel:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.CREDENTIALS_MANAGE)
    account = await session.scalar(select(ServiceAccountModel).where(
        ServiceAccountModel.id == service_account_id,
        ServiceAccountModel.workspace_id == workspace_id,
    ).with_for_update())
    if not account:
        raise StableAPIError(404, "SERVICE_ACCOUNT_NOT_FOUND", "Service account not found")
    account.is_active = is_active
    if not is_active:
        credentials = list((await session.scalars(select(ApiCredentialModel).where(
            ApiCredentialModel.workspace_id == workspace_id,
            ApiCredentialModel.service_account_id == account.id,
            ApiCredentialModel.revoked_at.is_(None),
        ).with_for_update())).all())
        now = get_current_utc_datetime()
        for credential in credentials:
            credential.revoked_at = now
            append_audit_event(
                session, workspace_id=workspace_id, actor_id=actor.user_id,
                event_type="credential.revoked", subject_type="credential", subject_id=credential.id,
                metadata={"reason": "service-account-disabled"},
            )
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="service_account.enabled" if is_active else "service_account.disabled",
        subject_type="service_account", subject_id=account.id,
    )
    await session.commit(); await session.refresh(account)
    return account


def _credential_id(token: str) -> UUID | None:
    try:
        prefix, _secret = token.split(".", 1)
        if not prefix.startswith("bws_"): return None
        return UUID(hex=prefix[4:])
    except (ValueError, AttributeError):
        return None


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def verify_service_credential(session: AsyncSession, token: str) -> VerifiedServiceCredential | None:
    credential_id = _credential_id(token)
    if credential_id is None:
        return None
    credential = await session.get(ApiCredentialModel, credential_id)
    if not credential or credential.revoked_at is not None or not hmac.compare_digest(credential.secret_digest, _digest(token)):
        LOGGER.warning("[workspace.credential] verification_failed category=missing_revoked_or_digest")
        return None
    if credential.expires_at is not None and _aware(credential.expires_at) <= get_current_utc_datetime():
        LOGGER.warning("[workspace.credential] verification_failed category=expired workspace_id=%s", credential.workspace_id)
        return None
    account = await session.get(ServiceAccountModel, credential.service_account_id)
    if not account or not account.is_active or account.workspace_id != credential.workspace_id:
        LOGGER.warning("[workspace.credential] verification_failed category=account_binding workspace_id=%s", credential.workspace_id)
        return None
    scopes = frozenset((await session.scalars(select(ApiCredentialScopeModel.scope).where(
        ApiCredentialScopeModel.credential_id == credential.id
    ))).all())
    if not scopes or not scopes.issubset(SERVICE_ACCOUNT_SCOPES):
        LOGGER.warning("[workspace.credential] verification_failed category=scopes workspace_id=%s", credential.workspace_id)
        return None
    return VerifiedServiceCredential(
        credential_id=credential.id, workspace_id=credential.workspace_id,
        service_account_id=account.id, service_account_name=account.name, scopes=scopes,
    )

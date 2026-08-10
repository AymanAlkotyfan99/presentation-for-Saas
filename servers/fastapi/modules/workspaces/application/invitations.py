from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from models.sql.user import User
from modules.workspaces.application.audit import append_audit_event
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import MembershipStatus, Permission, Role
from modules.workspaces.persistence.models import InvitationModel, MembershipModel
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime


MAX_INVITATION_LIFETIME = timedelta(days=7)
LOGGER = logging.getLogger(__name__)


def _digest(token: str) -> str:
    pepper = os.getenv("WORKSPACE_TOKEN_PEPPER", "").encode()
    return hmac.new(pepper, token.encode(), hashlib.sha256).hexdigest()


async def create_invitation(
    session: AsyncSession, *, actor, workspace_id: UUID,
    invited_identity: str, role: Role,
) -> tuple[InvitationModel, str]:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.INVITATIONS_MANAGE)
    identity = invited_identity.strip().casefold()
    if not 3 <= len(identity) <= 128:
        raise StableAPIError(422, "INVITATION_IDENTITY_INVALID", "Invitation identity is invalid")
    if role not in {Role.ADMIN, Role.EDITOR, Role.VIEWER}:
        raise StableAPIError(422, "INVITATION_ROLE_INVALID", "Invitation cannot grant this role")
    invitation_id = UUID(bytes=secrets.token_bytes(16), version=4)
    secret = secrets.token_urlsafe(32)
    token = f"bwi_{invitation_id.hex}.{secret}"
    invitation = InvitationModel(
        id=invitation_id, workspace_id=workspace_id, invited_identity=identity,
        role=role, token_digest=_digest(token), created_by=actor.user_id,
        expires_at=get_current_utc_datetime() + MAX_INVITATION_LIFETIME,
    )
    session.add(invitation)
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="invitation.created", subject_type="invitation", subject_id=invitation.id,
        metadata={"newRole": role.value},
    )
    await session.commit(); await session.refresh(invitation)
    return invitation, token


def _parse_token(token: str) -> UUID | None:
    try:
        prefix, _secret = token.split(".", 1)
        if not prefix.startswith("bwi_"): return None
        return UUID(hex=prefix[4:])
    except (ValueError, AttributeError):
        return None


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def accept_invitation(
    session: AsyncSession, *, user: User, token: str,
    expected_workspace_id: UUID | None = None,
) -> MembershipModel:
    invitation_id = _parse_token(token)
    invalid = StableAPIError(404, "INVITATION_INVALID", "Invitation is invalid or unavailable")
    if invitation_id is None:
        LOGGER.warning("[workspace.invitation] acceptance_denied state=invalid actor_id=%s", user.id)
        raise invalid
    invitation = await session.scalar(select(InvitationModel).where(InvitationModel.id == invitation_id).with_for_update())
    if invitation is None or not hmac.compare_digest(invitation.token_digest, _digest(token)):
        LOGGER.warning("[workspace.invitation] acceptance_denied state=invalid actor_id=%s", user.id)
        raise invalid
    if expected_workspace_id is not None and invitation.workspace_id != expected_workspace_id:
        raise invalid
    if invitation.revoked_at is not None:
        raise StableAPIError(410, "INVITATION_REVOKED", "Invitation is no longer available")
    if invitation.accepted_at is not None:
        raise StableAPIError(409, "INVITATION_ALREADY_USED", "Invitation has already been used")
    if _aware(invitation.expires_at) <= get_current_utc_datetime():
        raise StableAPIError(410, "INVITATION_EXPIRED", "Invitation has expired")
    if invitation.invited_identity != user.username.strip().casefold():
        LOGGER.warning("[workspace.invitation] acceptance_denied state=identity_mismatch actor_id=%s", user.id)
        raise invalid
    membership = await session.scalar(select(MembershipModel).where(
        MembershipModel.workspace_id == invitation.workspace_id,
        MembershipModel.user_id == user.id,
    ).with_for_update())
    if membership is None:
        membership = MembershipModel(
            workspace_id=invitation.workspace_id, user_id=user.id,
            role=invitation.role, status=MembershipStatus.ACTIVE,
        )
        session.add(membership)
        append_audit_event(
            session, workspace_id=invitation.workspace_id, actor_id=user.id,
            event_type="membership.added", subject_type="membership", subject_id=membership.id,
            metadata={"newRole": invitation.role.value},
        )
    else:
        membership.status = MembershipStatus.ACTIVE
        membership.role = invitation.role
        membership.permission_overrides = []
    invitation.accepted_at = get_current_utc_datetime(); invitation.accepted_by = user.id
    invitation_id = invitation.id
    append_audit_event(
        session, workspace_id=invitation.workspace_id, actor_id=user.id,
        event_type="invitation.accepted", subject_type="membership", subject_id=membership.id,
        metadata={"newRole": membership.role.value},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        # A concurrent accept can race only on databases without effective
        # row locks. Convert the uniqueness winner into the same safe replay
        # response instead of leaking a database error.
        await session.rollback()
        latest = await session.get(InvitationModel, invitation_id)
        if latest is not None and latest.accepted_at is not None:
            raise StableAPIError(409, "INVITATION_ALREADY_USED", "Invitation has already been used") from exc
        raise invalid from exc
    await session.refresh(membership)
    return membership


async def revoke_invitation(session: AsyncSession, *, actor, workspace_id: UUID, invitation_id: UUID) -> None:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.INVITATIONS_MANAGE)
    invitation = await session.scalar(select(InvitationModel).where(
        InvitationModel.id == invitation_id, InvitationModel.workspace_id == workspace_id,
    ).with_for_update())
    if not invitation:
        raise StableAPIError(404, "INVITATION_NOT_FOUND", "Invitation not found")
    if invitation.accepted_at is not None:
        raise StableAPIError(409, "INVITATION_ALREADY_USED", "Invitation has already been used")
    if invitation.revoked_at is None:
        invitation.revoked_at = get_current_utc_datetime()
        append_audit_event(
            session, workspace_id=workspace_id, actor_id=actor.user_id,
            event_type="invitation.revoked", subject_type="invitation", subject_id=invitation.id,
        )
        await session.commit()

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.user import User
from modules.workspaces.application.audit import append_audit_event
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import MembershipStatus, Permission, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime


async def create_workspace(session: AsyncSession, *, actor, name: str) -> WorkspaceModel:
    if actor.user_id is None:
        raise StableAPIError(403, "WORKSPACE_USER_REQUIRED", "A user session is required")
    candidate = name.strip()
    if not 1 <= len(candidate) <= 160:
        raise StableAPIError(422, "WORKSPACE_NAME_INVALID", "Workspace name must contain 1 to 160 characters")
    workspace = WorkspaceModel(name=candidate, is_personal=False, created_by=actor.user_id)
    session.add(workspace); await session.flush()
    session.add(MembershipModel(
        workspace_id=workspace.id, user_id=actor.user_id,
        role=Role.OWNER, status=MembershipStatus.ACTIVE,
    ))
    append_audit_event(
        session, workspace_id=workspace.id, actor_id=actor.user_id,
        event_type="workspace.created", subject_type="workspace", subject_id=workspace.id,
    )
    await session.commit(); await session.refresh(workspace)
    return workspace


async def update_member_role(
    session: AsyncSession, *, actor, workspace_id: UUID, user_id: UUID,
    role: Role, finance_review: bool | None = None,
) -> MembershipModel:
    actor_membership = await authorize_workspace(
        session, principal=actor, workspace_id=workspace_id, permission=Permission.MEMBERS_MANAGE,
    )
    membership = await session.scalar(select(MembershipModel).where(
        MembershipModel.workspace_id == workspace_id,
        MembershipModel.user_id == user_id,
    ).with_for_update())
    if not membership:
        raise StableAPIError(404, "MEMBERSHIP_NOT_FOUND", "Membership not found")
    if membership.role == Role.OWNER or role == Role.OWNER:
        raise StableAPIError(409, "OWNER_TRANSFER_REQUIRED", "Use ownership transfer for the owner role")
    if role not in {Role.ADMIN, Role.EDITOR, Role.VIEWER}:
        raise StableAPIError(422, "MEMBERSHIP_ROLE_INVALID", "Membership role is invalid")
    if finance_review is not None and actor_membership.role != Role.OWNER:
        raise StableAPIError(403, "FINANCE_PERMISSION_OWNER_REQUIRED", "Only the workspace owner can change finance review")
    previous = membership.role
    membership.role = role
    if finance_review is not None:
        values = set(membership.permission_overrides)
        if finance_review: values.add(Permission.FINANCE_REVIEW.value)
        else: values.discard(Permission.FINANCE_REVIEW.value)
        membership.permission_overrides = sorted(values)
        append_audit_event(
            session, workspace_id=workspace_id, actor_id=actor.user_id,
            event_type="finance.permission.changed", subject_type="membership", subject_id=membership.id,
            metadata={"enabled": finance_review},
        )
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="membership.role.changed", subject_type="membership", subject_id=membership.id,
        metadata={"previousRole": previous.value, "newRole": role.value},
    )
    await session.commit(); await session.refresh(membership)
    return membership


async def remove_member(session: AsyncSession, *, actor, workspace_id: UUID, user_id: UUID) -> None:
    await authorize_workspace(session, principal=actor, workspace_id=workspace_id, permission=Permission.MEMBERS_MANAGE)
    membership = await session.scalar(select(MembershipModel).where(
        MembershipModel.workspace_id == workspace_id,
        MembershipModel.user_id == user_id,
    ).with_for_update())
    if not membership:
        raise StableAPIError(404, "MEMBERSHIP_NOT_FOUND", "Membership not found")
    if membership.role == Role.OWNER:
        raise StableAPIError(409, "LAST_OWNER_REQUIRED", "The workspace owner cannot be removed")
    await session.delete(membership)
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="membership.removed", subject_type="user", subject_id=user_id,
    )
    await session.commit()


async def transfer_ownership(session: AsyncSession, *, actor, workspace_id: UUID, recipient_id: UUID) -> None:
    actor_membership = await authorize_workspace(
        session, principal=actor, workspace_id=workspace_id, permission=Permission.OWNER_TRANSFER,
    )
    workspace = await session.scalar(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id).with_for_update())
    if not workspace or workspace.is_personal:
        raise StableAPIError(409, "PERSONAL_WORKSPACE_TRANSFER_FORBIDDEN", "Personal workspace ownership cannot be transferred")
    # PostgreSQL locks the selected row. SQLite ignores FOR UPDATE, so this
    # bounded write acquires its database write lock before membership state is
    # read. Either way concurrent transfers serialize before choosing owners.
    workspace.updated_at = get_current_utc_datetime()
    await session.flush()
    memberships = list((await session.scalars(select(MembershipModel).where(
        MembershipModel.workspace_id == workspace_id,
        MembershipModel.status == MembershipStatus.ACTIVE,
    ).with_for_update())).all())
    owners = [membership for membership in memberships if membership.role == Role.OWNER]
    if len(owners) != 1 or owners[0].id != actor_membership.id:
        raise StableAPIError(409, "WORKSPACE_OWNER_INVARIANT", "Workspace owner invariant is not satisfied")
    recipient = next((membership for membership in memberships if membership.user_id == recipient_id), None)
    if recipient is None:
        raise StableAPIError(404, "MEMBERSHIP_NOT_FOUND", "Recipient must be an active member")
    owners[0].role = Role.ADMIN
    recipient.role = Role.OWNER
    recipient.permission_overrides = []
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor.user_id,
        event_type="workspace.owner.transferred", subject_type="user", subject_id=recipient_id,
    )
    await session.commit()


async def resolve_user(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username.strip()))

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import or_

from modules.workspaces.domain.models import MembershipStatus, Permission
from modules.workspaces.domain.policies import permissions_for_role, scope_allows
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel
from utils.api_errors import StableAPIError
from api.v1.auth.context import get_current_owner_id, get_current_service_account_id, get_current_workspace_id
from utils.architecture_flags import legacy_owner_bridge_enabled, workspace_rbac_enforcement_enabled


LOGGER = logging.getLogger(__name__)


async def active_membership(session: AsyncSession, workspace_id: UUID, user_id: UUID) -> MembershipModel | None:
    return await session.scalar(select(MembershipModel).where(
        MembershipModel.workspace_id == workspace_id,
        MembershipModel.user_id == user_id,
        MembershipModel.status == MembershipStatus.ACTIVE,
    ))


async def authorize_workspace(
    session: AsyncSession,
    *,
    principal,
    workspace_id: UUID,
    permission: Permission,
    resource_workspace_id: UUID | None = None,
) -> MembershipModel | None:
    """Authorize identity, tenant membership, resource binding, then capability."""
    if resource_workspace_id is not None and resource_workspace_id != workspace_id:
        LOGGER.warning(
            "[workspace.authz] denied category=resource_binding workspace_id=%s resource_workspace_id=%s actor_id=%s",
            workspace_id, resource_workspace_id, principal.user_id,
        )
        raise StableAPIError(404, "RESOURCE_NOT_FOUND", "Resource not found")
    if principal.method == "service_account":
        if principal.workspace_id != workspace_id or not scope_allows(principal.scopes, permission):
            LOGGER.warning(
                "[workspace.authz] denied category=service_scope workspace_id=%s service_account_id=%s permission=%s",
                workspace_id, principal.service_account_id, permission.value,
            )
            raise StableAPIError(403, "WORKSPACE_PERMISSION_DENIED", "Workspace permission denied")
        return None
    if principal.user_id is None:
        raise StableAPIError(401, "AUTHENTICATION_REQUIRED", "Authentication required")
    membership = await active_membership(session, workspace_id, principal.user_id)
    if membership is None:
        LOGGER.warning(
            "[workspace.authz] denied category=membership workspace_id=%s actor_id=%s",
            workspace_id, principal.user_id,
        )
        raise StableAPIError(404, "WORKSPACE_NOT_FOUND", "Workspace not found")
    if permission not in permissions_for_role(membership.role, membership.permission_overrides):
        LOGGER.warning(
            "[workspace.authz] denied category=permission workspace_id=%s actor_id=%s role=%s permission=%s",
            workspace_id, principal.user_id, membership.role.value, permission.value,
        )
        raise StableAPIError(403, "WORKSPACE_PERMISSION_DENIED", "Workspace permission denied", params={"permission": permission.value})
    return membership


async def validated_workspace_selection(
    session: AsyncSession,
    *,
    user_id: UUID,
    requested_workspace_id: UUID | None,
    explicit: bool,
) -> tuple[WorkspaceModel, MembershipModel]:
    if requested_workspace_id is not None:
        membership = await active_membership(session, requested_workspace_id, user_id)
        workspace = await session.get(WorkspaceModel, requested_workspace_id) if membership else None
        if membership and workspace:
            return workspace, membership
        if explicit:
            raise StableAPIError(404, "WORKSPACE_NOT_FOUND", "Workspace not found")
    workspace = await session.scalar(select(WorkspaceModel).where(WorkspaceModel.personal_owner_id == user_id))
    if not workspace:
        raise StableAPIError(409, "PERSONAL_WORKSPACE_REQUIRED", "Personal workspace is not provisioned")
    membership = await active_membership(session, workspace.id, user_id)
    if not membership:
        raise StableAPIError(409, "PERSONAL_WORKSPACE_MEMBERSHIP_REQUIRED", "Personal workspace membership is not provisioned")
    return workspace, membership


def resource_scope_predicate(model):
    """Central predicate for owner/workspace dual-enforcement in DML queries."""
    workspace_id = get_current_workspace_id()
    owner_id = get_current_owner_id()
    if workspace_rbac_enforcement_enabled() and workspace_id is not None:
        if legacy_owner_bridge_enabled() and owner_id is not None and get_current_service_account_id() is None:
            return or_(model.workspace_id == workspace_id, model.workspace_id.is_(None) & (model.owner_id == owner_id))
        return model.workspace_id == workspace_id
    return model.owner_id.is_(None) if owner_id is None else model.owner_id == owner_id

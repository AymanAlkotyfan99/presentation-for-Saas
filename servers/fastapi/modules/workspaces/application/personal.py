from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.user import User
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel
from modules.workspaces.application.audit import append_audit_event


async def ensure_personal_workspace(session: AsyncSession, user: User) -> WorkspaceModel:
    """Create the deterministic user-id workspace and owner membership idempotently."""
    workspace = await session.scalar(select(WorkspaceModel).where(WorkspaceModel.personal_owner_id == user.id))
    if workspace is None:
        # Reusing the user UUID in a separate table gives migrations and runtime
        # retries a portable deterministic identity without database extensions.
        workspace = WorkspaceModel(
            id=user.id,
            name=user.username or "Personal workspace",
            is_personal=True,
            personal_owner_id=user.id, created_by=user.id,
        )
        session.add(workspace)
        await session.flush()
        append_audit_event(
            session, workspace_id=workspace.id, actor_id=user.id,
            event_type="workspace.created", subject_type="workspace", subject_id=workspace.id,
            metadata={"reason": "personal-provisioning"},
        )
    membership = await session.scalar(select(MembershipModel).where(
        MembershipModel.workspace_id == workspace.id,
        MembershipModel.user_id == user.id,
    ))
    if membership is None:
        session.add(MembershipModel(
            id=user.id, workspace_id=workspace.id, user_id=user.id,
            role=Role.OWNER, status=MembershipStatus.ACTIVE,
        ))
        await session.flush()
    elif membership.status != MembershipStatus.ACTIVE or membership.role != Role.OWNER:
        membership.status = MembershipStatus.ACTIVE
        membership.role = Role.OWNER
        membership.permission_overrides = []
        await session.flush()
    return workspace

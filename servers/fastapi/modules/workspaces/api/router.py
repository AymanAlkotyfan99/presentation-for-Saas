from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.operation_security import operation_guard
from api.v1.auth.principal import principal_from_request
from models.sql.user import User
from modules.workspaces.application.audit import append_audit_event
from modules.workspaces.application.authorization import authorize_workspace, validated_workspace_selection
from modules.workspaces.application.credentials import create_service_account, issue_credential, revoke_credential, set_service_account_active
from modules.workspaces.application.invitations import accept_invitation, create_invitation, revoke_invitation
from modules.workspaces.application.memberships import create_workspace, remove_member, transfer_ownership, update_member_role
from modules.workspaces.domain.models import Permission, Role
from modules.workspaces.domain.policies import permissions_for_role
from modules.workspaces.persistence.models import (
    ApiCredentialModel, ApiCredentialScopeModel, AuditEventModel, InvitationModel,
    MembershipModel, ServiceAccountModel, WorkspaceModel,
)
from services.database import get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import invitations_enabled, service_accounts_enabled, workspaces_enabled


CURRENT_WORKSPACE_COOKIE = "bayanly_workspace"


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


class WorkspaceCreate(CamelModel):
    name: str = Field(min_length=1, max_length=160)


class WorkspaceUpdate(WorkspaceCreate): pass


class CurrentWorkspaceUpdate(CamelModel):
    workspace_id: UUID


class InvitationCreate(CamelModel):
    invited_identity: str = Field(min_length=3, max_length=128)
    role: Role


class InvitationAccept(CamelModel):
    token: str = Field(min_length=20, max_length=256)
    workspace_id: UUID | None = None


class MemberUpdate(CamelModel):
    role: Role
    finance_review: bool | None = None


class OwnershipTransfer(CamelModel):
    recipient_id: UUID


class ServiceAccountCreate(CamelModel):
    name: str = Field(min_length=1, max_length=128)


class ServiceAccountUpdate(CamelModel):
    is_active: bool


class CredentialCreate(CamelModel):
    scopes: list[str] = Field(min_length=1, max_length=16)
    rotate_credential_id: UUID | None = None


def _flag(value: bool, code: str) -> None:
    if not value:
        raise StableAPIError(404, code, "Workspace feature is not enabled")


def _require_workspaces_enabled() -> None:
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")


WORKSPACES_ROUTER = APIRouter(
    prefix="/api/v1/workspaces", tags=["Workspaces"],
    dependencies=[Depends(_require_workspaces_enabled)],
)


def _workspace_json(workspace: WorkspaceModel, membership: MembershipModel | None = None):
    return {
        "id": str(workspace.id), "name": workspace.name, "isPersonal": workspace.is_personal,
        "role": membership.role.value if membership else None,
        "permissions": sorted(value.value for value in permissions_for_role(membership.role, membership.permission_overrides)) if membership else [],
        "createdAt": workspace.created_at.isoformat(),
    }


@WORKSPACES_ROUTER.post("", status_code=201)
async def create_workspace_endpoint(request: Request, payload: Annotated[WorkspaceCreate, Body()], session: AsyncSession = Depends(get_async_session)):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    workspace = await create_workspace(session, actor=principal_from_request(request), name=payload.name)
    membership = await session.scalar(select(MembershipModel).where(MembershipModel.workspace_id == workspace.id))
    return _workspace_json(workspace, membership)


@WORKSPACES_ROUTER.get("")
async def list_workspaces(request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    principal = principal_from_request(request)
    if principal.user_id is None:
        workspace = await session.get(WorkspaceModel, principal.workspace_id)
        return [_workspace_json(workspace)] if workspace else []
    rows = (await session.execute(
        select(WorkspaceModel, MembershipModel).join(MembershipModel, MembershipModel.workspace_id == WorkspaceModel.id).where(
            MembershipModel.user_id == principal.user_id,
            MembershipModel.status == "ACTIVE",
        ).order_by(WorkspaceModel.is_personal.desc(), WorkspaceModel.name)
    )).all()
    return [_workspace_json(workspace, membership) for workspace, membership in rows]


@WORKSPACES_ROUTER.get("/current")
async def get_current_workspace(request: Request):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    workspace = getattr(request.state, "workspace", None)
    membership = getattr(request.state, "workspace_membership", None)
    if not workspace:
        raise StableAPIError(409, "WORKSPACE_CONTEXT_REQUIRED", "Current workspace is unavailable")
    return _workspace_json(workspace, membership)


@WORKSPACES_ROUTER.put("/current")
async def set_current_workspace(
    request: Request, response: Response, payload: Annotated[CurrentWorkspaceUpdate, Body()],
    session: AsyncSession = Depends(get_async_session),
):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    principal = principal_from_request(request)
    if principal.user_id is None:
        raise StableAPIError(403, "WORKSPACE_USER_REQUIRED", "A user session is required")
    workspace, membership = await validated_workspace_selection(
        session, user_id=principal.user_id, requested_workspace_id=payload.workspace_id, explicit=True,
    )
    response.set_cookie(
        CURRENT_WORKSPACE_COOKIE, str(workspace.id), httponly=True,
        secure=request.url.scheme == "https", samesite="strict", max_age=60 * 60 * 24 * 365,
    )
    return _workspace_json(workspace, membership)


@WORKSPACES_ROUTER.post("/invitations/accept")
async def accept_invitation_endpoint(
    request: Request, payload: Annotated[InvitationAccept, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(workspaces_enabled() and invitations_enabled(), "INVITATIONS_DISABLED")
    principal = principal_from_request(request)
    user = await session.get(User, principal.user_id) if principal.user_id else None
    if not user:
        raise StableAPIError(403, "WORKSPACE_USER_REQUIRED", "A user session is required")
    async with operation_guard("workspace_invitation"):
        membership = await accept_invitation(session, user=user, token=payload.token, expected_workspace_id=payload.workspace_id)
    return {"workspaceId": str(membership.workspace_id), "role": membership.role.value, "status": membership.status.value}


@WORKSPACES_ROUTER.get("/{workspace_id}")
async def read_workspace(workspace_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    membership = await authorize_workspace(session, principal=principal_from_request(request), workspace_id=workspace_id, permission=Permission.WORKSPACE_VIEW)
    workspace = await session.get(WorkspaceModel, workspace_id)
    if not workspace: raise StableAPIError(404, "WORKSPACE_NOT_FOUND", "Workspace not found")
    return _workspace_json(workspace, membership)


@WORKSPACES_ROUTER.patch("/{workspace_id}")
async def update_workspace_endpoint(
    workspace_id: UUID, request: Request, payload: Annotated[WorkspaceUpdate, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(workspaces_enabled(), "WORKSPACES_DISABLED")
    principal = principal_from_request(request)
    await authorize_workspace(session, principal=principal, workspace_id=workspace_id, permission=Permission.WORKSPACE_UPDATE)
    workspace = await session.get(WorkspaceModel, workspace_id)
    if not workspace: raise StableAPIError(404, "WORKSPACE_NOT_FOUND", "Workspace not found")
    workspace.name = payload.name.strip()
    append_audit_event(session, workspace_id=workspace_id, actor_id=principal.user_id, event_type="workspace.updated", subject_type="workspace", subject_id=workspace_id)
    await session.commit(); await session.refresh(workspace)
    return _workspace_json(workspace)


@WORKSPACES_ROUTER.get("/{workspace_id}/members")
async def list_members(workspace_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = principal_from_request(request)
    await authorize_workspace(session, principal=principal, workspace_id=workspace_id, permission=Permission.MEMBERS_VIEW)
    rows = (await session.execute(select(MembershipModel, User).join(User, User.id == MembershipModel.user_id).where(
        MembershipModel.workspace_id == workspace_id
    ).order_by(MembershipModel.created_at))).all()
    return [{
        "id": str(membership.id), "userId": str(user.id), "username": user.username,
        "role": membership.role.value, "status": membership.status.value,
        "financeReview": Permission.FINANCE_REVIEW.value in membership.permission_overrides,
    } for membership, user in rows]


@WORKSPACES_ROUTER.patch("/{workspace_id}/members/{user_id}")
async def update_member_endpoint(
    workspace_id: UUID, user_id: UUID, request: Request, payload: Annotated[MemberUpdate, Body()], session: AsyncSession = Depends(get_async_session),
):
    membership = await update_member_role(
        session, actor=principal_from_request(request), workspace_id=workspace_id,
        user_id=user_id, role=payload.role, finance_review=payload.finance_review,
    )
    return {"userId": str(membership.user_id), "role": membership.role.value, "financeReview": Permission.FINANCE_REVIEW.value in membership.permission_overrides}


@WORKSPACES_ROUTER.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member_endpoint(workspace_id: UUID, user_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    await remove_member(session, actor=principal_from_request(request), workspace_id=workspace_id, user_id=user_id)


@WORKSPACES_ROUTER.post("/{workspace_id}/ownership-transfer", status_code=204)
async def transfer_endpoint(
    workspace_id: UUID, request: Request, payload: Annotated[OwnershipTransfer, Body()], session: AsyncSession = Depends(get_async_session),
):
    await transfer_ownership(session, actor=principal_from_request(request), workspace_id=workspace_id, recipient_id=payload.recipient_id)


@WORKSPACES_ROUTER.get("/{workspace_id}/invitations")
async def list_invitations(workspace_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(invitations_enabled(), "INVITATIONS_DISABLED")
    await authorize_workspace(session, principal=principal_from_request(request), workspace_id=workspace_id, permission=Permission.INVITATIONS_MANAGE)
    invitations = list((await session.scalars(select(InvitationModel).where(InvitationModel.workspace_id == workspace_id).order_by(InvitationModel.created_at.desc()))).all())
    return [{
        "id": str(item.id), "invitedIdentity": item.invited_identity, "role": item.role.value,
        "expiresAt": item.expires_at.isoformat(), "acceptedAt": item.accepted_at.isoformat() if item.accepted_at else None,
        "revokedAt": item.revoked_at.isoformat() if item.revoked_at else None,
    } for item in invitations]


@WORKSPACES_ROUTER.post("/{workspace_id}/invitations", status_code=201)
async def invite_endpoint(
    workspace_id: UUID, request: Request, payload: Annotated[InvitationCreate, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(invitations_enabled(), "INVITATIONS_DISABLED")
    async with operation_guard("workspace_invitation"):
        invitation, token = await create_invitation(
            session, actor=principal_from_request(request), workspace_id=workspace_id,
            invited_identity=payload.invited_identity, role=payload.role,
        )
    return {"id": str(invitation.id), "token": token, "expiresAt": invitation.expires_at.isoformat()}


@WORKSPACES_ROUTER.delete("/{workspace_id}/invitations/{invitation_id}", status_code=204)
async def revoke_invitation_endpoint(workspace_id: UUID, invitation_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(invitations_enabled(), "INVITATIONS_DISABLED")
    await revoke_invitation(session, actor=principal_from_request(request), workspace_id=workspace_id, invitation_id=invitation_id)


@WORKSPACES_ROUTER.post("/{workspace_id}/service-accounts", status_code=201)
async def service_account_endpoint(
    workspace_id: UUID, request: Request, payload: Annotated[ServiceAccountCreate, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(service_accounts_enabled(), "SERVICE_ACCOUNTS_DISABLED")
    account = await create_service_account(session, actor=principal_from_request(request), workspace_id=workspace_id, name=payload.name)
    return {"id": str(account.id), "name": account.name, "isActive": account.is_active}


@WORKSPACES_ROUTER.get("/{workspace_id}/service-accounts")
async def list_service_accounts(workspace_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(service_accounts_enabled(), "SERVICE_ACCOUNTS_DISABLED")
    await authorize_workspace(session, principal=principal_from_request(request), workspace_id=workspace_id, permission=Permission.CREDENTIALS_MANAGE)
    accounts = list((await session.scalars(select(ServiceAccountModel).where(
        ServiceAccountModel.workspace_id == workspace_id,
    ).order_by(ServiceAccountModel.created_at))).all())
    response = []
    for account in accounts:
        credentials = list((await session.scalars(select(ApiCredentialModel).where(
            ApiCredentialModel.workspace_id == workspace_id,
            ApiCredentialModel.service_account_id == account.id,
        ).order_by(ApiCredentialModel.created_at.desc()))).all())
        rendered_credentials = []
        for credential in credentials:
            scopes = list((await session.scalars(select(ApiCredentialScopeModel.scope).where(
                ApiCredentialScopeModel.credential_id == credential.id,
            ))).all())
            rendered_credentials.append({
                "id": str(credential.id), "keyPrefix": credential.key_prefix,
                "scopes": sorted(scopes), "createdAt": credential.created_at.isoformat(),
                "expiresAt": credential.expires_at.isoformat() if credential.expires_at else None,
                "revokedAt": credential.revoked_at.isoformat() if credential.revoked_at else None,
            })
        response.append({"id": str(account.id), "name": account.name, "isActive": account.is_active, "credentials": rendered_credentials})
    return response


@WORKSPACES_ROUTER.patch("/{workspace_id}/service-accounts/{service_account_id}")
async def update_service_account(
    workspace_id: UUID, service_account_id: UUID, request: Request,
    payload: Annotated[ServiceAccountUpdate, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(service_accounts_enabled(), "SERVICE_ACCOUNTS_DISABLED")
    account = await set_service_account_active(
        session, actor=principal_from_request(request), workspace_id=workspace_id,
        service_account_id=service_account_id, is_active=payload.is_active,
    )
    return {"id": str(account.id), "name": account.name, "isActive": account.is_active}


@WORKSPACES_ROUTER.post("/{workspace_id}/service-accounts/{service_account_id}/credentials", status_code=201)
async def credential_endpoint(
    workspace_id: UUID, service_account_id: UUID, request: Request,
    payload: Annotated[CredentialCreate, Body()], session: AsyncSession = Depends(get_async_session),
):
    _flag(service_accounts_enabled(), "SERVICE_ACCOUNTS_DISABLED")
    async with operation_guard("workspace_credential"):
        credential, token = await issue_credential(
            session, actor=principal_from_request(request), workspace_id=workspace_id,
            service_account_id=service_account_id, scopes=payload.scopes,
            rotate_credential_id=payload.rotate_credential_id,
        )
    return {"id": str(credential.id), "token": token, "keyPrefix": credential.key_prefix, "scopes": sorted(set(payload.scopes))}


@WORKSPACES_ROUTER.delete("/{workspace_id}/credentials/{credential_id}", status_code=204)
async def revoke_credential_endpoint(workspace_id: UUID, credential_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _flag(service_accounts_enabled(), "SERVICE_ACCOUNTS_DISABLED")
    await revoke_credential(session, actor=principal_from_request(request), workspace_id=workspace_id, credential_id=credential_id)


@WORKSPACES_ROUTER.get("/{workspace_id}/audit-events")
async def audit_events(workspace_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    await authorize_workspace(session, principal=principal_from_request(request), workspace_id=workspace_id, permission=Permission.AUDIT_READ)
    events = list((await session.scalars(select(AuditEventModel).where(AuditEventModel.workspace_id == workspace_id).order_by(AuditEventModel.created_at.desc()).limit(100))).all())
    return [{
        "id": str(event.id), "eventType": event.event_type, "subjectType": event.subject_type,
        "subjectId": event.subject_id, "safeMetadata": event.safe_metadata,
        "actorId": str(event.actor_id) if event.actor_id else None, "createdAt": event.created_at.isoformat(),
    } for event in events]

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

# Register the repository-wide tenant criteria listeners.
import services.database  # noqa: F401
from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_workspace_id,
    set_current_owner_id,
    set_current_workspace_id,
)
from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from models.sql.image_asset import ImageAsset
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.presentation_revision import PresentationRevisionModel, PresentationRevisionPatchModel
from models.sql.template import TemplateModel
from models.sql.user import User
from modules.presentations.revision_service import RevisionNotFoundError, apply_revision_commands
from modules.workspaces.application.authorization import authorize_workspace, validated_workspace_selection
from modules.workspaces.application.credentials import issue_credential, revoke_credential, set_service_account_active, verify_service_credential
from modules.workspaces.application.invitations import accept_invitation, create_invitation, revoke_invitation
from modules.workspaces.application.memberships import create_workspace, remove_member, transfer_ownership
from modules.workspaces.application.personal import ensure_personal_workspace
from modules.workspaces.domain.models import MembershipStatus, Permission, Role
from modules.workspaces.domain.policies import ROLE_PERMISSIONS, SERVICE_ACCOUNT_SCOPES, permissions_for_role, role_allows, scope_allows
from modules.workspaces.persistence.models import (
    ApiCredentialModel,
    ApiCredentialScopeModel,
    AuditEventModel,
    InvitationModel,
    MembershipModel,
    ServiceAccountModel,
    WorkspaceModel,
)
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime
from utils.architecture_flags import (
    invitations_enabled, legacy_owner_bridge_enabled, service_accounts_enabled,
    workspace_rbac_enforcement_enabled, workspaces_enabled,
)


WORKSPACE_TABLES = (
    User.__table__, WorkspaceModel.__table__, MembershipModel.__table__,
    InvitationModel.__table__, ServiceAccountModel.__table__, ApiCredentialModel.__table__,
    ApiCredentialScopeModel.__table__, AuditEventModel.__table__,
)


async def database(tmp_path, name="workspaces.db", extra=()):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=[*WORKSPACE_TABLES, *extra]))
    return engine, sessions


def principal(user, *, admin=False):
    return SimpleNamespace(
        user_id=user.id, username=user.username, is_admin=admin, method="jwt",
        workspace_id=None, service_account_id=None, scopes=frozenset(),
    )


async def add_user(session, name):
    user = User(username=name, hashed_password="not-a-secret-hash")
    session.add(user)
    await session.flush()
    return user


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_central_rbac_matrix_is_exact_and_deny_by_default(role, permission):
    assert role_allows(role, permission) is (permission in ROLE_PERMISSIONS[role])
    assert permissions_for_role(role, ["unknown:permission"]) == ROLE_PERMISSIONS[role]


def test_sensitive_permissions_and_service_scopes_are_bounded():
    assert Permission.WORKSPACE_DELETE in ROLE_PERMISSIONS[Role.OWNER]
    assert Permission.OWNER_TRANSFER in ROLE_PERMISSIONS[Role.OWNER]
    assert Permission.FINANCE_REVIEW in ROLE_PERMISSIONS[Role.OWNER]
    for role in (Role.ADMIN, Role.EDITOR, Role.VIEWER):
        assert Permission.WORKSPACE_DELETE not in ROLE_PERMISSIONS[role]
        assert Permission.OWNER_TRANSFER not in ROLE_PERMISSIONS[role]
        assert Permission.FINANCE_REVIEW not in ROLE_PERMISSIONS[role]
    assert "credentials:manage" not in SERVICE_ACCOUNT_SCOPES
    assert scope_allows(["presentations:read"], Permission.PRESENTATIONS_READ)
    assert not scope_allows(["workspace:delete"], Permission.WORKSPACE_DELETE)


def test_workspace_rollout_flags_have_safe_defaults(monkeypatch):
    for name in (
        "WORKSPACES_ENABLED", "WORKSPACE_RBAC_ENFORCEMENT_ENABLED",
        "INVITATIONS_ENABLED", "SERVICE_ACCOUNTS_ENABLED", "LEGACY_OWNER_BRIDGE_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    assert not workspaces_enabled()
    assert not workspace_rbac_enforcement_enabled()
    assert not invitations_enabled()
    assert not service_accounts_enabled()
    assert legacy_owner_bridge_enabled()


def test_personal_workspace_provisioning_is_deterministic_atomic_and_idempotent(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            user = await add_user(session, "personal-user")
            first = await ensure_personal_workspace(session, user)
            second = await ensure_personal_workspace(session, user)
            await session.commit()
            assert first.id == second.id == user.id
            assert len((await session.scalars(select(WorkspaceModel))).all()) == 1
            memberships = list((await session.scalars(select(MembershipModel))).all())
            assert len(memberships) == 1
            assert memberships[0].role == Role.OWNER
            events = list((await session.scalars(select(AuditEventModel))).all())
            assert [event.event_type for event in events] == ["workspace.created"]
        await engine.dispose()
    asyncio.run(scenario())


def test_workspace_selection_validates_membership_and_stale_cookie_falls_back(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            user = await add_user(session, "selector")
            personal = await ensure_personal_workspace(session, user)
            await session.commit()
            fallback, membership = await validated_workspace_selection(
                session, user_id=user.id, requested_workspace_id=uuid4(), explicit=False,
            )
            assert fallback.id == personal.id and membership.role == Role.OWNER
            with pytest.raises(StableAPIError) as explicit:
                await validated_workspace_selection(
                    session, user_id=user.id, requested_workspace_id=uuid4(), explicit=True,
                )
            assert explicit.value.code == "WORKSPACE_NOT_FOUND"
        await engine.dispose()
    asyncio.run(scenario())


def test_invitation_security_lifecycle_and_owner_transfer(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            owner = await add_user(session, "owner")
            invited = await add_user(session, "invited")
            wrong = await add_user(session, "wrong")
            await session.commit()
            team = await create_workspace(session, actor=principal(owner), name="Team")

            valid, token = await create_invitation(
                session, actor=principal(owner), workspace_id=team.id,
                invited_identity=invited.username, role=Role.EDITOR,
            )
            assert token.startswith(f"bwi_{valid.id.hex}.")
            assert valid.token_digest not in token and token not in valid.token_digest
            with pytest.raises(StableAPIError) as owner_role:
                await create_invitation(
                    session, actor=principal(owner), workspace_id=team.id,
                    invited_identity=invited.username, role=Role.OWNER,
                )
            assert owner_role.value.code == "INVITATION_ROLE_INVALID"
            with pytest.raises(StableAPIError) as wrong_identity:
                await accept_invitation(session, user=wrong, token=token)
            assert wrong_identity.value.code == "INVITATION_INVALID"
            with pytest.raises(StableAPIError) as wrong_workspace:
                await accept_invitation(session, user=invited, token=token, expected_workspace_id=uuid4())
            assert wrong_workspace.value.code == "INVITATION_INVALID"
            membership = await accept_invitation(session, user=invited, token=token)
            assert membership.role == Role.EDITOR
            with pytest.raises(StableAPIError) as unauthorized:
                await create_invitation(
                    session, actor=principal(invited), workspace_id=team.id,
                    invited_identity=wrong.username, role=Role.VIEWER,
                )
            assert unauthorized.value.code == "WORKSPACE_PERMISSION_DENIED"
            with pytest.raises(StableAPIError) as replay:
                await accept_invitation(session, user=invited, token=token)
            assert replay.value.code == "INVITATION_ALREADY_USED"

            expired, expired_token = await create_invitation(
                session, actor=principal(owner), workspace_id=team.id,
                invited_identity=wrong.username, role=Role.VIEWER,
            )
            expired.expires_at = get_current_utc_datetime() - timedelta(seconds=1)
            await session.commit()
            with pytest.raises(StableAPIError) as expiry:
                await accept_invitation(session, user=wrong, token=expired_token)
            assert expiry.value.code == "INVITATION_EXPIRED"

            revoked, revoked_token = await create_invitation(
                session, actor=principal(owner), workspace_id=team.id,
                invited_identity=wrong.username, role=Role.VIEWER,
            )
            await revoke_invitation(session, actor=principal(owner), workspace_id=team.id, invitation_id=revoked.id)
            with pytest.raises(StableAPIError) as revocation:
                await accept_invitation(session, user=wrong, token=revoked_token)
            assert revocation.value.code == "INVITATION_REVOKED"

            await transfer_ownership(session, actor=principal(owner), workspace_id=team.id, recipient_id=invited.id)
            rows = list((await session.scalars(select(MembershipModel).where(MembershipModel.workspace_id == team.id))).all())
            assert [(row.user_id, row.role) for row in rows if row.role == Role.OWNER] == [(invited.id, Role.OWNER)]
            with pytest.raises(StableAPIError):
                await transfer_ownership(session, actor=principal(owner), workspace_id=team.id, recipient_id=owner.id)
            with pytest.raises(StableAPIError) as last_owner:
                await remove_member(session, actor=principal(invited), workspace_id=team.id, user_id=invited.id)
            assert last_owner.value.code == "LAST_OWNER_REQUIRED"
            events = [event.event_type for event in (await session.scalars(select(AuditEventModel).where(AuditEventModel.workspace_id == team.id))).all()]
            assert {"workspace.created", "invitation.created", "membership.added", "invitation.accepted", "invitation.revoked", "workspace.owner.transferred"}.issubset(events)
            assert all(token not in str(event.safe_metadata) for event in (await session.scalars(select(AuditEventModel))).all())
        await engine.dispose()
    asyncio.run(scenario())


def test_service_credentials_are_hashed_scoped_bound_rotatable_and_revocable(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            owner = await add_user(session, "credential-owner")
            await session.commit()
            team = await create_workspace(session, actor=principal(owner), name="Automation")
            other_team = await create_workspace(session, actor=principal(owner), name="Other automation")
            from modules.workspaces.application.credentials import create_service_account
            account = await create_service_account(session, actor=principal(owner), workspace_id=team.id, name="Exporter")
            credential, token = await issue_credential(
                session, actor=principal(owner), workspace_id=team.id,
                service_account_id=account.id, scopes=["presentations:read", "jobs:read"],
            )
            assert credential.secret_digest not in token and token not in credential.secret_digest
            assert len(credential.secret_digest) == 64
            verified = await verify_service_credential(session, token)
            assert verified and verified.workspace_id == team.id
            assert verified.scopes == frozenset({"presentations:read", "jobs:read"})
            with pytest.raises(StableAPIError) as unknown:
                await issue_credential(session, actor=principal(owner), workspace_id=team.id, service_account_id=account.id, scopes=["unknown:*"],)
            assert unknown.value.code == "CREDENTIAL_SCOPE_INVALID"
            with pytest.raises(StableAPIError) as wrong_workspace:
                await issue_credential(
                    session, actor=principal(owner), workspace_id=other_team.id,
                    service_account_id=account.id, scopes=["assets:read"],
                )
            assert wrong_workspace.value.code == "SERVICE_ACCOUNT_NOT_FOUND"
            replacement, replacement_token = await issue_credential(
                session, actor=principal(owner), workspace_id=team.id,
                service_account_id=account.id, scopes=["assets:read"], rotate_credential_id=credential.id,
            )
            assert await verify_service_credential(session, token) is None
            assert await verify_service_credential(session, replacement_token) is not None
            await revoke_credential(session, actor=principal(owner), workspace_id=team.id, credential_id=replacement.id)
            assert await verify_service_credential(session, replacement_token) is None
            third, third_token = await issue_credential(
                session, actor=principal(owner), workspace_id=team.id,
                service_account_id=account.id, scopes=["templates:read"],
            )
            await set_service_account_active(
                session, actor=principal(owner), workspace_id=team.id,
                service_account_id=account.id, is_active=False,
            )
            assert await verify_service_credential(session, third_token) is None
            assert (await session.get(ApiCredentialModel, third.id)).revoked_at is not None
        await engine.dispose()
    asyncio.run(scenario())


def test_concurrent_owner_transfer_serializes_to_exactly_one_owner(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            owner = await add_user(session, "transfer-owner")
            first = await add_user(session, "transfer-first")
            second = await add_user(session, "transfer-second")
            await session.commit()
            team = await create_workspace(session, actor=principal(owner), name="Transfer race")
            session.add_all([
                MembershipModel(workspace_id=team.id, user_id=first.id, role=Role.EDITOR, status=MembershipStatus.ACTIVE),
                MembershipModel(workspace_id=team.id, user_id=second.id, role=Role.EDITOR, status=MembershipStatus.ACTIVE),
            ])
            await session.commit()

        async def attempt(recipient_id):
            async with sessions() as session:
                try:
                    await transfer_ownership(
                        session, actor=principal(owner), workspace_id=team.id,
                        recipient_id=recipient_id,
                    )
                    return "transferred"
                except StableAPIError as exc:
                    return exc.code

        outcomes = await asyncio.gather(attempt(first.id), attempt(second.id))
        assert outcomes.count("transferred") == 1
        async with sessions() as session:
            owners = list((await session.scalars(select(MembershipModel).where(
                MembershipModel.workspace_id == team.id,
                MembershipModel.status == MembershipStatus.ACTIVE,
                MembershipModel.role == Role.OWNER,
            ))).all())
            assert len(owners) == 1
        await engine.dispose()
    asyncio.run(scenario())


def test_concurrent_invitation_accept_has_one_winner_and_one_safe_replay(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            owner = await add_user(session, "race-owner")
            invitee = await add_user(session, "race-invitee")
            await session.commit()
            team = await create_workspace(session, actor=principal(owner), name="Race")
            _invitation, token = await create_invitation(
                session, actor=principal(owner), workspace_id=team.id,
                invited_identity=invitee.username, role=Role.VIEWER,
            )

        async def attempt():
            async with sessions() as session:
                user = await session.get(User, invitee.id)
                try:
                    membership = await accept_invitation(session, user=user, token=token)
                    return ("accepted", membership.id)
                except StableAPIError as exc:
                    return (exc.code, None)

        outcomes = await asyncio.gather(attempt(), attempt())
        assert sorted(value[0] for value in outcomes) == ["INVITATION_ALREADY_USED", "accepted"]
        async with sessions() as session:
            memberships = list((await session.scalars(select(MembershipModel).where(
                MembershipModel.workspace_id == team.id,
                MembershipModel.user_id == invitee.id,
            ))).all())
            assert len(memberships) == 1
        await engine.dispose()
    asyncio.run(scenario())


def test_audit_events_are_immutable_and_metadata_is_redacted(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        async with sessions() as session:
            user = await add_user(session, "audit-owner")
            await session.commit()
            team = await create_workspace(session, actor=principal(user), name="Audited")
            team_id = team.id
            event = await session.scalar(select(AuditEventModel).where(AuditEventModel.workspace_id == team_id))
            assert event is not None
            event.safe_metadata = {"secret": "must-not-be-written"}
            with pytest.raises(ValueError, match="append-only"):
                await session.commit()
            await session.rollback()
            event = await session.scalar(select(AuditEventModel).where(AuditEventModel.workspace_id == team_id))
            await session.delete(event)
            with pytest.raises(ValueError, match="append-only"):
                await session.commit()
            await session.rollback()
        await engine.dispose()
    asyncio.run(scenario())


def test_workspace_scope_filters_commercial_resources_and_revision_writes(tmp_path, monkeypatch):
    async def scenario():
        extra = (
            PresentationModel.__table__, PresentationDocumentModel.__table__,
            PresentationRevisionModel.__table__, PresentationRevisionPatchModel.__table__,
            ImageAsset.__table__, TemplateModel.__table__, AsyncTaskModel.__table__,
        )
        engine, sessions = await database(tmp_path, "isolation.db", extra)
        async with sessions() as session:
            user_a = await add_user(session, "tenant-a")
            user_b = await add_user(session, "tenant-b")
            workspace_a = await ensure_personal_workspace(session, user_a)
            workspace_b = await ensure_personal_workspace(session, user_b)
            presentation_a = PresentationModel(owner_id=user_a.id, workspace_id=workspace_a.id, version=PresentationVersion.V2_STANDARD, content="a", n_slides=1, language="en")
            presentation_b = PresentationModel(owner_id=user_b.id, workspace_id=workspace_b.id, version=PresentationVersion.V2_STANDARD, content="b", n_slides=1, language="en")
            session.add_all([
                presentation_a, presentation_b,
                ImageAsset(owner_id=user_a.id, workspace_id=workspace_a.id, path="a"),
                ImageAsset(owner_id=user_b.id, workspace_id=workspace_b.id, path="b"),
                TemplateModel(owner_id=user_a.id, workspace_id=workspace_a.id, name="a"),
                TemplateModel(owner_id=user_b.id, workspace_id=workspace_b.id, name="b"),
                AsyncTaskModel(id="a", owner_id=user_a.id, workspace_id=workspace_a.id, actor_id=user_a.id, presentation_id=presentation_a.id, type="export", status=AsyncTaskStatus.PENDING),
                AsyncTaskModel(id="b", owner_id=user_b.id, workspace_id=workspace_b.id, actor_id=user_b.id, presentation_id=presentation_b.id, type="export", status=AsyncTaskStatus.PENDING),
            ])
            await session.commit()

        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        owner_token = set_current_owner_id(user_a.id)
        workspace_token = set_current_workspace_id(workspace_a.id)
        try:
            async with sessions() as session:
                assert [row.workspace_id for row in (await session.scalars(select(PresentationModel))).all()] == [workspace_a.id]
                assert [row.path for row in (await session.scalars(select(ImageAsset))).all()] == ["a"]
                assert [row.name for row in (await session.scalars(select(TemplateModel))).all()] == ["a"]
                assert [row.id for row in (await session.scalars(select(AsyncTaskModel))).all()] == ["a"]
                with pytest.raises(RevisionNotFoundError):
                    await apply_revision_commands(
                        session, presentation_id=presentation_b.id, actor_id=user_a.id,
                        base_revision=0, commands=[], idempotency_key="cross-tenant",
                    )
                with pytest.raises(StableAPIError) as binding:
                    await authorize_workspace(
                        session, principal=principal(user_a), workspace_id=workspace_a.id,
                        resource_workspace_id=workspace_b.id, permission=Permission.PRESENTATIONS_READ,
                    )
                assert binding.value.status_code == 404
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
        await engine.dispose()
    asyncio.run(scenario())

import logging
import os

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from api.v1.auth.users import PASSWORD_HELPER
from models.sql.access_token import AccessToken
from models.sql.user import User
from models.sql.async_task import AsyncTaskModel
from models.sql.async_presentation_generation_status import (
    AsyncPresentationGenerationTaskModel,
)
from models.sql.chat_history_message import ChatHistoryMessageModel
from models.sql.image_asset import ImageAsset
from models.sql.key_value import KeyValueSqlModel
from models.sql.presentation import PresentationModel
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.presentation_layout_code import PresentationLayoutCodeModel
from models.sql.slide import SlideModel
from models.sql.template import TemplateModel
from models.sql.template_create_info import TemplateCreateInfoModel
from models.sql.template_v2 import TemplateV2
from models.sql.webhook_subscription import WebhookSubscription
from services.database import async_session_maker
from api.v1.auth.config import (
    get_legacy_admin_credentials,
    persist_admin_credentials,
)
from utils.get_env import is_disable_auth_enabled
from modules.workspaces.application.personal import ensure_personal_workspace


logger = logging.getLogger(__name__)

# A PostgreSQL transaction-scoped advisory lock serializes administrator
# provisioning across application replicas. The unique ``admin_slot`` column is
# still the final database invariant for every supported database.
_POSTGRES_BOOTSTRAP_LOCK_ID = 5_070_119_843_873_401


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _validate_new_environment_password(password: str | None) -> None:
    if password is not None and len(password) < 8:
        raise RuntimeError("AUTH_PASSWORD must be at least 8 characters")


def _validate_new_environment_username(username: str) -> None:
    if username and len(username) < 3:
        raise RuntimeError("AUTH_USERNAME must be at least 3 characters")


async def _acquire_bootstrap_lock(session) -> None:
    """Serialize first-administrator provisioning where the database supports it."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": _POSTGRES_BOOTSTRAP_LOCK_ID},
        )
    elif dialect == "sqlite":
        # SQLite has no row to lock before the first account exists. Taking the
        # write lock before reading makes concurrent first-boot attempts observe
        # the committed administrator instead of racing the unique constraint.
        await session.execute(text("BEGIN IMMEDIATE"))


async def bootstrap_database_admin() -> None:
    """Provision the primary administrator from deployment-time credentials.

    The public HTTP setup flow is intentionally not involved. Provisioning and
    legacy migration happen under a database lock and commit once, so two
    replicas cannot both create privileged users or leave partially migrated
    ownership behind.
    """
    async with async_session_maker() as session:
        await _acquire_bootstrap_lock(session)
        admin = await session.scalar(
            select(User).where(User.is_superuser.is_(True)).limit(1)
        )
        reset_requested = _truthy(os.getenv("RESET_AUTH"))
        override_requested = _truthy(os.getenv("AUTH_OVERRIDE_FROM_ENV"))
        env_username = (os.getenv("AUTH_USERNAME") or "").strip()
        env_password = os.getenv("AUTH_PASSWORD")
        _validate_new_environment_username(env_username)
        if admin is not None:
            admin.admin_slot = "primary"
            if (reset_requested or override_requested) and not env_password:
                raise RuntimeError(
                    "RESET_AUTH and AUTH_OVERRIDE_FROM_ENV require AUTH_PASSWORD so "
                    "account ownership and data can be preserved"
                )
            if (reset_requested or override_requested) and env_password:
                _validate_new_environment_password(env_password)
                if env_username:
                    admin.username = env_username
                admin.hashed_password = PASSWORD_HELPER.hash(env_password)
                admin.auth_version += 1
                await session.execute(
                    delete(AccessToken).where(AccessToken.user_id == admin.id)
                )
                await session.flush()
            await _backfill_legacy_ownership(session, admin)
            await session.commit()
            if reset_requested or override_requested:
                persist_admin_credentials(
                    admin.username,
                    admin.hashed_password,
                    rotate_secret=True,
                )
                logger.warning(
                    "Recovered bootstrap administrator credentials from environment."
                )
            return

        account_count = int(
            await session.scalar(select(func.count()).select_from(User)) or 0
        )
        if account_count:
            raise RuntimeError(
                "User accounts exist but no bootstrap administrator is configured"
            )

        legacy_username, legacy_hash = get_legacy_admin_credentials()
        use_environment = reset_requested or override_requested
        username = (
            env_username if use_environment and env_username else legacy_username
        ) or env_username
        if not username:
            if is_disable_auth_enabled():
                logger.warning(
                    "Authentication is explicitly disabled; no administrator was "
                    "provisioned."
                )
                return
            raise RuntimeError(
                "No administrator is configured. Set AUTH_USERNAME and AUTH_PASSWORD "
                "at deployment time before starting the service."
            )

        if use_environment and env_password:
            _validate_new_environment_password(env_password)
            password_hash = PASSWORD_HELPER.hash(env_password)
        elif legacy_hash:
            password_hash = legacy_hash
        elif env_password:
            _validate_new_environment_password(env_password)
            password_hash = PASSWORD_HELPER.hash(env_password)
        else:
            if is_disable_auth_enabled():
                logger.warning(
                    "Authentication is explicitly disabled; no administrator was "
                    "provisioned."
                )
                return
            raise RuntimeError(
                "AUTH_PASSWORD is required to provision the initial administrator."
            )

        admin = User(
            username=username,
            hashed_password=password_hash,
            is_active=True,
            is_verified=True,
            is_superuser=True,
            admin_slot="primary",
            auth_version=1,
        )
        session.add(admin)
        try:
            await session.flush()
            await _backfill_legacy_ownership(session, admin)
            await session.commit()
        except IntegrityError:
            # The unique primary-admin slot remains the last line of defense on
            # databases without a first-row/advisory lock. A concurrent winner
            # is a successful bootstrap outcome, not a second administrator.
            await session.rollback()
            concurrent_admin = await session.scalar(
                select(User).where(User.is_superuser.is_(True)).limit(1)
            )
            if concurrent_admin is not None:
                logger.info(
                    "Another process completed administrator provisioning first."
                )
                return
            raise
        persist_admin_credentials(username, password_hash)
        logger.info("Provisioned the deployment administrator in the user database.")


async def _backfill_legacy_ownership(session, admin: User) -> None:
    personal_workspace = await ensure_personal_workspace(session, admin)
    owned_models = (
        PresentationModel,
        PresentationDocumentModel,
        SlideModel,
        PresentationLayoutCodeModel,
        TemplateModel,
        AsyncTaskModel,
        AsyncPresentationGenerationTaskModel,
        ChatHistoryMessageModel,
        ImageAsset,
        TemplateCreateInfoModel,
        WebhookSubscription,
    )
    for model in owned_models:
        await session.execute(
            update(model)
            .where(model.owner_id.is_(None))
            .values(owner_id=admin.id)
        )
        await session.execute(
            update(model)
            .where(model.workspace_id.is_(None), model.owner_id == admin.id)
            .values(workspace_id=personal_workspace.id)
        )
    # Built-in templates intentionally remain shared; only custom templates
    # migrate into the bootstrap admin's private workspace.
    await session.execute(
        update(TemplateV2)
        .where(TemplateV2.owner_id.is_(None), TemplateV2.is_default.is_(False))
        .values(owner_id=admin.id)
    )
    await session.execute(
        update(TemplateV2)
        .where(TemplateV2.workspace_id.is_(None), TemplateV2.owner_id == admin.id)
        .values(workspace_id=personal_workspace.id)
    )
    await session.execute(
        update(AccessToken)
        .where(AccessToken.workspace_id.is_(None), AccessToken.user_id == admin.id)
        .values(workspace_id=personal_workspace.id)
    )
    await session.execute(
        update(KeyValueSqlModel)
        .where(KeyValueSqlModel.key == "presentation_custom_themes")
        .values(key=f"presentation_custom_themes:{admin.id}")
    )

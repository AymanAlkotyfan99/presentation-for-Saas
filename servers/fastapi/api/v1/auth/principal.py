from dataclasses import dataclass
from typing import Literal
import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.users import UsernameUserDatabase, UserManager, get_jwt_strategy
from models.sql.access_token import AccessToken
from models.sql.user import User
from api.v1.auth.config import SESSION_COOKIE_NAME
from modules.workspaces.application.credentials import verify_service_credential
from utils.architecture_flags import service_accounts_enabled


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: uuid.UUID | None
    username: str
    is_admin: bool
    method: Literal["jwt", "api_key", "service_account"]
    workspace_id: uuid.UUID | None = None
    service_account_id: uuid.UUID | None = None
    scopes: frozenset[str] = frozenset()


async def resolve_request_principal(
    request: Request, session: AsyncSession
) -> tuple[AuthPrincipal | None, User | None]:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        user_db = UsernameUserDatabase(session)
        user = await get_jwt_strategy().read_token(cookie_token, UserManager(user_db))
        if user:
            return (
                AuthPrincipal(
                    user_id=user.id,
                    username=user.username,
                    is_admin=user.is_superuser,
                    method="jwt",
                ),
                user,
            )

    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token.startswith("bws_") and service_accounts_enabled():
            verified = await verify_service_credential(session, token)
            if verified is None:
                return None, None
            return (
                AuthPrincipal(
                    user_id=None,
                    username=verified.service_account_name,
                    is_admin=False,
                    method="service_account",
                    workspace_id=verified.workspace_id,
                    service_account_id=verified.service_account_id,
                    scopes=verified.scopes,
                ),
                None,
            )
        if not token.startswith("sk-presenton-"):
            return None, None
        access_token = await session.get(AccessToken, token)
        if access_token is None:
            return None, None
        user = await session.get(User, access_token.user_id)
        if user is None or not user.is_active or not user.is_superuser:
            return None, None
        return (
            AuthPrincipal(
                user_id=user.id,
                username=user.username,
                is_admin=True,
                method="api_key",
            ),
            user,
        )

    return None, None


def principal_from_request(request: Request) -> AuthPrincipal:
    principal = getattr(request.state, "auth_principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return principal


def require_browser_admin_principal(request: Request) -> AuthPrincipal:
    principal = principal_from_request(request)
    if principal.method != "jwt" or not principal.is_admin:
        raise HTTPException(status_code=403, detail="Admin browser session required")
    return principal

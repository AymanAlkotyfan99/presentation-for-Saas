from dataclasses import replace
from uuid import UUID
from fastapi import Request
from sqlalchemy import func, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.v1.auth.assets import is_app_data_path_authorized
from api.v1.auth.principal import resolve_request_principal
from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_owner_is_admin,
    reset_current_service_account_id,
    reset_current_workspace_id,
    reset_current_workspace_permissions,
    reset_current_workspace_role,
    set_current_owner_id,
    set_current_owner_is_admin,
    set_current_service_account_id,
    set_current_workspace_id,
    set_current_workspace_permissions,
    set_current_workspace_role,
)
from api.v1.auth.users import get_jwt_strategy
from models.sql.user import User
from services.database import async_session_maker
from utils.get_env import get_can_change_keys_env, is_disable_auth_enabled
from utils.user_config import update_env_with_user_config
from modules.workspaces.application.authorization import validated_workspace_selection
from modules.workspaces.application.personal import ensure_personal_workspace
from modules.workspaces.domain.models import Permission
from modules.workspaces.domain.policies import permissions_for_role, scope_allows
from modules.workspaces.persistence.models import WorkspaceModel
from utils.architecture_flags import workspace_rbac_enforcement_enabled, workspaces_enabled


class UserConfigEnvUpdateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if get_can_change_keys_env() != "false":
            update_env_with_user_config()
        return await call_next(request)


class SessionAuthMiddleware(BaseHTTPMiddleware):
    _PUBLIC_AUTH_PATHS = {
        "/api/v1/auth/status",
        "/api/v1/auth/verify",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }
    _PUBLIC_APP_DATA_PREFIXES: tuple[str, ...] = ()
    _PROTECTED_NON_API_PATHS = {"/docs", "/openapi.json", "/redoc"}

    def _requires_auth(self, path: str) -> bool:
        if path.startswith("/api/"):
            return True
        if any(path.startswith(prefix) for prefix in self._PUBLIC_APP_DATA_PREFIXES):
            return False
        if path.startswith("/app_data/"):
            return True
        return path in self._PROTECTED_NON_API_PATHS

    @staticmethod
    def _required_workspace_permission(path: str, method: str) -> Permission | None:
        if path.startswith("/api/v1/workspaces/") or path == "/api/v1/workspaces":
            return None
        if path.startswith("/app_data/"):
            return Permission.ASSETS_READ
        if path == "/api/v1/jobs" or path.startswith("/api/v1/jobs/"):
            return (
                Permission.JOBS_READ
                if method == "GET"
                else Permission.JOBS_WRITE
            )
        if path == "/api/v1/assets" or path.startswith("/api/v1/assets/"):
            if method == "GET" or path.endswith("/download-capability"):
                return Permission.ASSETS_READ
            return Permission.ASSETS_WRITE
        if path.startswith("/api/v1/async"):
            return Permission.JOBS_READ
        if path.startswith("/api/v1/webhook"):
            return Permission.CREDENTIALS_MANAGE
        if not path.startswith("/api/v1/ppt/"):
            return None
        modifying = method in {"POST", "PUT", "PATCH", "DELETE"}
        if "/template" in path or "/theme" in path or "/fonts" in path:
            return Permission.TEMPLATES_WRITE if modifying else Permission.TEMPLATES_READ
        if "/images" in path or "/files" in path or "/icons" in path:
            return Permission.ASSETS_WRITE if modifying or "/generate" in path else Permission.ASSETS_READ
        if "/status/" in path:
            return Permission.JOBS_READ
        if "/stream/" in path or "/generate" in path:
            return Permission.PRESENTATIONS_WRITE
        return Permission.PRESENTATIONS_WRITE if modifying else Permission.PRESENTATIONS_READ

    async def dispatch(self, request: Request, call_next):
        if is_disable_auth_enabled():
            return await call_next(request)

        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not self._requires_auth(path)
            or path in self._PUBLIC_AUTH_PATHS
        ):
            return await call_next(request)

        async with async_session_maker() as session:
            configured = bool(
                await session.scalar(select(func.count()).select_from(User))
            )
            if not configured:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Authentication unavailable"},
                )
            principal, user = await resolve_request_principal(request, session)
            if principal is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"},
                )
            admin_only = (
                path.startswith("/api/v1/admin/")
                or path.startswith("/api/v1/auth/token/")
                or path.startswith("/api/v1/ppt/codex/auth/")
                or (
                    path.startswith("/api/v1/ppt/fonts/")
                    and request.method in {"POST", "DELETE"}
                )
                or (
                    path == "/api/v1/ppt/ollama/models/pull"
                    and request.method == "POST"
                )
            )
            if admin_only and (
                principal.method != "jwt" or not principal.is_admin
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Admin browser session required"},
                )
            request.state.auth_principal = principal
            request.state.current_user = user
            request.state.auth_username = principal.username
            if principal.method == "api_key" and user is not None:
                request.state.internal_session_token = (
                    await get_jwt_strategy().write_token(user)
                )
            workspace = None
            membership = None
            permissions: frozenset[str] = frozenset()
            if workspaces_enabled():
                if principal.method == "service_account":
                    workspace = await session.get(WorkspaceModel, principal.workspace_id)
                    requested = request.headers.get("X-Workspace-ID")
                    if not workspace or (requested and requested != str(principal.workspace_id)):
                        return JSONResponse(status_code=404, content={"detail": "Workspace not found", "code": "WORKSPACE_NOT_FOUND", "params": {}})
                    permissions = principal.scopes
                else:
                    if user is None or principal.user_id is None:
                        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
                    await ensure_personal_workspace(session, user)
                    await session.commit()
                    header_value = request.headers.get("X-Workspace-ID")
                    cookie_value = request.cookies.get("bayanly_workspace")
                    candidate_value = header_value or cookie_value
                    try:
                        candidate = UUID(candidate_value) if candidate_value else None
                    except ValueError:
                        if header_value:
                            return JSONResponse(status_code=404, content={"detail": "Workspace not found", "code": "WORKSPACE_NOT_FOUND", "params": {}})
                        candidate = None
                    try:
                        workspace, membership = await validated_workspace_selection(
                            session, user_id=principal.user_id,
                            requested_workspace_id=candidate, explicit=bool(header_value),
                        )
                    except Exception as exc:
                        if hasattr(exc, "response_body"):
                            return JSONResponse(status_code=exc.status_code, content=exc.response_body())
                        raise
                    permissions = frozenset(value.value for value in permissions_for_role(membership.role, membership.permission_overrides))
                request.state.workspace = workspace
                request.state.workspace_membership = membership
                request.state.workspace_permissions = permissions
                if workspace is not None and principal.workspace_id != workspace.id:
                    principal = replace(principal, workspace_id=workspace.id)
                    request.state.auth_principal = principal

                if workspace_rbac_enforcement_enabled():
                    required = self._required_workspace_permission(path, request.method)
                    if principal.method == "service_account" and required is None:
                        return JSONResponse(status_code=403, content={"detail": "Workspace permission denied", "code": "WORKSPACE_PERMISSION_DENIED", "params": {}})
                    allowed = required is None or (
                        scope_allows(principal.scopes, required)
                        if principal.method == "service_account"
                        else required.value in permissions
                    )
                    if not allowed:
                        return JSONResponse(status_code=403, content={"detail": "Workspace permission denied", "code": "WORKSPACE_PERMISSION_DENIED", "params": {"permission": required.value}})

            if path.startswith("/app_data/") and not is_app_data_path_authorized(
                path,
                user_id=principal.user_id,
                is_admin=principal.is_admin,
                workspace_id=(workspace.id if workspace and workspace_rbac_enforcement_enabled() else None),
            ):
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Asset not found"},
                )

            context_token = set_current_owner_id(principal.user_id)
            admin_context_token = set_current_owner_is_admin(principal.is_admin)
            workspace_token = set_current_workspace_id(workspace.id if workspace else principal.workspace_id)
            role_token = set_current_workspace_role(membership.role.value if membership else None)
            permission_token = set_current_workspace_permissions(permissions)
            service_account_token = set_current_service_account_id(principal.service_account_id)
            try:
                return await call_next(request)
            finally:
                reset_current_service_account_id(service_account_token)
                reset_current_workspace_permissions(permission_token)
                reset_current_workspace_role(role_token)
                reset_current_workspace_id(workspace_token)
                reset_current_owner_is_admin(admin_context_token)
                reset_current_owner_id(context_token)

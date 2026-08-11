from contextvars import ContextVar, Token
import uuid


_CURRENT_OWNER_ID: ContextVar[uuid.UUID | None] = ContextVar(
    "presenton_current_owner_id", default=None
)
_CURRENT_OWNER_IS_ADMIN: ContextVar[bool] = ContextVar(
    "presenton_current_owner_is_admin", default=False
)
_CURRENT_WORKSPACE_ID: ContextVar[uuid.UUID | None] = ContextVar(
    "bayanly_current_workspace_id", default=None
)
_CURRENT_WORKSPACE_ROLE: ContextVar[str | None] = ContextVar(
    "bayanly_current_workspace_role", default=None
)
_CURRENT_WORKSPACE_PERMISSIONS: ContextVar[frozenset[str]] = ContextVar(
    "bayanly_current_workspace_permissions", default=frozenset()
)
_CURRENT_SERVICE_ACCOUNT_ID: ContextVar[uuid.UUID | None] = ContextVar(
    "bayanly_current_service_account_id", default=None
)
_CURRENT_JOB_ID: ContextVar[uuid.UUID | None] = ContextVar(
    "bayanly_current_job_id", default=None
)


def get_current_owner_id() -> uuid.UUID | None:
    return _CURRENT_OWNER_ID.get()


def get_current_owner_is_admin() -> bool:
    return _CURRENT_OWNER_IS_ADMIN.get()


def get_current_workspace_id() -> uuid.UUID | None:
    return _CURRENT_WORKSPACE_ID.get()


def get_current_workspace_role() -> str | None:
    return _CURRENT_WORKSPACE_ROLE.get()


def get_current_workspace_permissions() -> frozenset[str]:
    return _CURRENT_WORKSPACE_PERMISSIONS.get()


def get_current_service_account_id() -> uuid.UUID | None:
    return _CURRENT_SERVICE_ACCOUNT_ID.get()


def get_current_job_id() -> uuid.UUID | None:
    return _CURRENT_JOB_ID.get()


def set_current_owner_id(owner_id: uuid.UUID | None) -> Token:
    return _CURRENT_OWNER_ID.set(owner_id)


def set_current_owner_is_admin(is_admin: bool) -> Token:
    return _CURRENT_OWNER_IS_ADMIN.set(is_admin)


def set_current_workspace_id(workspace_id: uuid.UUID | None) -> Token:
    return _CURRENT_WORKSPACE_ID.set(workspace_id)


def set_current_workspace_role(role: str | None) -> Token:
    return _CURRENT_WORKSPACE_ROLE.set(role)


def set_current_workspace_permissions(permissions: frozenset[str]) -> Token:
    return _CURRENT_WORKSPACE_PERMISSIONS.set(permissions)


def set_current_service_account_id(service_account_id: uuid.UUID | None) -> Token:
    return _CURRENT_SERVICE_ACCOUNT_ID.set(service_account_id)


def set_current_job_id(job_id: uuid.UUID | None) -> Token:
    return _CURRENT_JOB_ID.set(job_id)


def reset_current_owner_id(token: Token) -> None:
    _CURRENT_OWNER_ID.reset(token)


def reset_current_owner_is_admin(token: Token) -> None:
    _CURRENT_OWNER_IS_ADMIN.reset(token)


def reset_current_workspace_id(token: Token) -> None:
    _CURRENT_WORKSPACE_ID.reset(token)


def reset_current_workspace_role(token: Token) -> None:
    _CURRENT_WORKSPACE_ROLE.reset(token)


def reset_current_workspace_permissions(token: Token) -> None:
    _CURRENT_WORKSPACE_PERMISSIONS.reset(token)


def reset_current_service_account_id(token: Token) -> None:
    _CURRENT_SERVICE_ACCOUNT_ID.reset(token)


def reset_current_job_id(token: Token) -> None:
    _CURRENT_JOB_ID.reset(token)

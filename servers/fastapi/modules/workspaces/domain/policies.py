"""Central, deny-by-default workspace permission matrix."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Permission, Role


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset({
        Permission.WORKSPACE_VIEW, Permission.WORKSPACE_UPDATE,
        Permission.MEMBERS_VIEW, Permission.MEMBERS_MANAGE,
        Permission.PRESENTATIONS_READ, Permission.PRESENTATIONS_WRITE,
        Permission.ASSETS_READ, Permission.ASSETS_WRITE,
        Permission.TEMPLATES_READ, Permission.TEMPLATES_WRITE,
        Permission.JOBS_READ, Permission.INVITATIONS_MANAGE,
        Permission.CREDENTIALS_MANAGE, Permission.AUDIT_READ,
    }),
    Role.EDITOR: frozenset({
        Permission.WORKSPACE_VIEW, Permission.MEMBERS_VIEW,
        Permission.PRESENTATIONS_READ, Permission.PRESENTATIONS_WRITE,
        Permission.ASSETS_READ, Permission.ASSETS_WRITE,
        Permission.TEMPLATES_READ, Permission.TEMPLATES_WRITE,
        Permission.JOBS_READ,
    }),
    Role.VIEWER: frozenset({
        Permission.WORKSPACE_VIEW, Permission.MEMBERS_VIEW,
        Permission.PRESENTATIONS_READ, Permission.ASSETS_READ,
        Permission.TEMPLATES_READ, Permission.JOBS_READ,
    }),
}

SERVICE_ACCOUNT_SCOPES = frozenset({
    Permission.PRESENTATIONS_READ.value,
    Permission.PRESENTATIONS_WRITE.value,
    Permission.ASSETS_READ.value,
    Permission.ASSETS_WRITE.value,
    Permission.TEMPLATES_READ.value,
    Permission.JOBS_READ.value,
})


def permissions_for_role(role: Role, overrides: Iterable[str] = ()) -> frozenset[Permission]:
    permissions = set(ROLE_PERMISSIONS.get(role, frozenset()))
    for value in overrides:
        try:
            permissions.add(Permission(value))
        except ValueError:
            continue
    return frozenset(permissions)


def role_allows(role: Role, permission: Permission, overrides: Iterable[str] = ()) -> bool:
    return permission in permissions_for_role(role, overrides)


def scope_allows(scopes: Iterable[str], permission: Permission) -> bool:
    return permission.value in set(scopes) and permission.value in SERVICE_ACCOUNT_SCOPES

from enum import Enum


class Role(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class Permission(str, Enum):
    WORKSPACE_VIEW = "workspace:view"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_DELETE = "workspace:delete"
    MEMBERS_VIEW = "members:view"
    MEMBERS_MANAGE = "members:manage"
    OWNER_TRANSFER = "owner:transfer"
    FINANCE_REVIEW = "finance:review"
    PRESENTATIONS_READ = "presentations:read"
    PRESENTATIONS_WRITE = "presentations:write"
    ASSETS_READ = "assets:read"
    ASSETS_WRITE = "assets:write"
    TEMPLATES_READ = "templates:read"
    TEMPLATES_WRITE = "templates:write"
    JOBS_READ = "jobs:read"
    JOBS_WRITE = "jobs:write"
    INVITATIONS_MANAGE = "invitations:manage"
    CREDENTIALS_MANAGE = "credentials:manage"
    AUDIT_READ = "audit:read"

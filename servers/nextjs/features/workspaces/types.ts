export type WorkspaceRole = "OWNER" | "ADMIN" | "EDITOR" | "VIEWER";

export type WorkspacePermission =
  | "workspace:view"
  | "workspace:update"
  | "workspace:delete"
  | "members:view"
  | "members:manage"
  | "owner:transfer"
  | "finance:review"
  | "presentations:read"
  | "presentations:write"
  | "assets:read"
  | "assets:write"
  | "templates:read"
  | "templates:write"
  | "jobs:read"
  | "invitations:manage"
  | "credentials:manage"
  | "audit:read";

export interface WorkspaceSummary {
  id: string;
  name: string;
  isPersonal: boolean;
  role: WorkspaceRole | null;
  permissions: string[];
  createdAt: string;
}

export interface WorkspaceMember {
  id: string;
  userId: string;
  username: string;
  role: WorkspaceRole;
  status: "ACTIVE" | "SUSPENDED";
  financeReview: boolean;
}

export interface WorkspaceInvitation {
  id: string;
  invitedIdentity: string;
  role: WorkspaceRole;
  expiresAt: string;
  acceptedAt: string | null;
  revokedAt: string | null;
}

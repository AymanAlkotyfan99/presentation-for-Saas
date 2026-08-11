import type { WorkspacePermission, WorkspaceRole } from "./types";

const PERMISSIONS = new Set<WorkspacePermission>([
  "workspace:view", "workspace:update", "workspace:delete", "members:view",
  "members:manage", "owner:transfer", "finance:review", "presentations:read",
  "presentations:write", "assets:read", "assets:write", "templates:read",
  "templates:write", "jobs:read", "jobs:write", "invitations:manage", "credentials:manage",
  "audit:read",
]);

export function normalizeCapabilities(values: readonly string[]): ReadonlySet<WorkspacePermission> {
  return new Set(values.filter((value): value is WorkspacePermission => PERMISSIONS.has(value as WorkspacePermission)));
}

export function can(capabilities: ReadonlySet<WorkspacePermission>, permission: WorkspacePermission): boolean {
  return capabilities.has(permission);
}

export function editableRolesFor(actorRole: WorkspaceRole | null): WorkspaceRole[] {
  return actorRole === "OWNER" || actorRole === "ADMIN" ? ["ADMIN", "EDITOR", "VIEWER"] : [];
}

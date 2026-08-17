// features/workspaces/capabilities.ts
var PERMISSIONS = /* @__PURE__ */ new Set([
  "workspace:view",
  "workspace:update",
  "workspace:delete",
  "members:view",
  "members:manage",
  "owner:transfer",
  "finance:review",
  "presentations:read",
  "presentations:write",
  "assets:read",
  "assets:write",
  "templates:read",
  "templates:write",
  "jobs:read",
  "jobs:write",
  "invitations:manage",
  "credentials:manage",
  "audit:read"
]);
function normalizeCapabilities(values) {
  return new Set(values.filter((value) => PERMISSIONS.has(value)));
}
function can(capabilities, permission) {
  return capabilities.has(permission);
}
function editableRolesFor(actorRole) {
  return actorRole === "OWNER" || actorRole === "ADMIN" ? ["ADMIN", "EDITOR", "VIEWER"] : [];
}
export {
  can,
  editableRolesFor,
  normalizeCapabilities
};

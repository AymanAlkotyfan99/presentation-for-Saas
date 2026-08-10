# Workspaces and RBAC

Sprint 7 adds a tenant boundary around the existing presentation model. A workspace is the tenant; an active membership connects a browser user to one workspace with one of four roles. Authentication still resolves identity in `api/v1/auth`. Authorization is centralized in `modules/workspaces` and is deny-by-default. Platform `is_superuser` remains limited to platform-admin routes and grants no workspace membership or tenant permission.

## Request boundary

`SessionAuthMiddleware` resolves the authenticated principal and provisions an idempotent personal workspace for browser users. `X-Workspace-ID`, when supplied, is treated as an explicit selection and must match an active membership. A stale cookie is ignored in favor of the personal workspace; an invalid explicit header fails closed. A service credential is permanently bound to its credential workspace.

The validated workspace, membership, role, permissions, actor, and service-account identity are placed in request-local context. SQLAlchemy loader criteria then scope reads for commercial models. Bulk writes use the same `resource_scope_predicate`. Route-level permission mapping blocks modifying calls before handlers run, while application services repeat sensitive authorization at the transactional boundary.

The legacy `owner_id` is retained. With `LEGACY_OWNER_BRIDGE_ENABLED=true`, a user may reach a not-yet-reconciled null-workspace row only when its legacy owner matches. A service account never receives that bridge. Rows with another workspace never pass through the bridge.

## Permission matrix

| Permission | Owner | Admin | Editor | Viewer |
| --- | ---: | ---: | ---: | ---: |
| workspace view | yes | yes | yes | yes |
| workspace update | yes | yes | no | no |
| workspace delete | yes | no | no | no |
| members view | yes | yes | yes | yes |
| members manage / invitations | yes | yes | no | no |
| owner transfer | yes | no | no | no |
| finance review | yes | explicit owner-managed grant only | explicit owner-managed grant only | explicit owner-managed grant only |
| presentations read | yes | yes | yes | yes |
| presentations write | yes | yes | yes | no |
| assets read | yes | yes | yes | yes |
| assets write | yes | yes | yes | no |
| templates read | yes | yes | yes | yes |
| templates write | yes | yes | yes | no |
| jobs read | yes | yes | yes | yes |
| credentials manage | yes | yes | no | no |
| audit read | yes | yes | no | no |

Unknown roles, permissions, overrides, and service scopes are denied. The frontend consumes the server-returned permission set only to shape UX; backend checks remain authoritative.

## Ownership invariants

- Each user has at most one personal workspace, deterministically keyed by the user UUID.
- Membership is unique per workspace/user.
- Application-created team workspaces begin with one active owner.
- `OWNER` cannot be assigned through ordinary role updates or invitations.
- The owner cannot be removed. Team ownership transfer locks the workspace and active memberships, demotes the old owner, and promotes an existing active recipient in one transaction. Personal workspaces cannot transfer.
- Membership suspension or deletion takes effect on the next request because membership authority is not cached outside request scope.

## Credentials and invitations

Invitation and service credential secrets contain 256 bits of randomness and are returned only at creation. The database stores an HMAC-SHA-256 digest, never plaintext. Deployments should configure `WORKSPACE_TOKEN_PEPPER`; compromise of a database alone then does not permit offline token verification. Invitations are identity-, workspace-, role-, expiry-, and single-use-bound. Creation and acceptance are operation-rate/concurrency controlled.

Service accounts are workspace-bound. Credentials have an explicit allow-listed scope set: `presentations:read`, `presentations:write`, `assets:read`, `assets:write`, `templates:read`, and `jobs:read`. Unknown scopes and administrative super-scopes are rejected. Rotation creates a new secret and revokes the selected old credential in the same transaction.

## Storage and jobs

When RBAC enforcement is enabled, new private app-data files use `/<root>/workspaces/<workspace-id>/...`; browser and server-side resolution compare that segment to validated request context. Legacy `users/<owner-id>` paths retain their owner-only behavior. Cross-workspace copies must create a new workspace-owned asset reference and byte path.

Workspace jobs store workspace, actor, and resource identity. Presentation jobs also pin the source revision once the presentation exists. Workers compare the persisted resource/workspace relationship with request-local authority before mutating or publishing a result. This is compatibility hardening only; tasks remain in-process and non-durable until the queue sprint.

## Audit and sensitive operations

Audit events are narrowly scoped security records. Safe metadata is allow-listed and excludes prompts, slide text, paths, invitations, and credentials. ORM and database triggers prevent update/delete. Owner transfer, finance grants, and credential issuance have explicit permission boundaries. The repository has no general MFA/reauthentication primitive, so production step-up remains required before these controls are exposed broadly; no simulated step-up is used.

Feature flags default off for workspaces, RBAC enforcement, invitations, and service accounts. The owner bridge defaults on for migration safety.

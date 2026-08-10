# Workspace migration

Alembic revision `8d0f2b4c6e8a` follows revision-safe persistence revision `7c9e1a3b5d6f`.

The migration creates `workspaces`, `memberships`, `invitations`, `service_accounts`, `api_credentials`, `api_credential_scopes`, and `audit_events`. It adds nullable indexed `workspace_id` foreign keys to presentations, canonical documents, revision/patch history, slides, assets, templates, both job tables, chat history, access tokens, webhooks, layout code, and template creation metadata. Job actor/resource identity is also reconciled. Legacy `owner_id` remains untouched.

Backfill is set-oriented and retry-safe at its domain boundaries:

1. Insert one personal workspace per user, using the user UUID and a unique `personal_owner_id`.
2. Insert one active owner membership per user/personal workspace.
3. Assign legacy resources to the personal workspace matching `owner_id` (or `user_id` for access tokens).
4. Reconcile canonical documents, revisions, patches, slides, chat history, and presentation jobs from their parent presentation workspace.
5. Backfill job actor and resource identifiers.
6. Install database triggers that reject audit event updates and deletes.

`workspace_id` remains nullable so operators can reconcile exceptional legacy/global rows before authority is made non-null in a later controlled migration. Built-in Template V2 rows with no owner remain shared/system templates.

## Rollout

Keep all new behavior flags off while upgrading. Run reconciliation queries for null workspace IDs and owner/workspace inconsistencies in bounded batches on a production copy. Enable `WORKSPACES_ENABLED` for an internal cohort, then RBAC enforcement, invitations, and service accounts separately. Keep `LEGACY_OWNER_BRIDGE_ENABLED=true` until reconciliation is zero and access-denial telemetry is reviewed.

The downgrade removes the added job fields and workspace columns in dependency-safe order, then drops the new domain tables. It does not delete legacy owner data. Downgrade intentionally removes workspace-only memberships, invitations, audit history, and credentials; back up those new tables before rolling back an environment that accepted Sprint 7 traffic.

SQLite upgrade/downgrade/upgrade is part of the focused gate. PostgreSQL must also be exercised in CI or a disposable deployment because row-lock concurrency, UUID casts, trigger behavior, and DDL transactions are not fully represented by SQLite.

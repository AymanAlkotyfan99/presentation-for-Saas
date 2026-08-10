# Revision-safe persistence migration

Migration `7c9e1a3b5d6f` is additive and follows `04b6d8f0a2c4`.

It adds `presentations.current_revision`, source-revision fields on `async_tasks`, and the `presentation_revisions` and `presentation_revision_patches` tables. Existing non-null canonical documents are copied set-wise into immutable snapshot anchors, using `presentation_id` as the seed row UUID, and their presentation pointer is updated to the existing document revision. Legacy-only presentations stay at revision zero.

## Deployment order

1. Back up the database and confirm the Alembic graph has one head.
2. Deploy the migration while all new feature flags remain disabled.
3. Verify every non-null `presentation_documents` row has one matching anchor and the same checksum/revision.
4. Enable revision writes only for the controlled canonical cohort.
5. Enable browser recovery and history separately after observing conflicts, replay failures, and write latency.

The migration does not deserialize presentation documents in application memory and does not rewrite legacy slides. Indexes support presentation history and actor-scoped idempotency lookups. PostgreSQL and SQLite install update-blocking triggers; ORM listeners also reject revision or patch mutation. Parent presentation deletion can still cascade history according to the existing data-deletion contract.

## Validation and rollback

Required checks are an empty-database upgrade, downgrade to the previous head, re-upgrade, schema constraint/index inspection, and a concurrent PostgreSQL stale-writer/idempotency test when a disposable PostgreSQL service is available. SQLite is the structural fallback, not evidence of PostgreSQL locking behavior.

Operational rollback is flag-first: disable `REVISION_WRITES_ENABLED`, `INDEXEDDB_RECOVERY_ENABLED`, and `VERSION_HISTORY_ENABLED`. The legacy document path remains available. Schema downgrade is appropriate only after confirming no revision-only writes must be retained; it removes immutable history and the source-revision task pins.

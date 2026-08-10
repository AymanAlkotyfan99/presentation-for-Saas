# Revision-safe persistence and recovery

Canonical presentations are persisted as an ordered, immutable stream. The server—not the browser—is authoritative for applying editor commands.

## Write protocol

`PATCH /api/v1/ppt/presentations/{id}/revisions` requires an `If-Match` revision, the same `baseRevision` in the JSON body, and an `Idempotency-Key`. The service locks the presentation row, checks actor access, resolves an actor-scoped idempotency record, verifies the base revision, applies the Sprint 5 command contract, validates the resulting canonical document, and commits these changes in one transaction:

- one immutable `presentation_revision_patches` row;
- one immutable `presentation_revisions` row;
- the materialized `presentation_documents` snapshot and checksum;
- `presentations.current_revision`.

Revision `0` means no persisted canonical document. The first persisted or migrated document is revision `1`. A stale base returns `REVISION_CONFLICT` with only the current revision and checksum. Replaying the same actor/key/payload returns the original acknowledgement; reusing the key for another payload fails closed.

Full-document PUT remains a controlled compatibility bridge. When revision writes are enabled, it creates an immutable snapshot revision through the same transaction instead of bypassing history.

## Replay, history, and restore

Revision 1, every twentieth revision, every legacy full replacement, and every restore are snapshot anchors. Other revisions contain commands only. Reconstruction starts at the closest anchor and replays at most nineteen command revisions, then verifies the stored SHA-256 checksum. A restore never changes an old row: it creates a new anchor revision with `source=restore` and `restored_from_revision` provenance.

History metadata and diff responses intentionally exclude document text. The diff endpoint returns counts and whether the title changed. Deletion/retention is not automated in this phase; `retention_class` identifies safe anchors for a future policy without risking unreplayable history.

## Browser durability

The canonical editor queues the exact command objects that it executes. Before a network attempt, a bounded command-only journal is written to IndexedDB. The UI reports “saved” only after the server acknowledgement advances the durable revision. Network ambiguity retains the same idempotency key. Reload recovery compares the journal base with the current server revision before retrying.

No full presentation document, credential, cookie, or access token is written to recovery storage. The journal is capped at 250 entries and 1 MiB. A BroadcastChannel/localStorage lease elects one writer tab; other tabs are visibly read-only until the lease expires. Only lease metadata is broadcast.

Conflicts pause autosave. Users can load the server version or explicitly download their local command recovery copy. Local changes are never silently applied over a newer server revision.

## Long-running work

Async task records can pin `presentation_id`, `source_revision`, and `actor_id`. Before late results or exports are applied, `assert_task_revision_current` rejects work whose source revision is no longer current. New-presentation generation pins revision zero once its presentation row exists.

## Flags and observability

Defaults preserve the prior production path:

```text
REVISION_WRITES_ENABLED=false
REQUIRE_IF_MATCH=true
INDEXEDDB_RECOVERY_ENABLED=false
VERSION_HISTORY_ENABLED=false
LEGACY_BLIND_UPDATE_BRIDGE_ENABLED=true
```

Browser-exposed flags use the corresponding `NEXT_PUBLIC_` names. Roll out revision writes to the existing canonical internal cohort first, then IndexedDB recovery, then history UI. Monitor stable error codes (`REVISION_CONFLICT`, `REVISION_IDEMPOTENCY_CONFLICT`, replay checksum failures), save latency, offline queue size, and stale-task rejection. Rollback disables the new flags; additive tables and legacy reads remain intact.

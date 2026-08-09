# Canonical document migration runbook

The migration is additive and rollback-safe. Alembic creates
`presentation_documents` after the locale migration; it does not alter or drop
`presentations`, `slides`, V1/V2 payloads, HTML, UI data, or physical assets.
Conversion reads owner-scoped legacy rows, prefers `SlideModel.ui` and
structured `content`, ignores rather than executes HTML, assigns deterministic
UUIDv5 IDs, validates the result, and writes a separate current record.

States are `NOT_STARTED`, `PENDING`, `CONVERTING`, `CONVERTED`, `FAILED`,
`UNSUPPORTED`, and `NEEDS_REVIEW`. Invalid transitions are rejected by the
domain transition table. Unsupported custom layouts, SVG/HTML-only content,
unknown elements, irregular tables, and unresolved assets are visible as
stable warnings/status rather than silently flattened. Failure details are a
bounded category and error code; stack traces and content are not stored or
returned. Retry is explicit and capped at three persisted attempts per
presentation. State transitions are checked by the repository before atomic
updates; the database also enforces the attempt ceiling.

## Preview and bounded backfill

Preview one owned presentation without writes:

```text
POST /api/v1/ppt/presentations/{id}/document/migration-preview
```

It makes no provider/export call and returns status, warnings, unsupported
features, redacted asset mapping summaries, size, schema version, and checksum.

The local administrator backfill defaults to dry-run:

```bash
cd servers/fastapi
python scripts/backfill_canonical_documents.py --dry-run --batch-size 25 --max-records 100
python scripts/backfill_canonical_documents.py --execute --batch-size 25 --max-records 100
python scripts/backfill_canonical_documents.py --execute --start-after UUID --retry-failed --systemic-error-threshold 5
```

Batch size is capped at 100 and the run at 10,000. Selection is cursor-based;
each presentation uses its own session/transaction; duplicate rows are blocked
by a unique constraint and optimistic conflict handling. The JSON summary's
`last_cursor` resumes the next bounded run. `attempts_exhausted` reports rows
that require operator review rather than another automatic retry. Source rows
are never deleted.
There is no unbounded task or production-scale queue claim: Sprint 8 should
move this interface to durable workers and preserve its cursor/state semantics.

## Failure, rollback, and monitoring

Stop on the configured systemic-error threshold. Investigate stable error-code
and count/size-bucket metrics without inspecting presentation content. Retry
only understood `FAILED`, `UNSUPPORTED`, or `NEEDS_REVIEW` records. Validate
schema/checksum parity and shadow structural parity before adding a
presentation/owner token to the cohort.

Rollback reads by disabling canonical read/write/shadow flags; legacy fallback
remains enabled. This requires no data deletion. The Alembic downgrade drops
only the new canonical table and should be used only when its records are no
longer needed; legacy source is unchanged. No legacy column is removable in
Sprint 4.

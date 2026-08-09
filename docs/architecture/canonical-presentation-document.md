# Canonical presentation document architecture

Status: Sprint 4 additive internal rollout. The legacy record and renderer
remain the served authority by default.

## Boundary and ownership

The versioned schema is the authoring truth. It contains stable presentation,
slide, element, text, note, and asset-reference IDs plus logical direction,
geometry, theme tokens, font policy, and controlled export intent. It never
contains ORM objects, owner/workspace authorization, database timestamps,
revision state, React/Konva/DOM instances, executable source, arbitrary HTML,
provider responses, secrets, signed URLs, or local paths.

`modules/presentations/domain` owns strict Python types, bounded semantic
validation, normalization, and checksums. `migrations/legacy_document.py`
performs deterministic V1/V2 conversion. `adapters/` translates to current V2
editor structures and escaped compatibility HTML without making either format
canonical. The generated TypeScript binding and runtime validation live under
`servers/nextjs/generated` and `lib/presentation-document`.

Document content is separate from `presentation_documents` metadata. The table
stores owner scope, revision, checksum, conversion state, redacted failure
metadata, and a private legacy asset lookup. One current row is allowed per
legacy presentation. It is intentionally compatible with a future nullable
`workspace_id`; ownership is not duplicated inside JSON.

## IDs, locale, assets, and revisions

New IDs are UUIDs. Legacy IDs use UUIDv5 derived from presentation identity and
a stable structural path, so repeated conversion is byte/checksum stable.
Array indexes express order but never identity. Text uses `en/ar`,
`ltr/rtl/auto`, paragraph direction, run language, and logical alignment from
Sprint 3. Full canvas bidi behavior remains Sprint 5.

Canonical asset references are UUIDs. Normal writes must resolve IDs through
owner-scoped asset records or the existing row's private legacy mapping.
Legacy conversion may create deterministic UUID aliases for existing paths;
those paths never enter responses or the document. Physical storage remains a
Sprint 9 concern.

Revision 1 is the first persisted row. `PUT` requires `If-Match`; creation uses
`If-Match: 0`, and updates must match the current revision. The update predicate
atomically checks owner, presentation, and revision before incrementing. A
failed validation or stale write leaves the prior document unchanged. Sprint 6
can extend this single revision sequence with patches/history without creating
a competing counter.

## Rollout and observability

Safe defaults are:

```text
CANONICAL_DOCUMENT_READS_ENABLED=false
CANONICAL_DOCUMENT_WRITES_ENABLED=false
CANONICAL_SHADOW_RENDER_ENABLED=false
LEGACY_DOCUMENT_FALLBACK_ENABLED=true
CANONICAL_INTERNAL_COHORT=
```

The cohort is an operator-set comma list of `presentation:<uuid>` and/or
`owner:<uuid>` tokens; empty or malformed values fail closed. Preview remains
non-persistent. Reads/writes require the relevant flag and cohort membership.
When no canonical row exists, enabled cohort reads may convert in memory and
serve the legacy fallback. No global canonical write is enabled in Sprint 4.

Shadow mode runs from the authoritative legacy single-presentation read,
converts the legacy path, and compares normalized renderer input by slide
count, element count, and supported/unsupported categories. Shadow errors fail
open to the unchanged legacy response; the canonical endpoint may also expose
the comparison status to an explicitly enabled cohort. Metrics contain only finite event
names, schema/legacy versions, status/error codes, size/count buckets, and
element categories—never titles, text, notes, prompts, URLs, or paths.

Sprint 5 should consume the adapter contract while replacing editor/renderer
internals. Sprint 6 extends revision semantics. Sprint 9 replaces private path
mappings with object-storage identities. Sprint 16 validates export capability
hints; Sprint 4 does not enable or promise the current exporter.

# Editor command system

Status: Sprint 5 canonical editor contract. This contract is frontend state
management, not backend authorization or Sprint 6 revision persistence.

## Ownership and state

`servers/nextjs/components/editor` owns the canonical editor boundary. One
validated `PresentationDocument` is held in `EditorHistoryState`; selection,
hover, active text editor, viewport, guides, and transform previews live in
`EditorViewModel` and are never written into the document. The explicit
`canonicalToEditorViewModel` and `editorViewModelToCanonicalOperation`
functions mark the two sides of that boundary.

The canonical editor uses stable UUIDs for identity. Selection supports
single, shift-toggle, marquee, select-all-visible, nested elements, and escape
clear. Hidden elements are excluded from canvas selection but remain in the
layer tree. Locked elements may be selected and unlocked, but ordinary
mutations reject the locked element or a locked descendant.

The old Redux slide snapshots, presentation hook, custom-template React-code
history, and Template V2 component-local history remain only for legacy
fallback flows. They are not imported by the canonical editor and must not be
connected to canonical documents.

## Command contract

Every authoring change is a serializable discriminated command with a bounded
`commandId`, `type`, stable `targetIds`, and typed `payload`. The implemented
types are:

```text
ADD_ELEMENT              DELETE_ELEMENTS       DUPLICATE_ELEMENTS
UPDATE_ELEMENT           MOVE_ELEMENTS          RESIZE_ELEMENTS
ROTATE_ELEMENTS          REORDER_ELEMENTS       GROUP_ELEMENTS
UNGROUP_ELEMENTS         LOCK_ELEMENTS          UNLOCK_ELEMENTS
HIDE_ELEMENTS            SHOW_ELEMENTS          ALIGN_ELEMENTS
DISTRIBUTE_ELEMENTS      UPDATE_TEXT            UPDATE_STYLE
REPLACE_ASSET            ADD_SLIDE              DELETE_SLIDE
DUPLICATE_SLIDE          REORDER_SLIDES         UPDATE_SLIDE
BATCH
```

`validateCommand` rejects an invalid base document, missing or duplicated
targets, cross-slide targets, locked targets/descendants, invalid parent or
order sets, duplicate IDs, unknown assets, wrong target kinds, unsupported
group shapes, non-finite numbers, functions/symbols/bigints/cycles, and size
limit violations. Applying a command is immutable and the resulting document
passes the complete Sprint 4 runtime validator. The browser is a capability
check only; a future persistence endpoint remains the authorization boundary.

Alignment uses rotated axis-aligned bounds and physical slide coordinates.
The UI says logical start/end, but no RTL geometry mirroring occurs.
Distribution fixes the first and last bounds, computes one gap, and rounds
coordinates to six decimal places to avoid cumulative drift.

## History and inversion

`EditorHistoryState` is the sole canonical history: bounded `past`, `present`,
and `future` with a configurable limit of 1–500 (default 100). A successful
new command clears redo. History validates the input document once and each
new result once; undo/redo reuse known-valid structurally shared `before` and
`after` snapshots and do not clone or serialize the full document. UI locale,
asset loading, autosave, selection, and viewport changes do not enter history.

`invertCommand` exposes a deterministic restore inverse for local use. The
inverse may hold a structurally shared document snapshot and is transient.
Sprint 6 should persist original serializable commands/batches with its base
revision and idempotency key, not these UI undo snapshots. No patch endpoint or
second revision store is added in Sprint 5.

## Interaction commits

Drag, resize, and rotation update `temporaryTransforms` and smart guides only.
Pointer completion emits one command (or one `BATCH` for resize plus rotate);
escape clears the preview. TipTap holds transient editing state and commits a
single `UPDATE_TEXT` on blur/done. Clipboard payloads use
`application/vnd.bayanly.canonical-fragment+json`, version 1, regenerate all
nested IDs, retain only asset IDs already present in the destination document,
and never consume external HTML. Safe plain text may become a text element.

Central shortcuts cover platform undo/redo, copy/paste/duplicate, delete,
nudge, select all, escape, and viewport zoom. Typing targets suppress editor
shortcuts except escape.

# Renderer architecture

Status: Sprint 5 controlled canonical rollout. Legacy fallback remains on by
default.

## Supported flow

```text
PresentationDocument (validated canonical authoring truth)
  -> transient editor view model
     -> typed command store/history
     -> canonical Konva stage (editing)
  -> shared render adapters
     -> canonical browser slide (preview)
  -> capability manifest
     -> future export adapter (Sprint 16)
```

Renderer state never becomes authoring truth. Konva nodes, DOM state, TipTap,
resolved URLs, image objects, viewport, selection, transforms, and guide
candidates are transient.

## Modules

`servers/nextjs/renderers/shared` owns exhaustive canonical element names,
capabilities, physical geometry, bounded styles, logical direction, asset/font
capabilities, scoped asset resolution, and rollout flags.

`renderers/konva` separates the stage, slide scene, element registry, text,
image/icon, shape/line/arrow/vector, table/chart, group/container renderers,
guide overlay, transform overlay, and interaction adapter. Drag previews do not
change the canonical document. Hidden elements do not mount. Locked elements
render but are not draggable/transformable.

`renderers/browser` uses the same canonical union and shared adapters. It emits
React DOM/SVG only: no raw HTML, runtime CDN, code compiler, document callback,
`eval`, or `new Function`. The existing Template V2 preview accepts an optional
canonical document/slide and selects this path only under the browser flag;
its escaped legacy converter remains the rollback path.

Both registries are TypeScript-exhaustive across text, image, shape, line,
arrow, vector, icon, table, chart, container, and group. A registry miss has a
visible red placeholder. An invalid runtime document produces a visible
boundary error; it is never partially interpreted or silently dropped.

## Direction and geometry

Document, slide, and paragraph direction resolve from canonical locale and
explicit `ltr`/`rtl`/`auto` values. Auto inherits canonical context; it is not
guessed from the first character. Runs preserve their original logical order,
language, numbers, URLs, punctuation, and email text. Browser paragraphs use
`unicode-bidi: plaintext`; Konva receives direction and physical alignment.
Only logical start/end labels map to left/right. Canvas geometry, layer order,
images, icons, and slide coordinates are never mirrored for Arabic UI.

## Assets and fonts

Renderers accept resolved URLs keyed by canonical `assetId`; documents never
contain URLs. `CanonicalAssetResolver` requires matching presentation context,
looks up declared canonical metadata, accepts only scoped relative paths or
credential-free HTTPS, detects expiry, caches resolution state per
presentation/session scope, and returns a visible fallback for missing,
unauthorized, unsafe, expired, or failed assets.
It rejects `file:`, `data:`, `javascript:`, local HTTP, and arbitrary external
schemes. Signed URLs stay in memory only. The provider interface can use local
compatibility storage now and an authorized object-storage service later.

The platform capability manifest bounds MIME types and raster dimensions and
accepts script coverage only from a verified platform font registry. Canonical
or user-supplied font metadata never expands these capabilities.

## Rollout and fallback

Safe defaults are:

```text
CANONICAL_KONVA_RENDERER_ENABLED=false
CANONICAL_BROWSER_RENDERER_ENABLED=false
UNIFIED_EDITOR_COMMANDS_ENABLED=false
LEGACY_RENDERER_FALLBACK_ENABLED=true
```

Public `NEXT_PUBLIC_` aliases are recognized for browser cohort builds. Direct
canonical components are internal contracts; application dispatch goes through
the flag boundary. Existing Template V2 god files moved to
`components/slide-editor/renderers/legacy`; their former paths are small
deprecated facades so existing callers and rollback behavior remain intact.

`compileLayout` remains a legacy compatibility compiler behind the existing
production-off unsafe-layout gate. Canonical documents and canonical
registries never import or invoke it. Removal requires declarative conversion
of retained custom layouts plus zero enabled production use.

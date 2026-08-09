# Presentation Document v1

`v1.schema.json` is the renderer-, editor-, provider-, and persistence-neutral
authoring contract for a Bayanly presentation. It is generated from
`scripts/generate-presentation-document.mjs`; that same source deterministically
generates `servers/nextjs/generated/presentation-document.ts`. Generated output
has no timestamps. Run `npm run canonical:generate` after changing the source
and `npm run canonical:check` in review and CI.

The fixed schema identifier is
`https://schemas.bayanly.com/presentation-document/v1.schema.json`; the first
document version is `1.0.0`. Patch versions may clarify validation without
changing accepted data. Additive optional fields require a minor version and
must remain safe for old readers. Removed or reinterpreted fields require a new
schema directory. V1 rejects unknown properties. Its controlled `extensions`
array accepts namespaced scalar data only; nested arbitrary payloads are not an
extension mechanism.

Coordinates use the current 1280×720 logical canvas. Geometry is a
renderer-independent view-box value, not a browser pixel promise. `x/y` may
bleed beyond the canvas within bounded limits; width and height are positive.
All alignment uses `start/center/end/justify`, and direction uses
`ltr/rtl/auto`. Stable IDs are UUIDs and do not depend on array position.

Assets are referenced only by UUID. URLs, filesystem paths, signed URLs, and
provider objects do not belong in the document. A private database-side
compatibility lookup resolves legacy paths until the Sprint 9 storage
migration; API authorization separately proves ownership of every asset ID.

Application validation adds whole-document rules JSON Schema cannot express:
global ID uniqueness, contiguous slide order, reference integrity, group
cycles/depth, consistent tables, total complexity, private-network URL
rejection, and deterministic checksums. Limits are safety limits, not plan
entitlements:

- 5 MiB canonical JSON; 200 slides; 500 elements per slide; 5,000 total.
- 2,000 assets; eight group levels; 2,000,000 text characters.
- 50,000 note characters per slide; 100×50 tables; 5,000 chart points.
- 100,000 characters per text run and explicit bounds on geometry and style.

Normalization is UTF-8 JSON with Unicode preserved, object keys sorted,
insignificant whitespace removed, and integral numbers serialized without a
decimal suffix. SHA-256 is used only for integrity/parity, never authorization.
Fixtures under `fixtures/` are consumed by both Python and TypeScript tests.

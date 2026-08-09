# Renderer capability manifest

Status: Sprint 5 verified implementation scope. `SUPPORTED` means the canonical
feature has a direct path, not pixel identity or PPTX editability. `PARTIAL`
and `RASTERIZED` are intentional fallback signals.

| Feature | Konva | Browser | Export compatibility | Notes |
| --- | --- | --- | --- | --- |
| text | SUPPORTED | SUPPORTED | PARTIAL | Paragraph direction/alignment and common run style; Konva rich mixed-run metrics require visual review |
| mixed bidi | PARTIAL | SUPPORTED | PARTIAL | No reversal; browser uses plaintext bidi; Konva depends on browser canvas shaping |
| image | SUPPORTED | SUPPORTED | RASTERIZED | URL supplied only by scoped resolver |
| image crop | PARTIAL | SUPPORTED | PARTIAL | Browser focal object position; Konva currently fits resolved bitmap without full crop-window parity |
| shape | SUPPORTED | SUPPORTED | SUPPORTED | Rectangle, rounded rectangle, ellipse, triangle, diamond |
| line/arrow | SUPPORTED | SUPPORTED | SUPPORTED | Controlled points, dash, arrow heads |
| vector | SUPPORTED | SUPPORTED | PARTIAL | Canonical point vectors only; no arbitrary SVG/XML |
| icon | PARTIAL | PARTIAL | RASTERIZED | Asset-backed icons render; named icons use visible safe placeholders |
| table | SUPPORTED | SUPPORTED | PARTIAL | Canonical rows/cells/text; browser honors spans; Konva span parity is limited |
| chart | PARTIAL | PARTIAL | RASTERIZED | Controlled bar/pie/donut visual adapter; no Chart.js objects or document callbacks |
| group | SUPPORTED | SUPPORTED | PARTIAL | Nested IDs/transforms retained; depth enforced by canonical validator |
| container | SUPPORTED | SUPPORTED | PARTIAL | Children retained; layout intent recorded, not a browser reflow instruction |
| gradients | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | Not in canonical v1 style contract; visible capability failure, no invented field |
| shadows | SUPPORTED | SUPPORTED | PARTIAL | Common canonical shadow fields |
| notes | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | Notes remain canonical data but are not slide visuals |
| RTL | SUPPORTED | SUPPORTED | PARTIAL | Logical alignment, no geometry mirroring |
| fonts | PARTIAL | PARTIAL | PARTIAL | Platform policy/fallbacks supported; exact shaping depends on installed/authorized font assets |
| hidden elements | SUPPORTED | SUPPORTED | SUPPORTED | Omitted from normal canvas/preview; retained in document/layer panel |
| locked elements | SUPPORTED | SUPPORTED | SUPPORTED | Visual output unchanged; editor mutation capability is restricted |

The typed source of truth is
`servers/nextjs/renderers/shared/capability.ts`. Tests require every canonical
element key in both registries and every capability manifest. Unsupported
status drives visible fallback and future parity/export decisions; it never
deletes canonical data.

Legacy is `LEGACY_ONLY` in the manifest because its schema-specific behaviors
are compatibility promises, not canonical renderer claims. The Sprint 16
export column is deliberately conservative and does not claim editable PPTX.

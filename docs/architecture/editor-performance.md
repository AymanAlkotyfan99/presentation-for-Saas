# Editor performance architecture

Status: Sprint 5 measured frontend-core baseline. Results describe this one
development run, not all customer hardware.

## Design

Only the active slide mounts in the canonical Konva editor. Browser images use
lazy decoding; Konva receives only currently resolved visible asset URLs.
Element registries have stable UUID keys. Drag updates transient geometry and
does not clone, stringify, validate, or commit the document per pointer frame.
The command commit performs one canonical result validation. Undo/redo swap
known-valid structurally shared snapshots. History is bounded to 100 by default
and never enters the canonical document.

Snapping indexes slide/element edge and center candidates once per active-slide
or selection change, sorts each axis, then uses binary search per pointer
sample. The threshold is divided by zoom to remain screen-consistent. It is
disabled with Alt. This avoids pairwise O(N²) guide scans.

The internal visual page mounts canonical browser and Konva renderers side by
side at `/internal/canonical-renderer-fixtures`; production returns 404 unless
`INTERNAL_CANONICAL_RENDERER_FIXTURES_ENABLED=true`. It uses deterministic
fonts/data and no network asset.

## Reference fixtures and budgets

Fixtures are deterministic and remain under the Sprint 4 5,000-element limit:

| Fixture | Validation budget | Command budget | Undo budget | Active-slide snap-index budget |
| --- | ---: | ---: | ---: | ---: |
| 10 slides / 100 elements | 200 ms | 300 ms | 25 ms | 100 ms |
| 30 slides / 1,000 elements | 600 ms | 900 ms | 25 ms | 150 ms |
| 50 slides / 3,000 elements | 1,500 ms | 2,200 ms | 25 ms | 200 ms |

Heap growth budget per fixture test is 200 MiB. These deliberately tolerate CI
contention while detecting algorithmic regression.

## Measured run

Measured 2026-08-09 on Windows with Node 22.17.1. CPU/RAM identity was not
available inside the restricted environment. The five focused Sprint 5 test
files ran concurrently; numbers use `performance.now()` around each operation.

| Fixture | Validate | Command apply | Undo | Snap index | Observed heap growth |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 / 100 | 70.10 ms | 55.96 ms | 0.68 ms | 1.37 ms | 1.03 MiB |
| 30 / 1,000 | 226.82 ms | 266.02 ms | 0.03 ms | 0.78 ms | 2.49 MiB |
| 50 / 3,000 | 461.44 ms | 342.65 ms | 0.02 ms | 0.42 ms | 7.19 MiB |

All measured core budgets passed. Snap time is for the active slide, which has
10, 34, and 60 elements respectively; inactive slides are intentionally not in
the pointer path.

Browser initial editor render, slide-switch paint, real Konva drag frame time,
GPU memory, and asset decode time were not reliably measurable in the Node-only
environment and are not claimed. The editor has a privacy-safe browser observer
for frame-time buckets and bounded long-task counts, and the fixture page is the
manual measurement surface before private alpha. Metrics contain only renderer,
schema version, count/depth/time buckets, command type/status, asset status, and
parity status—never text, notes, prompts, clipboard, URLs, filenames, or paths.

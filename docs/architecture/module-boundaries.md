# Module boundaries and migration architecture

Status: active, Sprint 1. Owners below are logical ownership domains rather
than a claim about a particular person. The executable source of truth is
`config/architecture-boundaries.json`; `npm run check:boundaries` rejects
unowned routes and forbidden dependency directions.

## Dependency direction

FastAPI route modules are transport adapters. Presentation routes may depend
on `modules/presentations`, template routes on `modules/templates`, and both
may depend on shared models/services. Application modules must not import
FastAPI request objects, provider endpoint modules, provider settings, or
provider SDK clients. Provider selection stays in `provider-integrations` and
passes plain values into presentation workflows.

Next.js `app/` modules compose screens. Product behavior moves incrementally
to `features/`; feature packages may depend on shared `components/ui` and the
slide-editor domain, but shared UI must never depend on feature or route code.
Browser code must not import Electron main-process modules or the separately
versioned presentation-export runtime. Electron is an outer adapter around
the HTTP applications and owns OS integration, packaging, updates, and export
process isolation.

Generated runtime source is checked in only when it is deterministic and has
an explicit generator plus `--check` mode. Runtime code must never generate
`.ts`, `.tsx`, `.js`, or `.jsx` files inside application source directories.
Build output, coverage, logs, SBOM output, and test reports remain untracked.
The canonical schema and generated TypeScript document binding are owned by
the presentations domain. Their generator/check mode is the synchronization
boundary; routes and editors use adapters instead of copying the schema into
renderer-specific types.

## Public interfaces and route ownership

All `/api/*` routes are session-authenticated by `SessionAuthMiddleware`
except login/logout/status/verify and health endpoints explicitly listed in
that middleware. Admin routes additionally require the superuser dependency.
Database ownership filtering is injected through the Phase 0 owner context;
moving a route must not bypass that context.

| Route family | Owner | Public interface | Authentication |
| --- | --- | --- | --- |
| `/api/v1/auth/*` | identity-access | session lifecycle and access tokens | login/logout/status/verify public as configured; token operations session |
| `/api/v1/admin/*` | identity-access | users and provider settings administration | session + superuser |
| `/api/v1/async-tasks/*` | task-orchestration | task list/status | session + owner scope |
| `/api/v1/ppt/presentation/*`, `/presentations/*/document`, `/outlines/*`, `/slide/*` | presentations | presentation CRUD, canonical preview/read/write/convert, generation, editing, export preparation | session + owner scope; canonical flags/cohort |
| `/api/v1/ppt/template/*` | templates | template preview, creation, layouts, blocks, CRUD | session + owner scope; defaults read-only |
| `/api/v1/ppt/chat/*` | presentation-chat | conversations, history, message stream | session + owner/resource scope |
| `/api/v1/ppt/theme*` | themes | theme list/create/update/delete/generate | session + owner scope |
| `/api/v1/ppt/files/*`, `/fonts/*`, `/images/*`, `/icons/*` | asset-storage | bounded upload/search/generated-asset operations | session; Phase 0 path/operation controls |
| `/api/v1/ppt/openai/*`, `/google/*`, `/anthropic/*`, `/ollama/*`, `/codex/auth/*` | provider-integrations | model discovery and provider authentication | session |
| `/api/v1/webhook/*` | integrations | webhook subscriptions/delivery interface | session + owner scope |
| `/api/v1/mock/*` | test-infrastructure | guarded test completion/failure hooks | session and environment guard |
| `/api/v1/health/live`, `/ready` | runtime | liveness/readiness | public, excluded from OpenAPI |

Every Python module containing a route decorator is enumerated in the boundary
configuration. A new route fails CI until it has an owner.

## Renderer and schema inventory

`PresentationRender` is the active presentation facade. It can dispatch to
the legacy `V1ContentRender` for persisted V1 decks and to the Template V2
Konva/HTML render path for V2 decks. `TemplateV2KonvaSlide` and
`components/slide-editor/surface/nodes.tsx` are active editor/render surfaces.
`V1ContentRender` remains reachable from presentation rendering and dashboard
thumbnails; it is deprecated, not dead. `V1SelectEdit` has no active importer
and is retained only as a time-boxed deletion candidate pending telemetry and
manual UI verification.

Persisted `PresentationVersion.V1_STANDARD` reads and writes default on for
compatibility. Operators can separately set `LEGACY_V1_READS_ENABLED=false`
or `LEGACY_V1_WRITES_ENABLED=false`; `ARCHITECTURE_FACADES_ENABLED` records the
facade rollout and defaults on. These are rollback controls, not permission to
remove the V1 schema. New creation paths write V2. V1 deletion requires: zero
read/write telemetry for a release, a tested data conversion/export path, and
explicit product/data-owner approval.

## Strangler sequence

1. Transport adapters delegate low-risk persistence and policy to modules;
   paths, status codes, response models, and transactions stay unchanged.
2. New behavior is added only behind the application/feature facades.
3. V1 write traffic is disabled and observed, then V1 reads are disabled and
   observed. Either flag can be restored without a schema rollback.
4. Deprecated files are removed only after their deprecation-register exit
   evidence is satisfied.

## Background task catalog

| Task | Trigger/implementation | Persistence | Retry/recovery | Owner |
| --- | --- | --- | --- | --- |
| presentation generation | `presentation /generate/async`, FastAPI `BackgroundTasks` | `AsyncTaskModel` | status persisted; client may retry a failed request; no durable worker lease | presentations |
| template creation | `template /create/async`, FastAPI `BackgroundTasks` | `AsyncTaskModel` with progress | status persisted; no cross-process durable queue | templates |
| slide asset generation | presentation streaming `asyncio.create_task` | presentation/slide state and asset files | request-process scoped; stream reports errors | presentations |
| template layout generation | bounded thread pools plus async coordination | template layouts/task progress | partial progress persisted by task path | templates |
| export conversion/rendering | `ExportTaskService` subprocess/HTTP adapter | output paths/files | operation timeout/concurrency controls from Phase 0; caller retries | export-runtime |
| operation-security lease renewal | middleware `asyncio.create_task` | in-memory/DB-backed controls | cancelled at operation end; readiness verifies controls | runtime |
| font preview processing | bounded async child tasks | font/image assets | request scoped; aggregate failure returned | asset-storage |

The in-process tasks are not a durable distributed queue. Deployments must not
assume a task survives process termination; a future queue migration must keep
the `AsyncTaskModel` status contract or version its API.

## Storage ownership catalog

| Location/type | Writer | Reader | Lifetime and rule |
| --- | --- | --- | --- |
| application database | SQLModel repositories/services | API/services | durable; Alembic owns schema |
| `APP_DATA_DIRECTORY` | image/font/template services | `/app_data`, render/export | durable user data; owner/path checks mandatory |
| `TEMP_DIRECTORY` | `TempFileService`, upload/decompose/export staging | document loaders/export | ephemeral; resolved paths must remain inside root |
| packaged `static/` | build process only | FastAPI and renderers | immutable at runtime |
| Next.js `public/brand/v1` | repository/build only | web shell | versioned immutable approved assets |
| Electron `resources` / `build/brand/v1` | repository/build only | Electron shell/packager | versioned immutable approved assets |
| presentation-export runtime | sync script with pinned artifact manifest | Electron/FastAPI export adapter | separately versioned compatibility boundary |
| user provider configuration | atomic user config store | provider integration layer | durable local secret-adjacent config; never log values |

Dynamic imports are limited to build/runtime isolation (Electron), optional
provider integrations, and generated Google-font metadata. Runtime assets must
be resolved through the existing resource/path helpers; importing arbitrary
code from user-writable storage is forbidden.

## Cleanup evidence

`api/v1/ppt/endpoints/layouts.py` was an unregistered router: it was not
included by `api/v1/ppt/router.py`, absent from the checked-in OpenAPI contract,
and had no importer or test caller. It is therefore removed in Sprint 1. Other
legacy renderers, schema models, old branded assets, environment variables,
Docker names, and external-runtime identifiers remain until their documented
compatibility exits are met.

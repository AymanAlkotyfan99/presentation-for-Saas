# Presenton Executive Restructuring and Delivery Roadmap

Status: future delivery plan based on the repository after the Phase 0 stabilization work. Nothing in this document authorizes treating Phase 0 as a public-launch approval, and none of the future sprints described here has been implemented by creating this file.

## 1. Executive Transformation Summary

### Current state after Phase 0

Presenton remains a useful presentation-generation product with three active applications: a Next.js web application in servers/nextjs, a FastAPI application in servers/fastapi, and an Electron desktop wrapper in electron. Phase 0 adds a safer engineering floor: protected administrator bootstrap, centralized outbound-request and operation-control points, centralized safe Markdown and security headers, privacy-safe telemetry defaults, hardened Electron IPC, production-off switches for unsafe custom layouts and unverified export execution, pinned artifact integrity metadata, secret scanning, supported runtime versions, SBOM generation, and expanded security tests. Representative baseline controls now live in servers/fastapi/api/operation_security.py, servers/fastapi/utils/outbound_http.py, servers/nextjs/lib/safe-markdown.ts, servers/nextjs/lib/security-headers.mjs, servers/nextjs/lib/unsafe-custom-layouts.ts, servers/nextjs/lib/presentation-export-policy.ts, electron/app/ipc/security.ts, config/artifact-integrity.json, and scripts/scan_secrets.py.

That baseline is deliberately not the final SaaS architecture. The data model still stores source text and local file paths on presentations, and stores slide content, renderer UI JSON, and HTML side by side in servers/fastapi/models/sql/presentation.py and servers/fastapi/models/sql/slide.py. The application still carries V1 and V2 behavior, including V1ContentRender.tsx, V1SelectEdit.tsx, TemplateV2 records, Python template schemas, Konva UI models, and HTML conversion. Expensive generation and template work still enters through very large endpoint modules and FastAPI BackgroundTasks. Provider configuration remains a singleton JSON document rather than encrypted workspace-scoped records. There are no durable workspace, entitlement, immutable credit-ledger, subscription, or payment domains.

### Why a heavy refactor is still required

The repository has accumulated product logic around renderer and provider implementations instead of stable domain contracts. For example, servers/fastapi/api/v1/ppt/endpoints/presentation.py mixes request orchestration, generation, persistence, SSE, template hydration, asset work, and export; servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx combines a large interaction surface; and servers/nextjs/components/slide-editor/surface/nodes.tsx and TemplateV2KonvaSlide.tsx contain renderer-heavy behavior. These modules make correctness, tenant isolation, retries, Arabic layout behavior, and safe horizontal scaling difficult to reason about.

The refactor must preserve working generation, editing, templates, and desktop functionality while moving them behind a canonical presentation document, modular domain boundaries, durable jobs, object storage, workspace authorization, and provider-neutral interfaces. A staged strangler migration is safer than a rewrite: introduce new contracts beside legacy behavior, dual-read or shadow-compare, migrate data in reversible batches, cut traffic over behind feature flags, then delete legacy code only after compatibility telemetry and rollback windows pass.

### Valuable parts to keep

- The Next.js editor and Konva primitives under servers/nextjs/components/slide-editor provide substantial interaction and rendering value.
- The generation, chat, outline, image, template, and export behavior under servers/fastapi/api/v1/ppt, servers/fastapi/services, servers/fastapi/templates, and servers/fastapi/utils/llm_calls contains product knowledge that should be extracted rather than discarded.
- SQLModel, Alembic, FastAPI Users, owner filtering, and the Phase 0 security control points are appropriate foundations.
- The template library under templates, static icons, font utilities, PPTX handling, and the checked export runtime are valuable subject to provenance and compatibility work.
- The Electron application is a viable desktop distribution shell once it consumes the same versioned API and canonical document as the web product.
- Existing unit, integration, Cypress component, metadata, integrity, privacy, SSRF, auth, and Electron security tests form the first regression suite.

### Parts that must not become the long-term architecture

- Renderer-specific ui and html_content fields must not remain the business source of truth.
- Raw local paths in PresentationModel.file_paths and ImageAsset.path must not identify commercial assets.
- FastAPI BackgroundTasks and process-local task sets must not execute commercial AI, image, conversion, or export work.
- ProviderSettings.config must not remain a global plaintext JSON secret container.
- User-visible credits must not be calculated from raw model tokens, and provider response objects must not leak into billing or presentation schemas.
- Template-supplied executable source and dynamically compiled layouts must not be re-enabled as a production customization mechanism.
- SQLite must remain a local-development convenience only; the commercial source of truth is PostgreSQL.
- Root-run all-in-one containers, local-disk coordination, and unbounded in-request fan-out must not be the launch topology.

### Proposed final modular architecture

Use a modular monolith for the HTTP and domain layer, with modules for identity/workspaces, presentations, revisions, assets, jobs, providers, generation, exports, conversions, entitlements, usage/credits, payments, administration, and audit. A single PostgreSQL database may initially host schemas for all modules, but ownership and dependency direction must be explicit. Redis supplies distributed limits, short-lived coordination, and queue/broker functions; it is not a source of truth. Durable Python workers consume versioned jobs written through a transactional outbox. S3-compatible storage holds immutable, checksum-addressed objects. Next.js uses versioned API clients and a generated TypeScript canonical-document binding. Export and untrusted conversion run in isolated workers with scoped object capabilities.

### Provider-agnostic strategy

Create stable internal interfaces for TextAIProvider, ImageAIProvider, SearchProvider, StorageProvider, ExportProvider, PaymentProvider, NotificationProvider, and MalwareScanner. Registries advertise capabilities and regional/plan availability. Every job records an immutable provider-configuration snapshot by internal identifiers, while encrypted credentials remain outside job payloads. Common wrappers enforce endpoint policy, timeout budgets, bounded retry, circuit breaking, idempotency, metering, redaction, and emergency disable switches. Business models contain only provider-neutral result and cost records. Providers that can operate lawfully and reliably in Syria are selected through configuration and policy; no provider is declared universally available or hardcoded as the Syrian provider.

### Planning assumptions for approximately 10,000 users

The figures below are capacity-planning assumptions, not measured facts. Sprint 20 must replace them with load-test and production measurements.

| Dimension | Planning assumption |
|---|---|
| Registered users | 10,000 accounts across up to 3,000 workspaces |
| Daily active users | 2,500 on a normal day; 3,500 during launch campaigns |
| Peak authenticated sessions | 800 active sessions in a 15-minute peak |
| Concurrent web requests | 250 in flight; 100 requests/second sustained and 300 requests/second short burst, excluding CDN assets |
| Concurrent AI jobs | 60 text-generation jobs, with per-provider and global admission limits |
| Concurrent image jobs | 100 image jobs, independently retryable and bounded by plan/provider budgets |
| Concurrent exports | 24 export jobs; memory-heavy exports isolated from API instances |
| File upload throughput | 20 simultaneous uploads, up to 25 accepted objects/second and 50 MB/second aggregate ingress after direct-to-object-storage adoption |
| Storage growth | 40–60 GB/day gross at launch, with lifecycle cleanup targeting less than 15 TB retained in year one |
| Database load | 500 reads/second and 150 writes/second peak through a pooler; fewer than 200 physical PostgreSQL connections |
| Queue backlog | Normal ready backlog below 250; warning at 500 or five minutes oldest age; critical at 2,000 or fifteen minutes, with per-class fairness |

Capacity must be segmented by operation: browser traffic, generation, images, exports, conversions, webhook delivery, and maintenance must not starve one another. All queues and caches require finite retention and backpressure.

### Migration and release stages

1. **Internal development:** establish module contracts, PostgreSQL-only CI coverage, canonical-document fixtures, provider fakes, and staff-only feature flags.
2. **Private alpha:** migrate test workspaces and selected legacy presentations; run shadow conversion, worker, export, Arabic, and accounting checks without charging users.
3. **Closed beta:** enable workspaces, plans, selected providers, object storage, and payment review for invited cohorts; maintain legacy read compatibility and staffed rollback.
4. **Syrian commercial launch:** require legal/provider review, Arabic and English quality gates, local payment operations, restore and incident drills, penetration testing, cost controls, and measured capacity.
5. **Broader regional launch:** add locale/payment/provider adapters through the same contracts, validate data residency and consumer-law requirements per market, and scale only from observed SLO and capacity data.

## 2. Architecture Principles

1. **Modular monolith first.** Keep one deployable API/domain codebase until independent scaling or ownership is measured; workers are separate processes because their failure and resource profiles differ.
2. **Clear module boundaries.** Modules own tables, commands, events, and authorization policies. Cross-module writes occur through application services or events, never arbitrary model imports.
3. **PostgreSQL as commercial source of truth.** SQLite remains only for simple local development and focused tests. CI exercises PostgreSQL migrations, locking, constraints, and query plans.
4. **Durable queues and workers.** AI, image, export, conversion, notification, and maintenance operations execute from durable bounded queues with cancellation, heartbeats, leases, and dead-letter handling.
5. **Transactional outbox.** State transitions and event publication commit atomically; consumers are idempotent and inbox/deduplication aware.
6. **S3-compatible object storage.** Database records identify immutable objects by internal IDs, checksum, and storage key; paths and provider URLs are implementation details.
7. **Canonical presentation document.** A versioned, validated document with stable IDs, logical alignment, asset references, and export intent is the only presentation content source of truth.
8. **Versioned schemas and migrations.** Database, API, event, job, and document versions have forward migration, compatibility windows, fixtures, and rollback procedures.
9. **Workspaces and RBAC.** Every commercial resource belongs to a workspace; owner, admin, editor, viewer, finance-review, and service scopes are enforced server-side.
10. **Provider-neutral integrations.** Stable interfaces, capability discovery, policy routing, encrypted configuration, and normalized results prevent provider leakage into business models.
11. **Immutable financial ledgers.** Credits, grants, charges, releases, refunds, and payment events are append-only, balanced, idempotent, and auditable.
12. **Idempotency.** Mutating APIs, jobs, webhooks, payment decisions, and usage settlement require scoped idempotency keys and uniqueness constraints.
13. **Observability.** Structured logs, metrics, traces, identifiers, audit events, SLOs, and cost attribution are designed into commands and jobs.
14. **Privacy by design.** Collect only necessary data, default analytics and recording off until consent, redact payloads and secrets, and enforce retention and deletion.
15. **Arabic and RTL are first-class.** Logical direction, bidi text runs, Arabic fonts, shaping, locale-aware validation, and RTL visual regression are schema and renderer concerns, not CSS afterthoughts.
16. **No Kubernetes without evidence.** Begin with managed database/cache/object storage and a small number of horizontally scaled container services; adopt Kubernetes only if measured operational needs justify its cost.
17. **No unnecessary microservices.** Network boundaries are reserved for resource isolation, provider/legal constraints, or independently measured scaling.
18. **Horizontal scaling readiness.** HTTP instances remain stateless, security coordination is distributed, migrations are rolling-safe, jobs are leased, and uploads bypass local API disks.
19. **Finite work.** Every request, response, retry, queue, cache, upload, and provider operation has explicit size, time, attempt, and concurrency bounds.
20. **Secure defaults and reversible delivery.** High-risk capabilities default off, privilege is least-authority, migrations are expand/backfill/contract, and every cutover has an observable rollback.

## 3. Target Architecture

### Component map

    Browser / Electron
        |
        v
    CDN + Reverse Proxy + TLS + request limits
        |
        +--> Next.js Web Application (stateless UI/BFF only)
        |
        +--> FastAPI Modular Monolith
               |--> identity + workspaces + RBAC
               |--> presentations + revisions
               |--> assets + uploads
               |--> jobs + outbox
               |--> providers + generation
               |--> entitlements + ledger + payments
               |--> administration + audit
               |
               +--> PostgreSQL through connection pooler
               +--> Redis for limits, cache, coordination, and broker
               +--> S3-compatible Object Storage
               +--> Durable Worker Pools
                       |--> AI/outline workers
                       |--> image workers
                       |--> export workers
                       |--> Gotenberg/file-conversion workers
                       |--> webhook/notification workers
               +--> Metrics, logs, traces, and privacy-safe error tracking

### Initial colocation and mandatory isolation

For internal development, Next.js, FastAPI, Redis, PostgreSQL, and a general worker may run in Docker Compose; a local storage adapter may emulate object storage. During private alpha, the same modular monolith can serve API and administration routes, and low-volume AI/image jobs may share a worker deployment with distinct queues and concurrency pools.

Before any public paid launch, PostgreSQL and Redis must be managed or independently durable; uploads must go directly to S3-compatible storage; API and Next.js must be horizontally scalable and stateless; export and office/PDF conversion must run outside the API container with CPU, memory, process, network, and time limits; payment review and finance audit access must be separately authorized; malware scanning must precede document processing; and worker queues must have independent admission limits. Gotenberg or an equivalent conversion implementation is an ExportProvider/FileConversionProvider adapter, not a business-domain dependency.

### Contract boundaries

- Next.js consumes OpenAPI-derived clients and canonical-document TypeScript bindings; it does not reach into database or provider configuration.
- FastAPI commands validate workspace authorization, entitlement, idempotency, and revision preconditions before writing.
- PostgreSQL transactions write domain state, immutable ledger entries where applicable, and outbox records together.
- Workers claim finite jobs, load encrypted provider references through a secret service, read/write scoped objects, emit normalized results, and settle usage only after durable success.
- Object access uses short-lived, purpose-bound capabilities. Export workers never receive general session cookies or arbitrary internal URLs.
- Electron exposes a narrow preload contract and uses the same API/document versions; local-only features remain explicitly separate from SaaS authority.

## 4. Complete Sprint List

### Sprint 1 — Repository Rationalization and Architecture Boundaries

- **Business objective:** Make ownership and migration boundaries explicit so future work can ship without repeatedly breaking generation, editor, desktop, or export paths.
- **Why this sprint is necessary:** The current repository mixes V1/V2 behavior and large cross-cutting modules; every later sprint needs a stable map and dependency rules.
- **Current technical problems:** Presentation orchestration, template hydration, generation, SSE, persistence, and export share one endpoint file; frontend pages and editor surfaces contain multi-thousand-line components; duplicate V1/V2 render paths remain.
- **Evidence from the repository:** servers/fastapi/api/v1/ppt/endpoints/presentation.py, servers/fastapi/api/v1/ppt/endpoints/template.py, servers/fastapi/services/chat/memory_layer.py, servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx, servers/nextjs/components/slide-editor/surface/nodes.tsx, servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx, servers/nextjs/app/(presentation-generator)/components/V1SelectEdit.tsx, and servers/nextjs/components/slide-editor/surface/TemplateV2KonvaSlide.tsx show the overlap. Phase 0 also proved the need for a permanent generated-file policy by removing tracked TypeScript build metadata, coverage state, and an empty Alembic SQLite sentinel.
- **User-facing problems caused by the current design:** Changes produce regressions across editing, generation, templates, and exports; behavior differs by presentation version; recovery and error messages are inconsistent.
- **Security implications:** Oversized handlers hide authorization and limit gaps; generated/runtime artifacts risk leaking state; executable custom-layout legacy paths are difficult to contain.
- **Scalability implications for approximately 10,000 users:** Mixed responsibilities prevent independent worker scaling and make database/query hot spots hard to measure.
- **Provider-agnostic implications:** Provider calls are interwoven with orchestration; boundaries must prevent provider SDK objects from crossing into presentation or billing domains.
- **Scope:** Inventory reachable routes, commands, models, renderers, generated assets, packages, and V1/V2 behavior; define module dependency rules and deprecation records; add architecture checks.
- **Explicit out-of-scope items:** No canonical schema migration, visual rebrand, provider rewrite, or end-user feature change.
- **Existing files to modify:** README.md, servers/fastapi/api/main.py, servers/fastapi/api/v1/ppt/router.py, servers/nextjs/package.json, package.json, and .gitignore for architecture documentation, scripts, and generated-file policy.
- **Existing files to split:** servers/fastapi/api/v1/ppt/endpoints/presentation.py into thin routes and application services; servers/fastapi/api/v1/ppt/endpoints/template.py into import, validation, query, and task services; servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx into conversation, command, and presentation-context features; servers/nextjs/components/slide-editor/surface/nodes.tsx into element renderers.
- **Existing files to deprecate:** servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx, servers/nextjs/app/(presentation-generator)/components/V1SelectEdit.tsx, servers/fastapi/models/sql/presentation_layout_code.py, servers/fastapi/templates/custom_layout_from_db.py, and the V1_STANDARD write path in servers/fastapi/models/sql/presentation.py, all retained read-only until Sprint 4/5 migration.
- **Existing files to delete:** None unconditionally in Sprint 1. Phase 0 already removed servers/nextjs/tsconfig.tsbuildinfo, servers/fastapi/.coverage, and servers/fastapi/placeholder; any further deletion requires reachability evidence and the deprecation register.
- **New files to create:** docs/architecture/module-boundaries.md, docs/architecture/deprecation-register.md, scripts/check-boundaries.mjs, servers/fastapi/modules/__init__.py, and servers/nextjs/features/README.md.
- **Database models and migrations:** No business schema; add a migration smoke-test harness for empty, current, and legacy PostgreSQL databases.
- **API changes:** Freeze and document current v1 routes; add deprecation headers only for endpoints proven to be legacy and provide no removals yet.
- **Frontend changes:** Introduce feature folders and import aliases without changing UI; record V1/V2 entry points.
- **Background-job changes:** Catalog every BackgroundTasks and create_task call with target queue class and idempotency requirements for Sprint 8.
- **Storage changes:** Catalog all persisted local paths and generated assets; no object migration yet.
- **Security controls:** Dependency-boundary linting, generated-file denial, route authorization inventory, and continuation of Phase 0 unsafe-feature flags.
- **Observability requirements:** Baseline route latency, error, export, generation, and task counts tagged by version without content payloads.
- **Migration strategy:** Strangler structure: wrap current behavior behind module facades, then move internals in later sprints; do not bulk rename public routes.
- **Backward-compatibility strategy:** Preserve v1 API shapes and legacy reads; publish a deprecation matrix with owners and removal gates.
- **Feature flags:** architecture_facades, legacy_v1_reads, and legacy_v1_writes; writes default off once Sprint 4 migration begins.
- **Testing strategy:** Import-boundary tests, route snapshots, dead-code reachability checks, package-lock checks, PostgreSQL migration tests, and existing web/backend/Electron suites.
- **Acceptance criteria:** Every active route and renderer has an owner; forbidden dependency directions fail CI; deletion candidates have evidence and tests; no supported behavior disappears.
- **Rollback strategy:** Revert facade wiring while leaving documentation/checks; no irreversible data change occurs.
- **Dependencies on earlier sprints:** Phase 0 security and reproducibility baseline.
- **Risks:** Misclassifying dynamic imports or desktop-only assets as dead; mitigate through runtime coverage and a two-release deprecation register.
- **Complexity:** High.
- **Priority:** P0.
- **Estimated implementation order:** Inventory, dependency map, facade seams, generated-file policy enforcement, then conditional dead-code removal.
- **Deliverables:** Architecture map, package/dead-code report, module skeleton, deprecation register, boundary CI, and two verified cleanup changes.
- **Definition of Done:** CI enforces the documented boundaries, all retained/deprecated paths are classified, and deleted artifacts are proven regenerable or data-free.

### Sprint 2 — Independent Brand and Product Identity

- **Business objective:** Establish a trademark-safe commercial identity while preserving all upstream license and attribution obligations.
- **Why this sprint is necessary:** Presenton names and imagery appear in web, desktop, templates, documentation, package metadata, update behavior, and export resources.
- **Current technical problems:** Brand identity is duplicated across binary assets and strings, so partial replacement would create inconsistent UI and metadata.
- **Evidence from the repository:** servers/nextjs/public/Logo.png, servers/nextjs/public/logo-white.png, servers/nextjs/public/Presenton_Splash.png, servers/nextjs/public/dashboard-header/provider-presenton.png, electron/resources/ui/assets/images/presenton_logo.png, electron/build/logo.png, scripts/presenton-terminal-banner.mjs, package.json, electron/package.json, electron/version.json, README.md, NOTICE, and templates/* assets carry product identity or metadata.
- **User-facing problems caused by the current design:** Users see inconsistent names/icons between browser, installer, exports, terminal, metadata, and notifications.
- **Security implications:** Renamed applications must retain verified update origins and publisher identity; phishing risk rises if old and new signing identities are mixed.
- **Scalability implications for approximately 10,000 users:** Central brand tokens reduce per-channel drift and support localized campaigns without branching applications.
- **Provider-agnostic implications:** Product identity must not imply that a particular AI, image, storage, or payment provider is the product itself.
- **Scope:** Legal name clearance, brand token registry, app metadata, web/Electron assets, notification/export metadata, template audit, redirect/update-domain plan, and notice preservation.
- **Explicit out-of-scope items:** No UI information-architecture redesign, new pricing, or removal of third-party notices.
- **Existing files to modify:** package.json, electron/package.json, electron/version.json, servers/nextjs/app/layout.tsx, electron/build.js, scripts/presenton-terminal-banner.mjs, README.md, NOTICE, docs/macos/dev/README.md, and docs/macos/dev/direct-distribution.md.
- **Existing files to split:** Brand constants embedded in servers/nextjs/app/layout.tsx and Electron build configuration into shared generated metadata.
- **Existing files to deprecate:** Old branded public images and old package/application identifiers for one compatibility release.
- **Existing files to delete:** Old brand binaries only after all references, installers, snapshots, update manifests, and templates use approved replacements; LICENSE and NOTICE are never deletion candidates.
- **New files to create:** config/product-identity.json, scripts/generate-product-metadata.mjs, servers/nextjs/lib/product-identity.ts, electron/app/generated/product-identity.ts, docs/legal/brand-transition.md, and approved replacement assets in servers/nextjs/public/brand and electron/build/brand.
- **Database models and migrations:** Optional product_brand_version on export/audit metadata only; no user data rewrite.
- **API changes:** Version public product metadata and email/notification display names; preserve API URLs through redirects.
- **Frontend changes:** Replace icons, titles, Open Graph metadata, splash screens, provider-neutral wording, and accessible alt text.
- **Background-job changes:** Notification and export jobs capture brand-version identifiers so retries remain deterministic.
- **Storage changes:** Version public brand assets with immutable cache keys; retain old assets through compatibility TTL.
- **Security controls:** Domain/publisher allowlist, signed desktop update validation, CSP updates, and anti-phishing review of emails/payment instructions.
- **Observability requirements:** Track old-asset 404s, old-domain traffic, installer/update failures, and brand-version on exports.
- **Migration strategy:** Generate channel-specific metadata from one approved identity file; ship dual assets and redirects before removing old ones.
- **Backward-compatibility strategy:** Preserve existing document schemas and deep links; retain old desktop application IDs if changing them would break upgrades, with legal sign-off.
- **Feature flags:** new_brand_shell and new_export_metadata.
- **Testing strategy:** Metadata consistency, visual snapshots, installer upgrade tests, link checking, export property inspection, and notice/license assertions.
- **Acceptance criteria:** No unapproved Presenton user-facing brand remains; every channel matches the registry; required upstream notices remain intact.
- **Rollback strategy:** Switch generated metadata/assets to the prior approved brand version without changing user data or document IDs.
- **Dependencies on earlier sprints:** Sprint 1 inventory and metadata ownership.
- **Risks:** Trademark conflict, broken desktop upgrades, stale CDN assets, or lost attribution.
- **Complexity:** Medium.
- **Priority:** P1 before external alpha.
- **Estimated implementation order:** Legal clearance, identity registry, web assets, Electron/installer, exports/notifications, redirects, then old-asset retirement.
- **Deliverables:** Approved identity package, generated metadata, replacement assets, upgrade/redirect plan, and attribution review.
- **Definition of Done:** Legal and product owners approve the identity; automated checks find no unintended old-brand references; upgrade and export tests pass.

### Sprint 3 — Arabic/English Application Localization

- **Business objective:** Deliver an accessible bilingual shell with native Arabic RTL behavior, not merely Arabic generated slide text.
- **Why this sprint is necessary:** The launch market requires Arabic and English throughout navigation, forms, validation, account, payment, and editing workflows.
- **Current technical problems:** Web metadata and document language are fixed to English, user-visible strings are embedded in components, and RTL direction is not modeled across the shell.
- **Evidence from the repository:** servers/nextjs/app/layout.tsx sets locale en_US and html lang en; servers/nextjs/app/global-error.tsx also fixes lang=en; servers/nextjs/app/(presentation-generator)/upload/components/UploadPage.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/SettingPage.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, servers/nextjs/app/(presentation-generator)/presentation/components/PresentationActions.tsx, and servers/nextjs/components/Auth/AuthGate.tsx contain user-facing strings; only generated presentation language is carried by PresentationModel.language in servers/fastapi/models/sql/presentation.py.
- **User-facing problems caused by the current design:** Arabic users encounter English navigation/errors, incorrect reading order, physical left/right controls, mixed-direction cursor issues, and non-localized dates/numbers.
- **Security implications:** Authentication, consent, payment review, and destructive-action warnings must be unambiguous in both languages; catalog keys prevent unsafe provider text being rendered as UI.
- **Scalability implications for approximately 10,000 users:** Catalog-driven localization supports translation caching and prevents separate regional forks.
- **Provider-agnostic implications:** Provider errors and capability names are normalized to message keys; providers do not supply trusted localized HTML.
- **Scope:** Locale routing, message catalogs, RTL shell, logical CSS, bidi rules, locale-aware validation/date/number formatting, language switcher, Arabic font registry, translation workflow, accessibility and visual tests.
- **Explicit out-of-scope items:** Canonical slide text-run direction and full RTL editor/export fidelity belong to Sprints 4, 5, and 16.
- **Existing files to modify:** servers/nextjs/app/layout.tsx, servers/nextjs/app/global-error.tsx, servers/nextjs/app/globals.css, servers/nextjs/app/(presentation-generator)/(dashboard)/layout.tsx, servers/nextjs/app/(presentation-generator)/upload/components/*, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/*, servers/nextjs/components/Auth/AuthGate.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, and servers/nextjs/utils/apiErrorMessages.ts.
- **Existing files to split:** Hardcoded copy from servers/nextjs/app/(presentation-generator)/upload/components/UploadPage.tsx, servers/nextjs/app/(presentation-generator)/presentation/components/PresentationActions.tsx, servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx, and servers/nextjs/app/(presentation-generator)/(dashboard)/settings/SettingPage.tsx into feature-scoped catalogs.
- **Existing files to deprecate:** Direct user-visible string literals and physical CSS properties such as left/right where logical properties apply.
- **Existing files to delete:** None until catalog coverage and visual parity are proven; obsolete duplicate English copy modules may then be removed.
- **New files to create:** servers/nextjs/i18n/config.ts, middleware.ts, messages/en.json, messages/ar.json, app/[locale]/layout.tsx, components/LocaleSwitcher.tsx, lib/locale-format.ts, styles/rtl.css, tests/i18n-coverage.test.mjs, and cypress/e2e/rtl-shell.cy.ts.
- **Database models and migrations:** Add user preferred_locale and workspace default_locale with constrained BCP-47 values; keep presentation content language separate.
- **API changes:** Accept and return locale preference; use stable error codes plus parameters rather than server-authored English as the only contract.
- **Frontend changes:** Locale-prefixed routes, persistent accessible switcher, dir and lang updates, logical layout, localized forms/toasts/errors, Arabic font loading.
- **Background-job changes:** Jobs capture requested content locale and notification locale independently; workers emit error codes, not localized markup.
- **Storage changes:** Version and cache font assets; record license/provenance; no user-object change.
- **Security controls:** Escape interpolation, forbid HTML in catalogs by default, lint missing/unused keys, and require bilingual security/finance copy review.
- **Observability requirements:** Locale-tagged route/error metrics without recording entered text; missing-key counters and RTL visual-test results.
- **Migration strategy:** Add catalogs feature by feature; default existing users to English until they select Arabic; infer no locale from sensitive content.
- **Backward-compatibility strategy:** Redirect unprefixed routes to negotiated/default locale while preserving query/deep-link state.
- **Feature flags:** locale_routing, arabic_shell, and arabic_fonts.
- **Testing strategy:** Catalog completeness, interpolation safety, keyboard/screen-reader tests, date/number snapshots, pseudolocale, Arabic/English E2E, and RTL screenshots at supported breakpoints.
- **Acceptance criteria:** Every launch-critical flow is translated, html lang/dir is correct, no horizontal overflow or reversed semantics, and security/payment copy has human review.
- **Rollback strategy:** Keep English catalog and unprefixed route redirect as a safe fallback; disable Arabic routing without altering saved content.
- **Dependencies on earlier sprints:** Sprint 1 boundaries and Sprint 2 approved identity terms.
- **Risks:** Machine-translation errors, font licensing, mixed bidi content, and layout regressions.
- **Complexity:** High.
- **Priority:** P0 for Syrian launch.
- **Estimated implementation order:** Catalog framework, route negotiation, shell, auth/settings, generation/editor, admin/payment placeholders, accessibility, then visual hardening.
- **Deliverables:** English/Arabic catalogs, RTL shell, locale persistence API, font registry, translator guide, and automated localization suite.
- **Definition of Done:** Launch-critical pages have approved Arabic and English copy, meet accessibility checks, and pass mirrored visual and interaction tests.

### Sprint 4 — Canonical Presentation Document

- **Business objective:** Create one durable, versioned presentation representation that can be edited, rendered, exported, migrated, and audited consistently.
- **Why this sprint is necessary:** Workspaces, revisions, workers, RTL editing, export compatibility, and provider neutrality all depend on a renderer-independent source of truth.
- **Current technical problems:** Presentation content is split among source content, outline/layout/structure JSON, slide content, optional HTML, optional UI JSON, template JSON, and frontend-only models.
- **Evidence from the repository:** servers/fastapi/models/sql/presentation.py persists content, file_paths, outlines, layout, structure, theme, and fonts; servers/fastapi/models/sql/slide.py persists content, html_content, properties, and ui; servers/fastapi/templates/v2/schema.py and servers/nextjs/components/slide-editor/model/model.ts define separate shapes; servers/nextjs/lib/template-v2-json-to-html.ts is another adapter.
- **User-facing problems caused by the current design:** Edits can diverge between preview and export, presentation versions behave differently, IDs are unstable across transforms, and older presentations are difficult to recover.
- **Security implications:** HTML/source fields expand the injection surface; canonical validation can reject scripts, unsafe URLs, oversized documents, and cross-workspace asset references at one boundary.
- **Scalability implications for approximately 10,000 users:** Compact versioned documents, stable IDs, indexed metadata, and patchable revisions reduce write amplification and enable worker handoff.
- **Provider-agnostic implications:** AI and import providers return candidate operations or canonical fragments, never provider-specific objects or final renderer HTML.
- **Scope:** JSON Schema, stable presentation/slide/element/text-run IDs, locale/direction, logical alignment, assets, layout intent, speaker notes, export hints, validation, Python/TypeScript bindings, migrations from content/ui/html_content.
- **Explicit out-of-scope items:** Rich editor commands, revision history UI, and exporter replacement are Sprints 5, 6, and 16.
- **Existing files to modify:** servers/fastapi/models/sql/presentation.py, servers/fastapi/models/sql/slide.py, servers/fastapi/templates/v2/schema.py, servers/nextjs/components/slide-editor/model/model.ts, servers/nextjs/types/presentation.ts, servers/fastapi/api/v1/ppt/endpoints/presentation.py, and servers/fastapi/api/v1/ppt/endpoints/template.py.
- **Existing files to split:** servers/fastapi/templates/v2/schema.py into canonical bindings versus template authoring schemas; servers/nextjs/components/slide-editor/model/model.ts into canonical types, editor state, and renderer view models.
- **Existing files to deprecate:** SlideModel.html_content, renderer-specific SlideModel.ui persistence, PresentationModel.layout/structure as independent truth, and direct V1_STANDARD writes.
- **Existing files to delete:** None during expand/backfill; deprecated columns are removed only after Sprint 5/6 read cutover and export parity.
- **New files to create:** schemas/presentation-document/v1.schema.json, servers/fastapi/modules/presentations/domain/document.py, document_validation.py, migrations/legacy_document.py, servers/nextjs/generated/presentation-document.ts, lib/presentation-document/validate.ts, and shared canonical fixtures.
- **Database models and migrations:** Add presentation_documents with presentation_id, schema_version, document JSONB, checksum, revision, created_at; add conversion_status/error fields and constraints; initially retain legacy columns.
- **API changes:** Add v2 document GET, validated PUT with If-Match, and migration-preview endpoints; responses expose schema_version and revision.
- **Frontend changes:** Read canonical documents through a compatibility adapter; show explicit unsupported-version and migration-error states.
- **Background-job changes:** Add bounded legacy-to-canonical migration jobs and canonical-validation jobs; record document version in every future job.
- **Storage changes:** Replace file paths inside new documents with asset UUIDs; actual object migration waits for Sprint 9.
- **Security controls:** Strict schema limits, URL protocol rules, asset ownership checks, no executable code/HTML, canonical JSON checksum, and fuzz-tested parser depth/size limits.
- **Observability requirements:** Conversion success/failure by legacy version, validation code counts, document size, adapter parity, and checksum mismatch alerts.
- **Migration strategy:** Expand table, convert in deterministic batches, shadow-render legacy and canonical outputs, allow per-document fallback, then make canonical writes authoritative.
- **Backward-compatibility strategy:** Legacy readers remain through adapters; preserve original payload snapshots and a reversible mapping until two stable releases after full backfill.
- **Feature flags:** canonical_document_reads, canonical_document_writes, canonical_shadow_render, and legacy_document_fallback.
- **Testing strategy:** JSON Schema conformance, Python/TS cross-language golden fixtures, property/fuzz tests, V1/V2 migration corpus, Arabic/mixed-direction samples, maximum-size tests, and round-trip invariants.
- **Acceptance criteria:** Every supported legacy fixture converts deterministically or records an actionable error; Python and TypeScript agree; no executable content is accepted; shadow parity meets the approved threshold.
- **Rollback strategy:** Disable canonical reads/writes and return to preserved legacy fields; do not drop legacy data in this sprint.
- **Dependencies on earlier sprints:** Sprint 1 boundaries and Sprint 3 locale/direction vocabulary.
- **Risks:** Lossy HTML/UI conversion, schema overfitting to Konva, large JSONB rows, and unstable element identities.
- **Complexity:** Very high.
- **Priority:** P0 architectural foundation.
- **Estimated implementation order:** Vocabulary/fixtures, schema, bindings, validators, conversion, shadow reads, authoritative writes, then backfill.
- **Deliverables:** Versioned schema, generated bindings, conversion report, dual-read adapter, migration job, and compatibility fixtures.
- **Definition of Done:** Canonical documents are authoritative for an internal cohort, all validation and parity gates pass, and every legacy record has a migration state and rollback source.

### Sprint 5 — Renderer and Editor Architecture

- **Business objective:** Provide consistent, high-performance editing and rendering from the canonical document across browser preview, Konva editing, and export.
- **Why this sprint is necessary:** A canonical document only creates value when all renderers consume it and editor actions produce validated document operations.
- **Current technical problems:** Rendering and editing logic is concentrated in large components, persistence concerns leak into renderer models, and undo/redo paths differ between the presentation page and template studio.
- **Evidence from the repository:** servers/nextjs/components/slide-editor/surface/TemplateV2KonvaSlide.tsx, servers/nextjs/components/slide-editor/surface/nodes.tsx, servers/nextjs/components/slide-editor/model/model.ts, servers/nextjs/components/slide-editor/state/state.ts, servers/nextjs/app/(presentation-generator)/presentation/hooks/PresentationUndoRedo.ts, servers/nextjs/store/slices/undoRedoSlice.ts, servers/nextjs/app/(presentation-generator)/custom-template/hooks/useSlideUndoRedo.ts, servers/nextjs/app/(presentation-generator)/components/TemplateV2HtmlSlidePreview.tsx, and servers/nextjs/lib/template-v2-json-to-html.ts show parallel implementations.
- **User-facing problems caused by the current design:** Undo behavior varies, selection/layer commands are hard to predict, HTML and Konva previews differ, and mixed-direction editing is fragile.
- **Security implications:** Renderers must never compile document-supplied code or inject unsafe HTML; asset URLs and text are resolved through typed safe adapters.
- **Scalability implications for approximately 10,000 users:** Efficient selectors, viewport rendering, command patches, and worker-assisted layout reduce browser memory and API payload/write size.
- **Provider-agnostic implications:** Provider-generated content enters through canonical operations; no renderer branches on provider identity.
- **Scope:** Canonical adapters, renderer registry, unified commands, undo/redo, layers, lock/hide, alignment/distribution, snapping/guides, zoom, performance budgets, logical RTL/mixed-direction editing, and preview/export parity hooks.
- **Explicit out-of-scope items:** Multi-user live collaboration, full revision persistence, and exporter internals.
- **Existing files to modify:** servers/nextjs/components/slide-editor/model/*, servers/nextjs/components/slide-editor/surface/*, servers/nextjs/components/slide-editor/selection/*, servers/nextjs/components/slide-editor/layout/*, servers/nextjs/components/slide-editor/text/*, servers/nextjs/app/(presentation-generator)/presentation/components/PresentationPage.tsx, and servers/nextjs/app/(presentation-generator)/components/TemplateV2HtmlSlidePreview.tsx.
- **Existing files to split:** servers/nextjs/components/slide-editor/surface/nodes.tsx into text/image/shape/chart/table/group renderers; servers/nextjs/components/slide-editor/surface/TemplateV2KonvaSlide.tsx into stage, overlays, selection, and event adapters; servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx remains for the feature split begun in Sprint 1.
- **Existing files to deprecate:** servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx, servers/nextjs/app/(presentation-generator)/components/V1SelectEdit.tsx, direct DOM theme mutation in servers/nextjs/app/(presentation-generator)/presentation/utils/applyPresentationThemeDom.ts, servers/nextjs/app/hooks/compileLayout.ts, and duplicate undo stores.
- **Existing files to delete:** servers/nextjs/app/hooks/compileLayout.ts and its custom-template runtime compilation UI only after safe declarative template authoring covers retained use cases and the production-off flag has remained unused.
- **New files to create:** components/editor/commands/*, components/editor/document-store.ts, renderers/konva/*, renderers/browser/*, renderers/shared/asset-resolver.ts, renderers/shared/direction.ts, tests/editor-command-contract.test.ts, and visual fixture pages.
- **Database models and migrations:** No new authoritative model beyond Sprint 4; store editor capability/version metadata in document revisions, not renderer state.
- **API changes:** Accept typed document patch batches with base revision and idempotency key; provide asset/font capability manifests.
- **Frontend changes:** Replace component mutations with commands; one history stack; virtualization; keyboard-accessible layer panel; logical start/end controls; mixed Arabic/Latin text-run tools.
- **Background-job changes:** Optional layout-analysis workers consume immutable document snapshots; browser editing never waits on a provider call.
- **Storage changes:** Renderer resolves asset IDs to scoped URLs and preloads only visible assets; no raw path persistence.
- **Security controls:** No eval/new Function/dangerous HTML, sanitizer defense in depth for legacy preview, URL resolver allowlist, command authorization/validation, and memory/complexity ceilings.
- **Observability requirements:** Frame time, long tasks, memory, command failure, undo depth, renderer parity, and asset-load failure metrics with no slide text.
- **Migration strategy:** Implement adapters per element type, shadow compare screenshots, migrate internal cohorts, and retain read-only legacy renderer fallback until coverage is complete.
- **Backward-compatibility strategy:** Compatibility adapters map legacy documents into canonical view models; unsupported elements render a safe labeled placeholder and preserve data.
- **Feature flags:** canonical_konva_renderer, canonical_browser_renderer, unified_editor_commands, and legacy_renderer_fallback.
- **Testing strategy:** Command unit/property tests, undo/redo invariants, selection/layer keyboard tests, RTL/bidi input, performance fixtures, cross-renderer visual regression, and malicious document fixtures.
- **Acceptance criteria:** Supported elements round-trip without renderer state persistence; undo/redo is deterministic; Arabic/mixed direction behaves correctly; performance budgets pass on reference hardware.
- **Rollback strategy:** Route affected document versions to the legacy read-only renderer while preserving canonical documents and command logs.
- **Dependencies on earlier sprints:** Sprints 3 and 4.
- **Risks:** Visual drift, font metrics, Konva/Tiptap integration complexity, and regressions in large decks.
- **Complexity:** Very high.
- **Priority:** P0.
- **Estimated implementation order:** Command contract, shared resolver/direction, simple elements, text, compound elements, selection/history, performance, then legacy retirement.
- **Deliverables:** Renderer adapters, unified command system, one undo stack, parity suite, RTL editor support, and deprecation report.
- **Definition of Done:** Canonical editing is default for the supported corpus, no executable layout path is needed, and functional, visual, security, and performance gates pass.

### Sprint 6 — Revision-Safe Persistence and Recovery

- **Business objective:** Prevent lost edits and provide reliable recovery, history, restore, and multi-tab behavior.
- **Why this sprint is necessary:** Commercial users must trust that generation, editing, autosave, and retries cannot silently overwrite newer work.
- **Current technical problems:** Autosave computes client diffs but persistence lacks a first-class immutable revision stream, ETags, explicit patch records, and durable recovery semantics.
- **Evidence from the repository:** servers/nextjs/app/(presentation-generator)/presentation/hooks/useAutoSave.tsx, servers/nextjs/app/(presentation-generator)/presentation/utils/autoSaveDiff.ts, servers/nextjs/app/(presentation-generator)/presentation/hooks/PresentationUndoRedo.ts, servers/fastapi/models/sql/presentation.py updated_at, servers/fastapi/models/sql/slide.py, and servers/fastapi/api/v1/ppt/endpoints/presentation.py show mutable row-oriented saving without a revision domain.
- **User-facing problems caused by the current design:** Multiple tabs or stale export actions can overwrite edits; crashes leave ambiguous unsaved state; users cannot inspect or restore history.
- **Security implications:** Revision authorization and immutable audit evidence prevent cross-user restore, forged history, and stale capability reuse.
- **Scalability implications for approximately 10,000 users:** Patch writes, optimistic concurrency, compaction, and bounded local recovery avoid full-document write storms and coordinate many stateless API instances.
- **Provider-agnostic implications:** Provider jobs target an immutable base revision and return proposed patches; completion cannot overwrite later user edits.
- **Scope:** Presentation/slide revisions, optimistic concurrency, ETag/revision fields, typed patches, transactions, IndexedDB recovery, multi-tab coordination, unsaved-state UI, version history, restore, crash recovery, compaction.
- **Explicit out-of-scope items:** Simultaneous collaborative cursors/CRDT and external share links.
- **Existing files to modify:** servers/nextjs/app/(presentation-generator)/presentation/hooks/useAutoSave.tsx, servers/nextjs/app/(presentation-generator)/presentation/utils/autoSaveDiff.ts, servers/nextjs/app/(presentation-generator)/presentation/components/PresentationPage.tsx, servers/fastapi/api/v1/ppt/endpoints/presentation.py, servers/fastapi/models/sql/presentation.py, servers/fastapi/models/sql/slide.py, servers/fastapi/services/database.py, and servers/nextjs/app/(presentation-generator)/services/api/presentation-generation.ts.
- **Existing files to split:** Autosave transport from servers/nextjs/app/(presentation-generator)/presentation/hooks/useAutoSave.tsx into persistence client, local journal, conflict resolver, and UI status hooks.
- **Existing files to deprecate:** Blind full slide/document updates and updated_at-only concurrency decisions.
- **Existing files to delete:** Duplicate undo persistence code only after unified commands and IndexedDB journal are default; no history data is deleted.
- **New files to create:** modules/presentations/domain/revision.py, application/save_revision.py, persistence/revision_models.py, api/revisions.py, alembic revision for revisions, features/presentations/persistence/*, lib/indexeddb/recovery.ts, components/RevisionHistory.tsx, and conflict E2E tests.
- **Database models and migrations:** Add presentation_revisions, revision_patches, current_revision on presentations, parent/base constraints, actor/workspace IDs, checksums, and retention/compaction metadata.
- **API changes:** Conditional PATCH with If-Match, idempotency key, conflict payload, revision list/diff/restore, and autosave acknowledgement containing durable revision.
- **Frontend changes:** Durable local journal, online/offline status, conflict resolution, multi-tab BroadcastChannel lease, history browser, restore confirmation, and never claim saved before acknowledgement.
- **Background-job changes:** Generation/export jobs pin source revision; compaction and retention run as idempotent maintenance jobs.
- **Storage changes:** Revisions reference immutable asset IDs; revision cleanup releases asset references through a delayed garbage-collection policy.
- **Security controls:** Workspace authorization on every revision, patch schema/size limits, actor audit, CSRF/idempotency enforcement, and safe diff rendering.
- **Observability requirements:** Save latency/error/conflict, unsaved duration, recovery success, revision growth, compaction lag, stale-job rejection, and restore events.
- **Migration strategy:** Seed revision zero from canonical documents, enable conditional writes per cohort, reconcile shadow checksums, then reject blind writes.
- **Backward-compatibility strategy:** Legacy clients receive a compatibility ETag and a bounded grace window; server translates full updates into validated patches while emitting deprecation metrics.
- **Feature flags:** revision_writes, require_if_match, indexeddb_recovery, version_history, and legacy_blind_update_bridge.
- **Testing strategy:** Concurrent update integration tests on PostgreSQL, property-based patch replay, offline/reload/multi-tab E2E, restore authorization, compaction invariants, and stale export tests.
- **Acceptance criteria:** Lost-update tests are impossible by constraint, acknowledged edits recover after crash, conflicts are explicit, restore creates a new revision, and exports use requested revision.
- **Rollback strategy:** Stop requiring If-Match and read current canonical snapshot while retaining revision rows; never reverse by deleting history.
- **Dependencies on earlier sprints:** Sprints 4 and 5.
- **Risks:** Revision volume, difficult legacy diffs, IndexedDB browser variance, and confusing conflict UX.
- **Complexity:** Very high.
- **Priority:** P0 before paid beta.
- **Estimated implementation order:** Revision tables, conditional API, autosave client, local journal, history/restore, compaction, then legacy-write shutdown.
- **Deliverables:** Revision domain, migration, conditional API, recovery journal, history UI, compactor, and concurrency test suite.
- **Definition of Done:** All production writes create validated revisions, crash and concurrency drills pass, and no export/generation completion can clobber newer content.

### Sprint 7 — Workspaces, Membership, and RBAC

- **Business objective:** Make tenant ownership, collaboration, administration, and future team plans safe and explicit.
- **Why this sprint is necessary:** Per-user owner_id is insufficient for teams, finance review, scoped providers, shared assets, or defensible tenant isolation.
- **Current technical problems:** User resources reference owner_id directly, there is no workspace/membership/invitation domain, and admin privileges are coarse superuser booleans.
- **Evidence from the repository:** servers/fastapi/models/sql/user.py exposes is_superuser; servers/fastapi/models/sql/presentation.py, slide.py, image_asset.py, template.py, template_v2.py, async_task.py, chat_history_message.py, access_token.py, and webhook_subscription.py in that same directory use owner_id foreign keys; servers/fastapi/api/v1/admin/router.py is the sole backend admin area.
- **User-facing problems caused by the current design:** Users cannot invite collaborators, transfer ownership, separate personal/team work, or grant view-only/finance access.
- **Security implications:** Commercial launch requires server-side tenant isolation, least-privilege roles, invitation safety, scoped API credentials, and auditable privilege changes.
- **Scalability implications for approximately 10,000 users:** Workspace-indexed queries and authorization caching support 3,000 assumed workspaces across stateless instances without per-resource ad hoc filters.
- **Provider-agnostic implications:** Provider configuration and policy attach to workspace/plan, while service scopes remain provider-neutral.
- **Scope:** Workspace, membership, owner/admin/editor/viewer roles, finance-review permission, resource migration, invitations, audit events, service-account/API scopes, isolation tests, and team-plan hooks.
- **Explicit out-of-scope items:** Public sharing, real-time collaboration, subscriptions/credits implementation, and enterprise SSO.
- **Existing files to modify:** servers/fastapi/api/v1/auth/principal.py, context.py, and users.py; servers/fastapi/api/v1/security_dependencies.py; servers/fastapi/models/sql/* owner models; servers/fastapi/api/v1/admin/router.py; servers/nextjs/app/(presentation-generator)/services/api/dashboard.ts; servers/nextjs/components/Auth/AuthGate.tsx; servers/nextjs/app/(presentation-generator)/(dashboard)/Components/DashboardSidebar.tsx; and servers/nextjs/app/(presentation-generator)/(dashboard)/settings/UserAccountSettings.tsx.
- **Existing files to split:** Authentication identity from tenant authorization in servers/fastapi/api/v1/auth/context.py and servers/fastapi/api/v1/auth/principal.py; servers/fastapi/api/v1/admin/router.py into platform administration versus workspace administration.
- **Existing files to deprecate:** owner_id as the authorization source, global is_superuser checks outside platform-admin policy, and unscoped access tokens.
- **Existing files to delete:** No ownership columns in this sprint; they remain compatibility data until every row has workspace_id and the dual-check window passes.
- **New files to create:** modules/workspaces/domain/models.py, policies.py, application/invitations.py, api/router.py, persistence/models.py, modules/audit/domain/events.py, alembic workspace migration, features/workspaces/*, and tenant isolation tests.
- **Database models and migrations:** Add workspaces, memberships, invitations, service_accounts, api_credentials/scopes, audit_events, and workspace_id columns/indexes/constraints on owned resources.
- **API changes:** Workspace CRUD, membership/invitation lifecycle, role updates, current-workspace selection, scoped service credentials, and workspace-qualified resource routes or headers.
- **Frontend changes:** Workspace switcher, member/role settings, invitation accept/expiry UI, permission-aware controls, and clear personal-workspace migration.
- **Background-job changes:** Every job and outbox event carries workspace_id and actor_id; workers re-authorize resource/workspace binding rather than trusting payload claims.
- **Storage changes:** Asset keys and capabilities are workspace-scoped; cross-workspace copy creates a new authorized reference.
- **Security controls:** Policy-as-code, deny-by-default role matrix, non-enumerable invitations, hashed tokens, expiry/single use, step-up for owner/finance changes, and PostgreSQL isolation tests.
- **Observability requirements:** Workspace/role/actor IDs in redacted logs and audit events; denied-access, invitation abuse, privilege change, and cross-tenant probe alerts.
- **Migration strategy:** Create a personal workspace per existing user, backfill workspace_id in batches, dual-enforce owner and workspace consistency, then make workspace_id non-null.
- **Backward-compatibility strategy:** Existing sessions select the migrated personal workspace automatically; legacy owner endpoints map to it during a versioned grace period.
- **Feature flags:** workspaces, workspace_rbac_enforcement, invitations, service_accounts, and legacy_owner_bridge.
- **Testing strategy:** Role matrix unit tests, cross-tenant property/integration tests for every resource, invitation replay/expiry, concurrent owner transfer, API scope, and PostgreSQL row/query tests.
- **Acceptance criteria:** Every commercial resource has a non-null workspace owner, every endpoint uses centralized policy, and an automated matrix proves no cross-workspace access.
- **Rollback strategy:** Disable workspace UI and map sessions to personal workspaces while retaining dual owner checks; never remove workspace/audit data.
- **Dependencies on earlier sprints:** Sprints 1, 4, and 6.
- **Risks:** Missing an owner-filtered code path, accidental privilege escalation, invitation leakage, and slow backfills.
- **Complexity:** Very high.
- **Priority:** P0 before multi-user beta.
- **Estimated implementation order:** Policy model, tables, personal-workspace backfill, dual authorization, UI, invitations/service scopes, then owner-column contract migration.
- **Deliverables:** Workspace/RBAC domain, migration, centralized policies, member UI, invitations, scoped credentials, audit events, and exhaustive isolation suite.
- **Definition of Done:** All resource access is workspace-policy enforced, migrations reconcile every legacy owner, and red-team tenant-isolation tests pass.

### Sprint 8 — Durable Jobs and Transactional Outbox

- **Business objective:** Make expensive and asynchronous work durable, cancellable, idempotent, observable, and horizontally scalable.
- **Why this sprint is necessary:** AI generation, template import, images, exports, webhooks, and maintenance cannot rely on an HTTP process surviving.
- **Current technical problems:** AsyncTaskModel records status but lacks attempts, leases, heartbeats, cancellation, queue identity, and idempotency; FastAPI BackgroundTasks and process-local ConcurrentService execute durable business work.
- **Evidence from the repository:** servers/fastapi/models/sql/async_task.py, servers/fastapi/services/concurrent_service.py, servers/fastapi/api/v1/async_tasks/router.py, BackgroundTasks usage in servers/fastapi/api/v1/ppt/endpoints/presentation.py and template.py, servers/fastapi/services/webhook_service.py, and servers/fastapi/alembic/versions/a7d4c9e2f1b3_add_async_tasks.py plus b8e2f4a7c9d1_normalize_async_task_statuses.py show partial and duplicate task-state mechanisms.
- **User-facing problems caused by the current design:** Jobs disappear on restart, status can stall, retry may duplicate presentations or charges, and users cannot reliably cancel or understand partial failure.
- **Security implications:** Durable jobs need signed/validated payloads, least-authority workers, tenant checks, secret-free payloads, bounded retries, and queue-abuse limits.
- **Scalability implications for approximately 10,000 users:** Separate bounded queues and leases allow the assumed 60 AI, 100 image, and 24 export jobs without starving web requests.
- **Provider-agnostic implications:** Jobs name provider-neutral operation/capability and immutable configuration snapshot IDs; adapters execute later.
- **Scope:** Job/attempt model, status/progress/cancel, heartbeats, leases, retry policy, idempotency, transactional outbox/inbox, queue classes, dead letters, monitoring, Redis-backed broker, migration from BackgroundTasks, and duplicate-state removal.
- **Explicit out-of-scope items:** Provider routing internals, credit settlement rules, and autoscaling implementation.
- **Existing files to modify:** servers/fastapi/models/sql/async_task.py, servers/fastapi/api/v1/async_tasks/router.py, servers/fastapi/api/v1/ppt/endpoints/presentation.py, servers/fastapi/api/v1/ppt/endpoints/template.py, servers/fastapi/services/webhook_service.py, servers/fastapi/api/lifespan.py, servers/fastapi/pyproject.toml, Dockerfile, Dockerfile.dev, and docker-compose.yml.
- **Existing files to split:** Generation/template endpoint task functions in servers/fastapi/api/v1/ppt/endpoints/presentation.py and template.py into application commands and worker handlers; webhook delivery from servers/fastapi/services/webhook_service.py into dispatch records and delivery workers.
- **Existing files to deprecate:** servers/fastapi/services/concurrent_service.py, FastAPI BackgroundTasks for business operations, and legacy AsyncTaskModel.data in servers/fastapi/models/sql/async_task.py as an unversioned catch-all.
- **Existing files to delete:** servers/fastapi/services/concurrent_service.py only after no production import remains and restart/cancellation tests pass; duplicate legacy task-status helpers after data migration.
- **New files to create:** modules/jobs/domain/models.py, application/submit.py, persistence/models.py, outbox.py, api/router.py, workers/main.py, workers/registry.py, workers/queues.py, workers/handlers/*, modules/jobs/tests/*, and an Alembic jobs/outbox migration.
- **Database models and migrations:** Add jobs, job_attempts, outbox_messages, consumer_inbox, dead_letters, cancellation_requested_at, lease_owner/until, heartbeat, progress, idempotency_scope/key, payload/result schema versions, and indexes.
- **API changes:** POST job with idempotency key, GET/list status, cancel endpoint, resumable event stream with event IDs, and typed operation-specific submissions.
- **Frontend changes:** Unified job progress/cancel/retry UI, reconnect by last event ID, stable terminal states, and partial-result messaging.
- **Background-job changes:** All expensive work moves to durable workers with queue-specific concurrency, exponential bounded jitter, retry classifications, heartbeat, cancellation checkpoints, and dead-letter review.
- **Storage changes:** Large job inputs/results use object IDs; queue/database payloads contain bounded metadata only.
- **Security controls:** Workspace authorization, payload schema and size limits, operation admission controls from Phase 0, encrypted-secret references, no arbitrary callable names, and worker egress policies.
- **Observability requirements:** Queue depth/age, claim latency, run time, attempts, heartbeat age, cancellations, dead letters, idempotency dedupe, worker saturation, and trace propagation.
- **Migration strategy:** Submit legacy and durable jobs in shadow mode for fakes, move webhook/template work, then generation and exports; translate old task IDs while active.
- **Backward-compatibility strategy:** Existing task polling endpoints proxy to the new job model; legacy terminal rows remain readable through a compatibility serializer.
- **Feature flags:** durable_jobs_by_operation, durable_webhooks, durable_generation, durable_exports, and legacy_background_tasks.
- **Testing strategy:** Worker crash/restart, lease expiry/steal, idempotent replay, cancel race, retry classification, outbox atomicity, inbox dedupe, SSE reconnect, Redis outage, and PostgreSQL lock tests.
- **Acceptance criteria:** A killed API/worker cannot lose accepted work; duplicate submissions produce one side effect; cancellation and dead-letter behavior are deterministic; no expensive production route uses BackgroundTasks.
- **Rollback strategy:** Stop new durable submissions per operation and drain queues; retain compatibility polling and never discard accepted jobs/outbox rows.
- **Dependencies on earlier sprints:** Sprints 6 and 7; Phase 0 Redis-backed operation controls.
- **Risks:** Exactly-once misconceptions, lease clock skew, database contention, queue poisoning, and migration of in-flight tasks.
- **Complexity:** Very high.
- **Priority:** P0 before paid workload.
- **Estimated implementation order:** Schema/outbox, worker runtime, status API, webhook/template pilots, generation/images, export, then legacy runner removal.
- **Deliverables:** Durable job domain, outbox/inbox, workers, queue dashboards, compatibility API, migration tooling, and failure-injection suite.
- **Definition of Done:** Every accepted expensive operation survives process loss, has finite execution/retry, exposes correct progress/cancel state, and is traceable from request through durable result.

### Sprint 9 — Object Storage and Managed Asset Library

- **Business objective:** Give every upload, generated image, template asset, receipt, and export a secure durable identity independent of local disks.
- **Why this sprint is necessary:** Multiple API/worker instances cannot share raw filesystem paths, and commercial users need ownership, lifecycle, quota, and library behavior.
- **Current technical problems:** PresentationModel.file_paths, ImageAsset.path, temp services, app_data URLs, and export directories treat paths as durable identity.
- **Evidence from the repository:** servers/fastapi/models/sql/presentation.py, servers/fastapi/models/sql/image_asset.py, servers/fastapi/services/temp_file_service.py, servers/fastapi/utils/asset_directory_utils.py, servers/fastapi/utils/path_helpers.py, servers/fastapi/api/v1/ppt/endpoints/files.py, servers/fastapi/api/v1/ppt/endpoints/images.py, and servers/fastapi/services/export_task_service.py read/write local paths.
- **User-facing problems caused by the current design:** Assets may be unavailable on another instance, uploads cannot be reused safely, links expire unpredictably, and orphan files consume disk.
- **Security implications:** Direct object capabilities, malware state, MIME verification, tenant ownership, checksum dedupe, private receipts, and cleanup are centralized.
- **Scalability implications for approximately 10,000 users:** Direct multipart uploads remove API bandwidth/disk bottlenecks and support the assumed 50 MB/second ingress and year-one retention.
- **Provider-agnostic implications:** StorageProvider isolates S3-compatible, local-development, and future adapters; canonical documents store asset IDs only.
- **Scope:** Storage abstraction, local/S3 adapters, presigned upload/download, asset model, checksums, detected MIME, ownership, temporary/expiry state, orphan cleanup, quota hooks, local-path migration, thumbnail jobs, and asset library.
- **Explicit out-of-scope items:** Full billing enforcement and conversion-product UI.
- **Existing files to modify:** servers/fastapi/models/sql/image_asset.py, servers/fastapi/models/sql/presentation.py, servers/fastapi/api/v1/ppt/endpoints/files.py, servers/fastapi/api/v1/ppt/endpoints/images.py, servers/fastapi/services/temp_file_service.py, servers/fastapi/services/export_task_service.py, servers/fastapi/utils/asset_directory_utils.py, servers/nextjs/lib/readable-local-file.ts, servers/nextjs/app/api/upload-image/route.ts, and servers/nextjs/app/(presentation-generator)/upload/*.
- **Existing files to split:** servers/fastapi/services/temp_file_service.py into upload session, quarantine, and local adapter; servers/fastapi/api/v1/ppt/endpoints/files.py into upload orchestration versus document extraction submission.
- **Existing files to deprecate:** ImageAsset.path, PresentationModel.file_paths, public app_data paths, API-proxied large uploads, and permanent exports on instance disk.
- **Existing files to delete:** Orphaned local files only through a dry-run manifest, retention window, database-reference scan, and restoreable quarantine; no blanket directory deletion.
- **New files to create:** modules/assets/domain/models.py, application/uploads.py, application/lifecycle.py, providers/storage/base.py, local.py, s3.py, api/router.py, workers/thumbnails.py, features/assets/*, and object-storage integration tests.
- **Database models and migrations:** Add assets, object_versions, upload_sessions, asset_references, malware_scan status, checksum/size/MIME, workspace_id, storage_provider/key, retention state, and quota-accounting fields.
- **API changes:** Create/complete multipart upload, presigned scoped download, asset list/delete, reference/copy, and thumbnail endpoints; legacy upload returns both asset ID and temporary path during transition.
- **Frontend changes:** Managed asset picker, upload progress/retry, accessible metadata, replacement without broken references, and library filters.
- **Background-job changes:** Malware scan, metadata extraction, thumbnailing, migration, retention, and orphan collection use durable jobs with object-specific idempotency.
- **Storage changes:** S3-compatible private buckets, immutable keys, lifecycle classes, multipart abort cleanup, encryption, versioning policy, and local adapter for development.
- **Security controls:** Content-sniffing, extension/MIME policy, maximum size, quarantine-before-use, malware scanner interface, signed capabilities, SSRF-safe remote import, and tenant-reference checks.
- **Observability requirements:** Upload rate/latency/failure, bytes/storage by workspace, scan age/result, orphan candidates, lifecycle deletions, capability denial, and storage-provider health.
- **Migration strategy:** Inventory/checksum local files, create asset rows, upload/copy in batches, rewrite canonical references, verify checksums, then quarantine originals before deletion.
- **Backward-compatibility strategy:** Resolve legacy local references through a read-through migration adapter; return stable asset IDs to new clients.
- **Feature flags:** object_storage_writes, direct_uploads, asset_library, legacy_path_readthrough, and orphan_deletion.
- **Testing strategy:** Local and S3-contract tests, multipart interruption, MIME spoofing, cross-tenant capabilities, symlink/path traversal, malware fake, checksum mismatch, lifecycle, and legacy migration.
- **Acceptance criteria:** New production data never persists a raw path as identity; every object has ownership/checksum/state; private capabilities expire; migration reconciliation is zero-difference.
- **Rollback strategy:** Keep dual-written local originals during the rollback window and switch reads to the local adapter; suspend deletion jobs.
- **Dependencies on earlier sprints:** Sprints 4, 7, and 8.
- **Risks:** Broken references, unexpected egress cost, large backfill duration, scanner false results, and object-store regional availability.
- **Complexity:** Very high.
- **Priority:** P0 before horizontal scale.
- **Estimated implementation order:** Provider contract/models, upload sessions, quarantine/scanning, canonical references, asset library, migration, then lifecycle cleanup.
- **Deliverables:** StorageProvider, asset domain/API/UI, S3/local adapters, migration/reconciliation tool, scanner hook, thumbnail/cleanup workers, and runbook.
- **Definition of Done:** Production assets are private object records, direct upload and lifecycle tests pass, and legacy files are either reconciled or explicitly quarantined.

### Sprint 10 — Provider-Agnostic AI Platform

- **Business objective:** Route text, image, and search capabilities safely across replaceable providers based on availability, quality, plan, cost, and Syrian operating constraints.
- **Why this sprint is necessary:** Provider availability and commercial terms change; provider-specific environment/config branches cannot support reliable product policy.
- **Current technical problems:** Provider enums/config utilities and endpoint-specific implementations mix discovery, credentials, models, routing, and business decisions.
- **Evidence from the repository:** servers/fastapi/enums/llm_provider.py, image_provider.py, and web_search_provider.py; servers/fastapi/utils/llm_provider.py, llm_config.py, available_models.py, model_availability.py, and web_search.py; servers/fastapi/services/image_generation_service.py; servers/fastapi/api/v1/ppt/endpoints/openai.py, anthropic.py, google.py, and ollama.py; and servers/nextjs/utils/providerConstants.ts plus providerUtils.ts expose provider-shaped configuration.
- **User-facing problems caused by the current design:** Users see inconsistent setup/errors, jobs fail rather than route by policy, and regional availability or plan restrictions cannot be explained uniformly.
- **Security implications:** Workspace secrets need envelope encryption and redaction; custom endpoints require allowlists/SSRF policy; provider outages need circuit breakers and emergency shutdown.
- **Scalability implications for approximately 10,000 users:** Central admission, per-provider pools, circuit state, quotas, and health prevent one provider outage or slow SDK from exhausting workers.
- **Provider-agnostic implications:** This sprint establishes TextAIProvider, ImageAIProvider, and SearchProvider registries, normalized requests/results, capability discovery, and immutable routing decisions.
- **Scope:** Interfaces, registry, capabilities, health, encrypted config, workspace/plan policy, routing/fallback, timeout budgets, bounded retries, circuit breakers, metering/cost hooks, endpoint validation, secret rotation, emergency switches, and Syria-aware configuration.
- **Explicit out-of-scope items:** Selecting or claiming an official Syrian provider, billing ledger settlement, payment providers, and UI form redesign.
- **Existing files to modify:** servers/fastapi/utils/llm_provider.py, llm_config.py, available_models.py, and web_search.py; servers/fastapi/services/image_generation_service.py and provider_settings.py; servers/fastapi/models/sql/provider_settings.py; servers/nextjs/app/(presentation-generator)/(dashboard)/settings/TextProvider.tsx, ImageProvider.tsx, and WebSearchProvider.tsx; servers/nextjs/utils/providerConstants.ts and storeHelpers.ts.
- **Existing files to split:** servers/fastapi/services/image_generation_service.py into domain orchestration and adapters; servers/fastapi/utils/web_search.py into interface/adapters; servers/fastapi/utils/available_models.py into registry capability and health queries.
- **Existing files to deprecate:** Global ProviderSettings singleton, provider-specific public configuration routes, environment branches inside business services, and plaintext provider secrets in JSON.
- **Existing files to delete:** Old provider switches only after every supported adapter passes contract tests and migration; never delete config before encrypted import verification.
- **New files to create:** modules/providers/domain/contracts.py, capabilities.py, routing.py, application/configuration.py, security/secrets.py, adapters/text/*, adapters/image/*, adapters/search/*, api/router.py, features/providers/*, and provider contract/failure tests.
- **Database models and migrations:** Add provider_accounts, encrypted_provider_secrets, provider_capabilities, provider_health, routing_policies, immutable provider_snapshots, and workspace/plan restrictions; migrate singleton config to an admin/system workspace only when intended.
- **API changes:** Provider-neutral capability/status/config APIs, validated connection test jobs, policy simulation, secret rotate/delete, and normalized error codes.
- **Frontend changes:** Capability-based configuration, region/plan availability messaging, masked secrets, health/fallback status, and no provider-specific form unless loaded as adapter metadata.
- **Background-job changes:** Each job resolves policy once, records snapshot and chosen adapter, enforces timeout/retry/circuit, emits normalized usage, and never includes decrypted secrets.
- **Storage changes:** Provider artifacts flow through Asset/StorageProvider; secret material never enters object storage.
- **Security controls:** Envelope encryption with external master key, secret access audit, SSRF allowlists, TLS validation, response-size limits, log redaction, least-privilege SDK credentials, and disable switches.
- **Observability requirements:** Success/latency/error/circuit/timeout by capability/provider/model/region, normalized token/image/search usage, estimated/actual cost, and fallback reason without prompts.
- **Migration strategy:** Wrap current providers as adapters, compare normalized behavior under fakes, import config encrypted, enable policy routing per workspace, then remove switches.
- **Backward-compatibility strategy:** Map legacy config keys and provider names to registry IDs; preserve behavior with explicit pinned policy until users/admin migrate.
- **Feature flags:** provider_registry, encrypted_provider_config, policy_routing, provider_fallback, and legacy_provider_switches.
- **Testing strategy:** Adapter contract suite using fake servers, timeout/retry/circuit tests, secret encryption/rotation/redaction, custom-endpoint SSRF, capability policy, fallback determinism, and regional availability fixtures.
- **Acceptance criteria:** Business services depend only on interfaces; all supported adapters pass one contract; secrets are encrypted; a provider outage is bounded and observable; no provider is hardcoded for Syria.
- **Rollback strategy:** Pin workspaces to the compatibility adapter/policy while keeping encrypted config and recorded snapshots.
- **Dependencies on earlier sprints:** Sprints 7, 8, and 9; Phase 0 outbound-request layer.
- **Risks:** Provider semantic mismatch, unsafe fallback changing quality/cost, secret migration errors, and incomplete regional/legal information.
- **Complexity:** Very high.
- **Priority:** P0 for commercial reliability.
- **Estimated implementation order:** Contracts/normalized errors, secret store, current adapters, capabilities/health, routing/circuit, UI migration, then legacy removal.
- **Deliverables:** Provider contracts/registry, encrypted configuration, adapter suite, routing engine, health/cost hooks, admin controls, and regional policy documentation.
- **Definition of Done:** Supported provider changes require only an adapter/config entry, routing is deterministic and audited, secrets never appear plaintext outside a bounded decrypt operation, and outage tests pass.

### Sprint 11 — Structured Generation Form and Constraint Pipeline

- **Business objective:** Turn generation into a predictable, editable, validated product workflow whose explicit user settings are honored.
- **Why this sprint is necessary:** Commercial quality requires more than a free-text prompt and scattered request flags; users must see and control the generation contract.
- **Current technical problems:** Request fields, upload form state, outline state, prompt text, and generated structures are distributed, while a large endpoint orchestrates precedence and post-processing.
- **Evidence from the repository:** servers/fastapi/models/generate_presentation_request.py, presentation_structure_model.py, and presentation_outline_model.py; servers/nextjs/app/(presentation-generator)/upload/components/UploadPage.tsx, AdvanceSettings.tsx, ConfigurationSelects.tsx, NumberOfSlide.tsx, and LanguageSelector.tsx; servers/nextjs/app/(presentation-generator)/outline/*; servers/fastapi/utils/llm_calls/generate_presentation_structure.py; and servers/fastapi/api/v1/ppt/endpoints/presentation.py contain the pipeline.
- **User-facing problems caused by the current design:** Slide count, tone, detail, images, notes, and per-slide instructions may be unclear or inconsistently applied; partial failure is difficult to repair.
- **Security implications:** Structured schemas and limits reduce prompt injection impact, oversized generations, hidden instructions, and unsafe provider output.
- **Scalability implications for approximately 10,000 users:** Early validation and deterministic planning prevent wasted provider jobs and allow admission/cost estimates before execution.
- **Provider-agnostic implications:** Providers receive a normalized generation specification and must return schema-valid plans; no provider-specific prompt format is exposed to users.
- **Scope:** Audience, presentation type, tone, detail, slide count, aspect ratio, notes, image policy, precedence rules, editable outline, per-slide type/instructions, validation, structured output, constraint engine, post-generation verification, and partial-failure repair.
- **Explicit out-of-scope items:** Exact image execution, credit settlement, and final export compatibility.
- **Existing files to modify:** servers/fastapi/models/generate_presentation_request.py, presentation_structure_model.py, and presentation_outline_model.py; servers/fastapi/utils/llm_calls/generate_presentation_structure.py; servers/fastapi/api/v1/ppt/endpoints/presentation.py; servers/nextjs/app/(presentation-generator)/upload/components/*; servers/nextjs/app/(presentation-generator)/outline/*; and servers/nextjs/app/(presentation-generator)/services/api/presentation-generation.ts.
- **Existing files to split:** servers/nextjs/app/(presentation-generator)/upload/components/UploadPage.tsx into schema-driven form sections; servers/fastapi/api/v1/ppt/endpoints/presentation.py generation pipeline into validate, plan, generate, verify, and assemble application services.
- **Existing files to deprecate:** Implicit setting precedence, unvalidated provider JSON parsing, and free-form request fields that duplicate the structured specification.
- **Existing files to delete:** Duplicate form types/constants only after generated schema bindings replace them; no user request data deletion.
- **New files to create:** modules/generation/domain/specification.py, constraints.py, plan.py, application/plan_generation.py, verify_generation.py, schemas/generation-spec/v1.schema.json, generated/generation-spec.ts, features/generation-form/*, and fixtures/constraint-cases.
- **Database models and migrations:** Add generation_requests with immutable specification JSON/version, generation_plans, per-slide plan rows or bounded JSON, verification result, and source revision/workspace/job IDs.
- **API changes:** Validate/estimate, create plan, edit/approve outline, submit generation, retry failed slide, and retrieve verification report; all mutating calls are idempotent.
- **Frontend changes:** Accessible schema-driven form, explicit precedence summary, inline validation, editable outline cards, per-slide instructions/type, cost/quota estimate, and recoverable partial results.
- **Background-job changes:** Separate planning and slide-generation jobs, finite fan-out, dependency graph, partial terminal state, and targeted retry.
- **Storage changes:** Supporting documents and planned assets are asset IDs; immutable request/plan snapshots are database records.
- **Security controls:** Input and output schemas, prompt/data boundaries, maximum slides/text/files, provider output repair limit, policy-filtered URLs/assets, and content redaction.
- **Observability requirements:** Validation failures, plan/generation latency, constraint violations, repair attempts, partial failures, user edits to plan, and provider-normalized quality signals.
- **Migration strategy:** Build specification from current fields, show equivalence in shadow mode, then make new form default while translating old API requests.
- **Backward-compatibility strategy:** Maintain a versioned mapper from legacy GeneratePresentationRequest and old saved drafts to specification v1.
- **Feature flags:** structured_generation_form, generation_planning, constraint_verification, and legacy_generation_form.
- **Testing strategy:** Precedence tables, schema property tests, malicious prompt/provider fixtures, slide-count invariants, partial failure/retry, Arabic/English specifications, accessibility, and E2E with fake providers.
- **Acceptance criteria:** Explicit settings deterministically override inferred values; output has requested slide count or a clear partial state; invalid provider data never reaches the canonical document.
- **Rollback strategy:** Translate specification back to the legacy request path for supported fields while preserving the immutable request record.
- **Dependencies on earlier sprints:** Sprints 4, 8, and 10.
- **Risks:** Over-constraining creativity, provider schema differences, confusing precedence, and long planning latency.
- **Complexity:** High.
- **Priority:** P1.
- **Estimated implementation order:** Schema/precedence, validator/estimator, planner, outline editor, generation DAG, verifier, then legacy-form retirement.
- **Deliverables:** Generation specification/schema, form, plan API/UI, constraint engine, verifier, partial retry workflow, and compatibility mapper.
- **Definition of Done:** Fake-provider E2E proves all explicit constraints, Arabic and English flows, exact slide behavior, deterministic partial failure, and safe structured-output handling.

### Sprint 12 — Image Planning and Exact-Count Jobs

- **Business objective:** Deliver exactly the user-requested image work with visible per-image progress, targeted retries, stable bindings, and correct settlement.
- **Why this sprint is necessary:** Images have different provider costs/failures from slide text and must not be hidden inside broad generation fan-out.
- **Current technical problems:** ImageGenerationService couples provider choice, generation, placeholder fallback, and local paths; slide asset fetching is orchestrated inside presentation generation.
- **Evidence from the repository:** servers/fastapi/services/image_generation_service.py, servers/fastapi/api/v1/ppt/endpoints/images.py, servers/fastapi/utils/image_provider.py, servers/fastapi/utils/process_slides.py, servers/fastapi/models/sql/image_asset.py, servers/nextjs/components/ImageSelectionConfig.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/ImageProvider.tsx, servers/nextjs/components/slide-editor/images/ImagePickerModal.tsx, ImageToolbar.tsx in that same directory, and servers/nextjs/app/(presentation-generator)/presentation/utils/streamAssetMerge.ts show the current flow.
- **User-facing problems caused by the current design:** Users cannot see 4/5 completion clearly, retry only the failed image, lock manual choices, or guarantee an exact image count.
- **Security implications:** Remote image import must use SSRF controls; generated/uploaded objects require MIME checks, ownership, scanning, and safe metadata.
- **Scalability implications for approximately 10,000 users:** One finite job per image with queue fairness supports the assumed 100 concurrent image jobs and prevents a large deck monopolizing workers.
- **Provider-agnostic implications:** ImageAIProvider and stock/search capabilities return normalized candidates/assets; image roles and crop intent remain canonical.
- **Scope:** Exact count plan, per-image jobs, 4/5 states, retry, manual bindings, roles, crop/focal point, manual locks, stock/provider policy, validation, success-time settlement hooks, and orphan cleanup.
- **Explicit out-of-scope items:** Ledger implementation is Sprint 14; only settlement events/hooks are emitted here.
- **Existing files to modify:** servers/fastapi/services/image_generation_service.py, servers/fastapi/api/v1/ppt/endpoints/images.py, servers/fastapi/utils/process_slides.py, servers/fastapi/models/sql/image_asset.py, servers/nextjs/components/ImageSelectionConfig.tsx, servers/nextjs/components/slide-editor/images/ImagePickerModal.tsx, servers/nextjs/components/slide-editor/images/ImageToolbar.tsx, and the Sprint 4 canonical image elements plus Sprint 11 verifier.
- **Existing files to split:** servers/fastapi/services/image_generation_service.py into planning, provider execution, validation, and asset persistence; servers/fastapi/api/v1/ppt/endpoints/images.py into asset upload/query versus generation commands.
- **Existing files to deprecate:** Silent placeholder-as-success behavior, mutable local image path bindings, and presentation-level all-or-nothing image retries.
- **Existing files to delete:** Provider-specific image branches after Sprint 10 adapter parity; orphan files only through Sprint 9 lifecycle proof.
- **New files to create:** modules/images/domain/plan.py, bindings.py, application/create_plan.py, settle_result.py, workers/generate_image.py, features/images/ImageJobGrid.tsx, ImageBindingEditor.tsx, and exact-count tests.
- **Database models and migrations:** Add image_plans, image_requests, image_bindings, role/crop/focal/lock fields, expected_count, terminal outcome, provider snapshot, asset ID, reservation reference, and uniqueness/idempotency constraints.
- **API changes:** Create/inspect plan, list per-image status, retry one/all failed items, bind/unbind/lock asset, update crop/focal point, and explicitly accept partial completion.
- **Frontend changes:** Exact-count selector, per-item progress and errors, retry controls, manual/stock/generated choice, lock badges, crop/focal editor, and accessible partial-state summary.
- **Background-job changes:** One child job per requested image, bounded plan fan-out, provider concurrency groups, cancel propagation, result validation, settlement event, and cleanup compensation.
- **Storage changes:** Successful results are immutable Asset records; rejected/abandoned objects receive short retention and reference-aware cleanup.
- **Security controls:** Prompt and metadata size limits, SSRF-safe fetch, MIME/dimension/decompression-bomb checks, malware hook, workspace asset authorization, and no public provider URLs as permanent identity.
- **Observability requirements:** Planned/completed/failed counts, per-provider latency/cost, retry and fallback, validation rejection, orphan age, and settlement mismatch.
- **Migration strategy:** Derive image plans for new canonical generations first; preserve existing image assets as manually locked bindings when legacy decks migrate.
- **Backward-compatibility strategy:** Legacy clients receive aggregate progress synthesized from child jobs; old placeholder assets remain distinguishable and are not charged.
- **Feature flags:** exact_image_jobs, image_binding_editor, stock_fallback_policy, and legacy_inline_images.
- **Testing strategy:** Exact count with partial failures, targeted retry/idempotency, concurrent lock/edit, provider outage/fallback, crop serialization, unsafe remote URLs, malicious files, orphan cleanup, and fake settlement.
- **Acceptance criteria:** A request for five creates exactly five logical slots; 4/5 is stable and recoverable; retries never duplicate settlement; manual locks survive regeneration.
- **Rollback strategy:** Disable new planning while allowing accepted child jobs to drain; keep generated assets and translate completed bindings to legacy image fields.
- **Dependencies on earlier sprints:** Sprints 4, 8, 9, 10, and 11.
- **Risks:** Duplicate charges, provider moderation differences, partial-result UX, storage leaks, and crop parity across renderers/export.
- **Complexity:** High.
- **Priority:** P1.
- **Estimated implementation order:** Plan/binding schema, child handler, progress API/UI, validation/storage, retry/locks, settlement hooks, then legacy inline removal.
- **Deliverables:** Image plan domain, per-image workers/API/UI, binding/crop tools, validation pipeline, cleanup policy, and exact-count regression suite.
- **Definition of Done:** Exact-count and partial-retry scenarios pass under failures and concurrency, every successful image is a validated asset, and settlement events match durable successes only.

### Sprint 13 — Plans, Entitlements, and Subscriptions

- **Business objective:** Offer Free, Basic, and Pro plans through stable entitlements rather than scattered UI or provider checks.
- **Why this sprint is necessary:** Commercial permissions, limits, upgrades, renewals, and team features need one authoritative, provider-neutral policy.
- **Current technical problems:** The inspected SQL models and API modules contain no plan catalog, entitlement, subscription, or period model; operation limits are configuration controls, not commercial policy.
- **Evidence from the repository:** servers/fastapi/models/sql contains User, PresentationModel, AsyncTaskModel, ImageAsset, ProviderSettings, template, and webhook records but no billing domain; servers/nextjs/utils/presentationLimits.ts and servers/fastapi/api/operation_security.py impose technical limits without subscription state.
- **User-facing problems caused by the current design:** Users cannot understand plan benefits, renewal state, watermarks, storage/export access, or why a capability is unavailable.
- **Security implications:** Entitlements must be enforced server-side from trusted catalog/version data; admin changes and subscription transitions require audit and idempotency.
- **Scalability implications for approximately 10,000 users:** Cached compiled entitlements reduce repeated joins while PostgreSQL remains authoritative; invalidation is event-driven and workspace-scoped.
- **Provider-agnostic implications:** Plans grant capabilities and ceilings, never vendor model names; provider routing independently maps capabilities to available adapters.
- **Scope:** Free/Basic/Pro catalog, entitlement keys, subscription states/periods, renewal, upgrade/downgrade, trials, watermarks, export/storage/concurrent-job/theme access, and admin catalog management.
- **Explicit out-of-scope items:** Payment collection, immutable credit ledger, tax, coupons, and provider cost accounting.
- **Existing files to modify:** servers/fastapi/models/sql/user.py, Sprint 7 workspace modules, servers/fastapi/api/v1/security_dependencies.py, servers/fastapi/api/operation_security.py, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/SettingSideBar.tsx, servers/nextjs/app/(presentation-generator)/presentation/components/PresentationActions.tsx, servers/nextjs/app/(presentation-generator)/outline/components/TemplateSelection.tsx, servers/nextjs/app/(presentation-generator)/presentation/components/ThemeSelector.tsx, and servers/nextjs/lib/presentation-export-policy.ts.
- **Existing files to split:** Technical runtime limits from commercial entitlement evaluation; admin UI into plan catalog, subscription, and platform operations features.
- **Existing files to deprecate:** Client-only capability hiding, environment-only commercial limits, and direct plan-name conditionals.
- **Existing files to delete:** None until all capability checks use entitlement keys and old hardcoded conditions are proven unreachable.
- **New files to create:** modules/entitlements/domain/catalog.py, evaluator.py, subscriptions.py, application/change_plan.py, persistence/models.py, api/router.py, features/billing/PlansPage.tsx, SubscriptionStatus.tsx, admin/PlanCatalog.tsx, and entitlement matrix tests.
- **Database models and migrations:** Add plans, plan_versions, entitlement_definitions, plan_entitlements, subscriptions, subscription_periods, trials, scheduled_changes, and workspace subscription relation with constraints.
- **API changes:** Public active catalog, current entitlements/subscription, preview change, schedule/cancel downgrade, admin versioned catalog management, and internal entitlement decision endpoint/library.
- **Frontend changes:** Bilingual pricing/plan comparison, current status/renewal/trial messaging, upgrade/downgrade preview, watermark/export/theme affordances, and accessible denial explanations.
- **Background-job changes:** Period transition and grant events run idempotently; no payment activation occurs until Sprint 15.
- **Storage changes:** Storage quotas are entitlement values consumed by Sprint 9; no object deletion is triggered immediately on downgrade.
- **Security controls:** Server-side deny by default, immutable catalog versions for active periods, admin RBAC/audit, transition idempotency, and no trust in client plan claims.
- **Observability requirements:** Entitlement allow/deny by key/plan, subscription transition failures, cache age/invalidation, trial conversion, and over-limit states.
- **Migration strategy:** Assign existing workspaces a grandfathered Free plan version with current safe capabilities; shadow-evaluate before enforcing.
- **Backward-compatibility strategy:** Existing features stay available within the grandfathered catalog during beta; changes are explicit catalog versions, not silent flag reuse.
- **Feature flags:** entitlements_shadow, entitlements_enforce, subscriptions_ui, watermarks, and plan_admin.
- **Testing strategy:** Entitlement matrix, period boundaries/time zones, upgrade/downgrade scheduling, concurrent transitions, cache invalidation, RBAC, watermark/export behavior, and Arabic/English UI.
- **Acceptance criteria:** Every monetizable capability maps to a documented entitlement; server and UI decisions agree; plan changes are versioned, audited, idempotent, and reversible.
- **Rollback strategy:** Revert enforcement to shadow mode and restore the previous catalog version; retain subscription history and scheduled actions.
- **Dependencies on earlier sprints:** Sprints 7, 8, 9, and 10.
- **Risks:** Entitlement explosion, accidental feature removal on downgrade, timezone errors, and coupling plans to vendors.
- **Complexity:** High.
- **Priority:** P0 before commercial beta.
- **Estimated implementation order:** Entitlement vocabulary, catalog/version tables, evaluator/shadow mode, subscription state machine, UI/admin, then enforcement.
- **Deliverables:** Versioned catalog, entitlement evaluator, subscription domain/API/UI, plan administration, migration, and policy matrix.
- **Definition of Done:** All commercial gates use centralized server-side entitlements, existing workspaces are safely mapped, and transition/concurrency tests pass.

### Sprint 14 — Credits, Quotas, Usage, and Cost Accounting

- **Business objective:** Control spend and give users understandable presentation/image/conversion/storage allowances backed by an auditable immutable ledger.
- **Why this sprint is necessary:** Provider work has variable cost and failure; charging directly from tokens or mutable counters would be unfair and race-prone.
- **Current technical problems:** There is no wallet, reservation, ledger, normalized usage, provider-cost, or budget model; Phase 0 rate/concurrency controls are protective but not accounting.
- **Evidence from the repository:** servers/fastapi/models/sql has no credit/usage tables; servers/fastapi/utils/llm_calls/* and servers/fastapi/services/image_generation_service.py invoke providers, while servers/fastapi/models/sql/async_task.py has generic data but no accounting identity; servers/nextjs/utils/presentationLimits.ts is client-side guidance.
- **User-facing problems caused by the current design:** Users cannot see balances, reservations, refunds, quota periods, storage usage, or why costly work is blocked.
- **Security implications:** Mutable balances invite fraud and races; immutable double-entry-style events, idempotency, authorization, and admin separation are required.
- **Scalability implications for approximately 10,000 users:** Atomic PostgreSQL reservations and partitionable usage events support concurrent jobs; budget/admission checks occur before provider queues.
- **Provider-agnostic implications:** User credits are product units; normalized provider tokens/units and actual currency cost remain separate internal records.
- **Scope:** Presentation/image credits, conversion/storage quota, wallets, immutable ledger, reservation/settlement/release/refund/expiry/monthly grants, normalized provider usage/cost, attribution, dashboards, workspace/user/global budgets, concurrency, emergency cost controls, race tests.
- **Explicit out-of-scope items:** Payment collection, tax/accounting general ledger, cryptocurrency, and dynamic price optimization.
- **Existing files to modify:** Sprint 8 job submission/completion modules, Sprint 10 provider adapters, Sprint 12 image settlement handlers, Sprint 13 entitlement evaluator, servers/fastapi/api/operation_security.py, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/SettingPage.tsx, and Sprint 9 asset usage aggregation.
- **Existing files to split:** Provider SDK usage parsing from business credit pricing; technical concurrency limits from quota/budget admission.
- **Existing files to deprecate:** Any future mutable balance field, provider-token-as-credit UI, and settlement based on non-durable callbacks.
- **Existing files to delete:** None initially; any temporary beta counter is removed only after ledger reconciliation proves equal.
- **New files to create:** modules/usage/domain/units.py, events.py, cost.py, modules/credits/domain/ledger.py, reservation.py, application/settle.py, persistence/models.py, api/router.py, features/billing/UsageDashboard.tsx, admin/CostDashboard.tsx, and race/reconciliation tests.
- **Database models and migrations:** Add wallets, ledger_accounts, ledger_entries, reservations, grants, quota_periods, usage_events, provider_cost_events, budgets, and unique operation/idempotency constraints; use integer minor units/decimals, never float.
- **API changes:** Balance/usage history, cost estimate, reserve-aware job submission, quota status, admin adjustments with reason/approval, budgets, and exportable reconciliation.
- **Frontend changes:** Product-unit balances, pending reservations, monthly reset/expiry, per-operation usage, overage explanations, and no raw token pricing claim.
- **Background-job changes:** Admission reserves; durable success settles actual product units; cancel/permanent failure releases; compensators repair unmatched reservations; provider usage events are immutable.
- **Storage changes:** Daily object-byte snapshots/events feed storage quota; grace and archive policy precede deletion.
- **Security controls:** Serializable/locked ledger transactions, append-only permissions, idempotency, signed admin reason, separation of duties, anomaly controls, and emergency global/workspace/provider budgets.
- **Observability requirements:** Reserved/settled/released/refunded totals, unmatched reservations, negative-balance prevention, provider cost variance, cost per successful operation, budget denials, and reconciliation drift.
- **Migration strategy:** Run shadow metering with zero-charge beta grants, reconcile provider invoices and job outcomes, then enforce limits for a closed cohort.
- **Backward-compatibility strategy:** Grandfather beta workspaces with grants; keep historical normalized usage even if product credit pricing changes by catalog version.
- **Feature flags:** usage_metering, credit_shadow_ledger, credit_enforcement, cost_budgets, and admin_adjustments.
- **Testing strategy:** High-concurrency reservation/settlement, duplicate webhook/job completion, cancellation/refund/expiry, period rollover, integer/decimal precision, isolation, reconciliation, and failure injection on PostgreSQL.
- **Acceptance criteria:** Ledger debits/credits balance, duplicate events have one effect, no race overspends configured budget, every provider cost maps to a job/workspace, and user units stay provider-neutral.
- **Rollback strategy:** Disable enforcement but continue shadow recording; release open reservations with an audited compensating batch, never mutate/delete entries.
- **Dependencies on earlier sprints:** Sprints 8, 10, 12, and 13.
- **Risks:** Incorrect unit pricing, provider invoice mismatch, ledger hot rows, abusive retries, and confusing balances.
- **Complexity:** Very high.
- **Priority:** P0 before charging.
- **Estimated implementation order:** Usage vocabulary/events, ledger schema, reservation transaction, worker settlement, budgets/reconciliation, dashboards, then enforcement.
- **Deliverables:** Immutable ledger, quota/budget engine, normalized usage/cost records, settlement handlers, dashboards, reconciliation tooling, and concurrency suite.
- **Definition of Done:** Financial invariants hold under concurrent/replayed failures, shadow reconciliation is approved, and enforcement can be enabled per workspace without provider coupling.

### Sprint 15 — Provider-Neutral Payments for Syria

- **Business objective:** Support lawful, auditable subscription purchase in Syria through manual Sham Cash and Syriatel Cash review now and replaceable official adapters later.
- **Why this sprint is necessary:** Commercial launch needs payment state, evidence, fraud controls, and reconciliation without inventing unavailable APIs or binding billing to one channel.
- **Current technical problems:** No payment intent, price snapshot, receipt, review, transaction, refund, reconciliation, or finance permission domain exists.
- **Evidence from the repository:** The inspected servers/fastapi/models/sql, servers/fastapi/api/v1 routers, servers/nextjs/app/(presentation-generator)/(dashboard), and servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx contain no payment implementation; ImageAsset.path in servers/fastapi/models/sql/image_asset.py and generic admin superuser in servers/fastapi/models/sql/user.py are unsuitable for private receipts and finance review.
- **User-facing problems caused by the current design:** Users cannot submit a payment reference/receipt, track review, activate a subscription safely, or resolve duplicate/rejected payments.
- **Security implications:** Receipts are sensitive private assets; reviewer access, immutable decisions, duplicate detection, anti-fraud checks, audit, CSRF/idempotency, and safe signed access are mandatory.
- **Scalability implications for approximately 10,000 users:** Payment review needs indexed queues, bounded evidence handling, deterministic state transitions, and reconciliation rather than manual database edits.
- **Provider-agnostic implications:** PaymentProvider defines create/cancel/refund/reconcile/capabilities; manual Sham Cash and manual Syriatel Cash are adapters, not special fields in subscription models.
- **Scope:** Provider interface, two manual adapters, future adapter seams, intents, immutable price snapshot, references, receipt assets, private access, finance-review permission, approve/reject/expire/refund, subscription activation, credit granting, audit, reconciliation, duplicate/fraud controls, crypto disabled.
- **Explicit out-of-scope items:** No claim of official Sham Cash/Syriatel API, no crypto payment, no automatic banking integration, no tax/legal conclusion, and no card provider unless separately reviewed.
- **Existing files to modify:** Sprint 7 workspace RBAC policies, Sprint 9 asset access, Sprint 13 entitlement subscription service, Sprint 14 credit grant service, servers/nextjs/app/(presentation-generator)/(dashboard)/Components/DashboardSidebar.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, servers/nextjs/lib/security-headers.mjs, and Sprint 7 audit events.
- **Existing files to split:** Platform admin from finance-review workflows; generic asset previews from hardened receipt viewer.
- **Existing files to deprecate:** Any operational process that activates subscriptions or grants credits through direct database edits.
- **Existing files to delete:** None until a documented legacy/manual record import is reconciled; crypto UI/config remains absent or explicitly disabled.
- **New files to create:** modules/payments/domain/provider.py, intents.py, decisions.py, adapters/manual_sham_cash.py, manual_syriatel_cash.py, application/review.py, reconcile.py, persistence/models.py, api/router.py, features/payments/*, features/admin/payments/*, and payment security/state-machine tests.
- **Database models and migrations:** Add payment_providers, payment_intents, immutable price_snapshots, payment_attempts, transaction_references with uniqueness scopes, receipt_asset links, review_decisions, refunds, reconciliation_batches/items, fraud_flags, and outbox events.
- **API changes:** Create/cancel/inspect intent, submit reference/receipt, status history, finance queue/detail, approve/reject, expire, refund request/decision, and reconciliation import/resolve.
- **Frontend changes:** Arabic/English payment instructions controlled by reviewed configuration, intent expiry, private receipt upload, status timeline, duplicate guidance, and finance reviewer queue with least data.
- **Background-job changes:** Expiry, scan receipt, notify, activate subscription/grant credits through idempotent outbox consumers, and reconciliation jobs; approval HTTP requests do not perform remote side effects inline.
- **Storage changes:** Receipts use private encrypted Asset records, malware scanning, short-lived reviewer capabilities, no public URLs, retention/legal-hold policy, and access audit.
- **Security controls:** Finance-review RBAC and step-up, four-eyes threshold where configured, immutable price/currency, reference normalization/uniqueness, receipt validation, rate limits, CSRF/idempotency, audit, fraud velocity rules, and crypto kill switch default off.
- **Observability requirements:** Intent conversion/expiry, review age, duplicate/fraud flags, activation lag, reconciliation mismatch, refund status, receipt access, and reviewer actions.
- **Migration strategy:** Begin closed beta with staff-created catalog/prices and manual sandbox references; do not import unverified historic payments; enable one adapter/cohort at a time.
- **Backward-compatibility strategy:** Payment events call existing Sprint 13/14 commands; future official adapters implement the same interface and preserve intent/price/reference history.
- **Feature flags:** payments, manual_sham_cash, manual_syriatel_cash, payment_approval, refunds, and crypto_payments permanently false until a separately approved sprint.
- **Testing strategy:** State-machine/property tests, duplicate references, concurrent approvals, replayed activation, expired intent, receipt authorization/malware, reconciliation, refund compensation, RBAC, bidi copy, and fake adapters only.
- **Acceptance criteria:** No official API is invented; duplicate/replayed approval cannot double grant; receipts are private; every decision and activation is auditable/reconcilable; crypto is off.
- **Rollback strategy:** Stop new intents per adapter, allow existing intents to expire/review, disable activation consumer, and issue compensating ledger/subscription events rather than deleting records.
- **Dependencies on earlier sprints:** Sprints 7, 8, 9, 13, and 14 plus legal/operations approval.
- **Risks:** Fraud, ambiguous references, operational backlog, regional legal changes, receipt privacy, and manual reviewer error.
- **Complexity:** Very high.
- **Priority:** P0 for Syrian commercial launch, after legal readiness.
- **Estimated implementation order:** Legal/operational rules, provider/state model, private receipts, manual adapters, finance UI, activation/outbox, reconciliation/refund, then closed cohort.
- **Deliverables:** PaymentProvider, two manual adapters, intent/review/refund/reconciliation domains, private receipt flow, finance dashboard, runbook, and launch control checklist.
- **Definition of Done:** Approved end-to-end fake/manual scenarios reconcile exactly, security review passes, operations can process and reverse payments without database edits, and legal owners approve launch instructions.

### Sprint 16 — PPTX/PDF Export Compatibility Program

- **Business objective:** Produce reliable, editable, revision-correct PPTX and visually faithful PDF for Arabic and English decks.
- **Why this sprint is necessary:** Export is a core paid promise, while Phase 0 intentionally keeps unverified/high-risk runtime execution off unless explicitly trusted.
- **Current technical problems:** Export spans a downloaded presentation-export runtime, Node/Chromium/ImageMagick preparation, FastAPI subprocess orchestration, a Next route, local files, and Electron packaging; compatibility and licensing are not a unified product program.
- **Evidence from the repository:** scripts/sync-presentation-export.cjs, config/artifact-integrity.json, servers/fastapi/services/export_task_service.py, servers/fastapi/utils/export_utils.py, servers/fastapi/api/v1/ppt/endpoints/presentation.py, servers/nextjs/app/api/export-presentation/route.ts, servers/nextjs/app/(export)/pdf-maker, electron/scripts/sync-export-runtime.cjs, electron/scripts/prepare-export-chromium.cjs, electron/scripts/prepare-imagemagick.cjs, and electron/app/ipc/export_handlers.ts implement the chain.
- **User-facing problems caused by the current design:** Exports may be unavailable under safe defaults, stale relative to autosave, visually inconsistent, non-editable, slow, or unclear on failure.
- **Security implications:** Browser/subprocess execution, internal URLs/cookies, archive provenance, fonts, untrusted documents, and converter HTML that can retain external asset URLs demand isolated workers, deny-by-default browser egress, and one-time scoped capabilities.
- **Scalability implications for approximately 10,000 users:** The assumed 24 concurrent exports require queue isolation, resource quotas, cancellation, autoscaling from measured duration, and object results.
- **Provider-agnostic implications:** ExportProvider accepts canonical document/revision and normalized options; current runtime, a replacement, and PDF adapters remain interchangeable.
- **Scope:** Exporter audit/replacement decision, canonical export model/jobs, scoped capabilities, editable element matrix, OOXML validation, Arabic/RTL/fonts/charts/tables/SVG/groups/notes, PowerPoint/LibreOffice tests, visual regression, stale-save prevention, timeout/cancel, worker isolation.
- **Explicit out-of-scope items:** General office/PDF utilities in Sprint 17 and Kubernetes.
- **Existing files to modify:** servers/fastapi/services/export_task_service.py, servers/fastapi/utils/export_utils.py, servers/fastapi/api/v1/ppt/endpoints/presentation.py, servers/nextjs/lib/presentation-export-policy.ts, servers/nextjs/app/api/export-presentation/route.ts, servers/nextjs/app/(export)/pdf-maker/*, config/artifact-integrity.json, scripts/sync-presentation-export.cjs, electron/scripts/sync-export-runtime.cjs, electron/app/ipc/export_handlers.ts, and servers/nextjs/app/(presentation-generator)/presentation/components/PresentationActions.tsx.
- **Existing files to split:** servers/fastapi/services/export_task_service.py into provider adapter, capability issuer, subprocess sandbox, and result persistence; servers/nextjs/app/(presentation-generator)/presentation/components/PresentationActions.tsx export state into a feature module.
- **Existing files to deprecate:** Cookie-bearing export-from-URL, API-instance subprocess export, local output paths, unverified Chromium acquisition, and direct bundled-runtime business coupling.
- **Existing files to delete:** Legacy export-from-session URL path and old runtime layout only after canonical direct export meets parity and all supported desktop/server builds pass; unverified binaries remain absent.
- **New files to create:** modules/exports/domain/contracts.py, compatibility.py, application/request_export.py, capabilities.py, adapters/current_runtime.py, adapters/pdf.py, workers/export.py, features/exports/*, tests/export-fixtures/*, and docs/exports/compatibility-matrix.md.
- **Database models and migrations:** Add export_requests/results, source_revision/checksum, provider snapshot, format/options, capability nonce/hash/expiry/use count, status, error code, object asset ID, compatibility report, and idempotency key.
- **API changes:** Create/cancel/status/download export by immutable revision; capability exchange is internal and one-time; return compatibility warnings before submission.
- **Frontend changes:** Save/revision confirmation, format/options, compatibility warnings, progress/cancel/retry, expired download regeneration, and clear safe-disabled explanation.
- **Background-job changes:** Dedicated export queue/workers with per-format memory/CPU/time limits, cancellation checkpoints, sandboxed subprocess, result validation/upload, and finite retry.
- **Storage changes:** Inputs/results are private immutable objects with checksums, short-lived downloads, retention by plan, and no worker access beyond scoped keys.
- **Security controls:** Pinned/verifiable runtime, non-root sandbox, no arbitrary URL/cookie, egress deny by default, one-time capabilities, process/file limits, OOXML/PDF validation, font provenance, and redacted logs.
- **Observability requirements:** Queue age, duration/resource use by pages/elements/format, timeout/cancel/error, compatibility warnings, visual diff, validation failure, and download completion.
- **Migration strategy:** Build a golden canonical corpus, audit current runtime, run current/replacement candidates in shadow, choose by evidence/legal status, then enable per cohort/format.
- **Backward-compatibility strategy:** Preserve legacy export only for compatible migrated documents behind a monitored flag; output filenames and basic API responses remain stable.
- **Feature flags:** verified_exports, canonical_export_provider, export_format_pptx, export_format_pdf, legacy_export_adapter, and export_runtime_emergency_disable.
- **Testing strategy:** OOXML schema/open-repair, PDF parsing, PowerPoint and LibreOffice automation/manual matrix, Arabic/mixed RTL fonts, editable element assertions, visual regression, stale autosave, capability replay, timeout/cancel, malicious documents, and desktop packaging.
- **Acceptance criteria:** Every supported element has documented editable/fidelity status; exports use requested durable revision; no unverified runtime executes; reference corpus passes validation and approved visual thresholds.
- **Rollback strategy:** Disable affected provider/format, preserve queued job state and canonical inputs, and route eligible documents to the previous verified adapter.
- **Dependencies on earlier sprints:** Sprints 4, 6, 8, 9, and 10; legal/provenance review.
- **Risks:** Export runtime licensing, Office implementation differences, Arabic font substitution, huge deck resource use, and incomplete editability.
- **Complexity:** Very high.
- **Priority:** P0 for paid launch.
- **Estimated implementation order:** Corpus/matrix, provider contract, scoped worker, current-runtime audit, canonical mapping, compatibility hardening, desktop parity, then gated launch.
- **Deliverables:** ExportProvider, isolated worker, compatibility matrix/corpus, capability protocol, object result flow, validation/visual suite, and exporter decision record.
- **Definition of Done:** Approved PPTX/PDF fixtures are revision-correct, safe, downloadable, and compatible across documented applications; operational and legal launch gates pass.

### Sprint 17 — File Conversion and PDF Utilities

- **Business objective:** Add secure, quota-controlled document conversion and PDF tools as independently marketable workflows.
- **Why this sprint is necessary:** Existing document extraction and export utilities are presentation-oriented; public conversion needs isolation, malware handling, lifecycle, and a provider abstraction.
- **Current technical problems:** Office/document loaders and LiteParse run from the application environment, temporary files are local, and there is no conversion job/domain or anonymous abuse policy.
- **Evidence from the repository:** servers/fastapi/services/document_conversion_service.py, servers/fastapi/services/office_document_service.py, servers/fastapi/services/documents_loader.py, servers/fastapi/services/liteparse_service.py, electron/resources/document-extraction/liteparse_runner.mjs, servers/fastapi/api/v1/ppt/endpoints/files.py, servers/nextjs/app/(export)/pdf-maker, and servers/fastapi/services/temp_file_service.py contain conversion pieces but no complete product boundary.
- **User-facing problems caused by the current design:** Users cannot reliably convert Word/PowerPoint/Excel/images, merge/split/rotate/watermark/compress/reorder/delete pages, or retrieve results with stable progress.
- **Security implications:** Complex document parsers are high-risk; inputs need malware scanning, sandboxing, decompression/page limits, private objects, expiration, and anonymous rate controls.
- **Scalability implications for approximately 10,000 users:** Dedicated conversion queues and container limits stop CPU/memory-heavy files from affecting web/API/export, with finite anonymous capacity.
- **Provider-agnostic implications:** FileConversionProvider supports Gotenberg or an equivalent adapter without exposing vendor endpoints or payloads to business APIs.
- **Scope:** Provider abstraction; Word/PPT/Excel/images to PDF; merge, split, rotate, watermark, compression, reorder, delete pages, PDF-to-images; quota, anonymous limits, isolation, scanning, temp retention, and SEO product pages.
- **Explicit out-of-scope items:** OCR translation, document collaborative editing, and unsupported password circumvention.
- **Existing files to modify:** servers/fastapi/services/document_conversion_service.py, servers/fastapi/services/office_document_service.py, servers/fastapi/services/documents_loader.py, servers/fastapi/services/liteparse_service.py, servers/fastapi/api/v1/ppt/endpoints/files.py, servers/nextjs/app/(export)/pdf-maker/*, servers/fastapi/api/operation_security.py, docker-compose.yml, and nginx.conf.
- **Existing files to split:** Document extraction from conversion in servers/fastapi/services/documents_loader.py; presentation export PDF UI in servers/nextjs/app/(export)/pdf-maker from the new general PDF utility UI.
- **Existing files to deprecate:** In-process untrusted office conversion, raw temp paths in requests, unlimited anonymous conversion, and direct Gotenberg/vendor calls outside adapters.
- **Existing files to delete:** Insecure/in-process converters only after an isolated adapter passes the format corpus; temporary objects only through lifecycle jobs.
- **New files to create:** modules/conversion/domain/contracts.py, operations.py, adapters/gotenberg.py, adapters/local_safe.py, application/submit.py, workers/conversion.py, features/conversion/*, app/[locale]/tools/* SEO routes, tests/conversion-corpus, and docs/conversion/security.md.
- **Database models and migrations:** Add conversion_jobs, ordered input/output asset links, operation/version/options, provider snapshot, page/file metadata, anonymous privacy-preserving quota key, retention, and usage settlement reference.
- **API changes:** Multipart/direct upload session, validate/estimate, submit/cancel/status, private download, supported-capability query, and bounded anonymous endpoint with no account promotion bypass.
- **Frontend changes:** Bilingual task-specific pages, drag/reorder/page previews, validation/limits, progress/cancel, private result download, retention notice, and accessible SEO metadata.
- **Background-job changes:** Dedicated conversion worker and queues by resource class; scan-before-convert, timeout/cancel, page-level progress where possible, result validation, cleanup, and settlement.
- **Storage changes:** Quarantined input and expiring output assets in private buckets/prefixes; no local identity; lifecycle and legal hold are explicit.
- **Security controls:** MalwareScanner, sandbox/container user, network deny, CPU/memory/process/disk/time/page/decompression limits, MIME sniffing, password policy, signed object capabilities, Phase 0 SSRF/limits, and privacy-preserving anonymous keys.
- **Observability requirements:** Per-operation size/pages/duration/error/resource use, queue backlog, scanner lag, sandbox kills, anonymous denials, result size, cleanup age, and provider health.
- **Migration strategy:** Keep current presentation extraction unchanged behind its adapter; introduce new utility jobs with fake/safe corpora, then migrate compatible internal conversions.
- **Backward-compatibility strategy:** Existing presentation upload API maps its supported operations to the new job layer without exposing public converter internals.
- **Feature flags:** file_conversion, anonymous_conversion, conversion_operation_by_name, gotenberg_adapter, and conversion_emergency_disable.
- **Testing strategy:** Safe/malformed/malicious corpus, decompression bombs, high page counts, malware fake, sandbox limits, operation correctness/order, anonymous distributed limits, retention, provider outage, and SEO/accessibility.
- **Acceptance criteria:** Every advertised operation has golden outputs and enforced limits; untrusted parsers are isolated; inputs/results are private and expire; anonymous abuse cannot bypass shared controls.
- **Rollback strategy:** Disable individual operations/providers, drain or cancel accepted jobs, preserve inputs until communicated retention, and keep presentation extraction on the prior adapter.
- **Dependencies on earlier sprints:** Sprints 8, 9, 10, 13, 14, and 16.
- **Risks:** Parser vulnerabilities, malformed-file crashes, Gotenberg regional/operational fit, large resource cost, and fidelity expectations.
- **Complexity:** Very high.
- **Priority:** P1 after core presentation launch unless it is a launch requirement.
- **Estimated implementation order:** Threat model/corpus, provider contract, isolated worker, core conversions, PDF operations, quota/anonymous path, SEO pages, then internal migration.
- **Deliverables:** FileConversionProvider, isolated worker, conversion/PDF API and UI, security corpus, lifecycle/quotas, SEO pages, and operational runbook.
- **Definition of Done:** Advertised conversion flows pass correctness, isolation, abuse, privacy, retention, and failure tests without executing parsers in API instances.

### Sprint 18 — Administration and Operations Dashboard

- **Business objective:** Give authorized operations staff safe, audited tools to manage users, workspaces, plans, money, providers, jobs, storage, abuse, and emergency controls without database access.
- **Why this sprint is necessary:** Commercial operations cannot depend on a generic superuser screen or shell/database intervention.
- **Current technical problems:** The admin surface is narrow and centralized, while future domains need distinct permissions, safe actions, pagination, and audit context.
- **Evidence from the repository:** servers/fastapi/api/v1/admin/router.py and servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx are the current admin implementation; servers/fastapi/models/sql/user.py provides a global is_superuser boolean; provider settings and task APIs are separate.
- **User-facing problems caused by the current design:** Support cannot explain or repair job, subscription, credit, payment, export, or storage problems promptly and consistently.
- **Security implications:** Powerful actions require least privilege, step-up, reason codes, approval rules, immutable audit, redaction, pagination limits, and anti-enumeration.
- **Scalability implications for approximately 10,000 users:** Indexed search, server pagination, asynchronous bulk actions, and cached summaries avoid unbounded admin queries and API disruption.
- **Provider-agnostic implications:** Staff operate capability health/cost and provider registry entries through normalized controls, not SDK-specific secrets or payloads.
- **Scope:** Users, workspaces, plans, subscriptions, credits, payments/review, provider health/cost, jobs/failures, exports, storage, abuse flags, audit, security controls, feature flags, emergency switches, and support impersonation policy if approved.
- **Explicit out-of-scope items:** Unrestricted impersonation, raw secret viewing, arbitrary SQL, provider-specific debugging consoles, and analytics data warehouse.
- **Existing files to modify:** servers/fastapi/api/v1/admin/router.py, servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/layout.tsx, servers/nextjs/app/(presentation-generator)/(dashboard)/Components/DashboardSidebar.tsx, Sprint 7 RBAC/audit modules, Sprint 8–15 provider/job/asset/billing/payment APIs, and servers/nextjs/lib/security-headers.mjs.
- **Existing files to split:** servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx into domain pages; servers/fastapi/api/v1/admin/router.py into policy-protected domain query/command routers.
- **Existing files to deprecate:** Single is_superuser gate for all actions, inline bulk mutations, and operational database edits.
- **Existing files to delete:** Legacy monolithic admin sections only after routes and permission tests prove feature parity; no audit/financial records are deleted.
- **New files to create:** modules/admin/application/search.py, support_actions.py, api/router.py, modules/abuse/domain/flags.py, features/admin/layout.tsx, users/*, workspaces/*, billing/*, payments/*, providers/*, jobs/*, storage/*, security/*, and admin E2E/audit tests.
- **Database models and migrations:** Add operator_roles/permissions or reuse workspace/platform policy mapping, support_cases/actions, abuse_flags, feature_flag definitions/overrides, approval requests, and append-only admin audit metadata.
- **API changes:** Paginated/redacted search/detail, typed support commands, approval workflow, feature/emergency switch APIs, audit export, and job/reconciliation repair commands with idempotency.
- **Frontend changes:** Bilingual accessible domain pages, filters/cursors, status timelines, reason/confirmation dialogs, diff previews, approval inbox, and safe redacted copy.
- **Background-job changes:** Bulk, report, reconciliation, cleanup, and repair operations submit durable jobs; emergency pause can halt selected queues without data loss.
- **Storage changes:** Admin sees metadata and obtains one-time least-authority previews only when permitted; receipt/user asset access is separately audited.
- **Security controls:** Dedicated platform/finance/security/support roles, step-up authentication, short sessions, CSRF, field redaction, export watermark, approval thresholds, no secret reveal, and immutable action audit.
- **Observability requirements:** Admin command success/denial/latency, approval age, emergency-switch state, search cost, bulk job status, suspicious access, and receipt/asset views.
- **Migration strategy:** Build read-only views first, compare with direct operational reports, enable low-risk commands, then finance/security commands after role and audit review.
- **Backward-compatibility strategy:** Keep the legacy admin panel read-only during transition and deep-link to replacement pages; API commands remain versioned.
- **Feature flags:** admin_v2, admin_write_actions, support_actions, finance_review, and emergency_control_panel.
- **Testing strategy:** Permission matrix, redaction snapshots, step-up/session expiry, CSRF, approval races, cursor/pagination load, audit completeness, bulk idempotency, and Arabic/English accessibility.
- **Acceptance criteria:** Routine support/finance/provider/job/storage actions require no database access; every sensitive read/write is least-privilege and auditable.
- **Rollback strategy:** Switch all v2 actions to read-only, disable command routes, and retain audit/approval state; emergency controls remain available through a documented secure fallback.
- **Dependencies on earlier sprints:** Sprints 7–17 as their administrative capabilities become available.
- **Risks:** Privilege escalation, overly broad data exposure, dangerous bulk actions, slow cross-domain queries, and operator error.
- **Complexity:** High.
- **Priority:** P0 before commercial launch operations.
- **Estimated implementation order:** Role/action taxonomy, read-only shell, users/workspaces/jobs, providers/storage, billing/payments, security/flags, then audited write actions.
- **Deliverables:** Modular operations dashboard, admin APIs, support/approval workflows, abuse flags, emergency controls, audit coverage, and operator runbook.
- **Definition of Done:** Authorized staff complete rehearsed support/finance/incident scenarios without DB/secret access, while policy, audit, rollback, accessibility, and load tests pass.

### Sprint 19 — Observability, Privacy, and Auditability

- **Business objective:** Operate the platform against explicit SLOs while minimizing collected personal data and maintaining defensible audit evidence.
- **Why this sprint is necessary:** Ten-thousand-user reliability, provider cost control, incident response, and privacy cannot be retrofitted from ad hoc logs.
- **Current technical problems:** Phase 0 makes telemetry and Sentry safer by default, but identifiers, domain metrics, traces, retention, audit semantics, and SLOs are not yet end-to-end.
- **Evidence from the repository:** servers/nextjs/utils/mixpanel.ts, servers/nextjs/lib/telemetry-privacy.mjs, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/PrivacySettings.tsx, servers/fastapi/utils/sentry_config.py, electron/app/sentry/main.ts, electron/app/preloads/sentry.ts, servers/fastapi/api/middlewares.py, servers/fastapi/services/export_task_service.py, and servers/fastapi/api/operation_security.py are current control points.
- **User-facing problems caused by the current design:** Incidents and job failures are harder to explain, privacy choices may differ by surface, and support lacks consistent timelines.
- **Security implications:** Logs/traces can leak prompts, document text, secrets, receipts, provider payloads, or tokens; audit records must be tamper-evident and access controlled.
- **Scalability implications for approximately 10,000 users:** Metrics, sampling, cardinality budgets, and backlog/provider SLOs guide scaling without unbounded observability cost.
- **Provider-agnostic implications:** Normalized capability/operation dimensions permit provider comparison; telemetry backend is replaceable and provider payloads are excluded.
- **Scope:** Structured logs; request/job/workspace/presentation IDs; metrics/traces/error tracking; cost metrics; SLOs/alerts; redaction; retention; consent/session-recording policy; audit; security-event monitoring; privacy requests.
- **Explicit out-of-scope items:** Surveillance analytics, always-on session recording, logging prompts/documents by default, and a full BI warehouse.
- **Existing files to modify:** servers/fastapi/api/middlewares.py, servers/fastapi/api/main.py, servers/fastapi/utils/sentry_config.py, servers/nextjs/utils/mixpanel.ts, servers/nextjs/lib/telemetry-privacy.mjs, servers/nextjs/app/(presentation-generator)/(dashboard)/settings/PrivacySettings.tsx, electron/app/sentry/main.ts, electron/app/preloads/sentry.ts, electron/app/utils/safe-console.ts, Sprint 8 worker runtime, future domain event publishers, and Sprint 20 deployment config.
- **Existing files to split:** Product analytics from operational telemetry and immutable audit; shared correlation/redaction utilities from service-specific log calls.
- **Existing files to deprecate:** print calls, free-form payload logging, unbounded high-cardinality labels, global analytics without explicit consent, and sendDefaultPii behavior.
- **Existing files to delete:** Legacy logging/analytics initializers only after replacement coverage and privacy tests; audit records are never mutable/deleted outside approved retention/anonymization policy.
- **New files to create:** servers/fastapi/core/observability/logging.py, metrics.py, tracing.py, redaction.py, audit.py, servers/nextjs/lib/observability.ts, privacy/consent.ts, electron/app/observability/*, config/telemetry-schema.json, docs/operations/slos.md, alerts.md, and telemetry contract tests.
- **Database models and migrations:** Extend audit_events with category/action/subject/actor/workspace/request/job, redacted diff/hash, retention/legal hold; add consent records and privacy-request workflow where legally required.
- **API changes:** Privacy preference/consent history, audit list/export with RBAC, support diagnostic IDs, readiness dependency detail for internal use, and privacy request endpoints.
- **Frontend changes:** One cross-surface privacy center, consent before analytics, no recording default, diagnostic ID display, audit views for relevant workspace actions, and localized retention explanations.
- **Background-job changes:** Trace context propagates through outbox/jobs; workers emit finite lifecycle metrics; audit/telemetry export and retention are durable jobs.
- **Storage changes:** Observability storage is segregated with encryption, access control, region/retention policy, and no receipt/object body ingestion.
- **Security controls:** Schema allowlist and denylist redaction, secret/token/prompt filters, PII-off error tracking, consent enforcement, session recording opt-in and masking if ever enabled, audit integrity, and access monitoring.
- **Observability requirements:** This sprint defines RED/USE metrics, job/queue/provider/export/payment SLOs, burn-rate alerts, cost/cardinality budgets, on-call routing, and alert ownership.
- **Migration strategy:** Instrument golden request/job/payment flows, run dual logging without payload capture, validate redaction/cardinality, then retire free-form logs.
- **Backward-compatibility strategy:** Preserve existing privacy-disable environment settings as stronger overrides; map old consent into an explicit unknown/off state, never infer opt-in.
- **Feature flags:** structured_observability, distributed_tracing, product_analytics_consent, audit_ui, and session_recording fixed off until separate privacy approval.
- **Testing strategy:** Redaction corpus, canary-secret tests, trace propagation, metric cardinality, SLO alert simulation, consent across web/Electron, audit completeness/authorization, retention, and telemetry-backend outage.
- **Acceptance criteria:** Operators trace a request to jobs/provider/cost without content; test secrets never escape; consent defaults off; launch SLOs and alerts have owners and drills.
- **Rollback strategy:** Reduce sampling or disable external exporters while retaining local minimal security/audit events; privacy-safe behavior remains the fallback.
- **Dependencies on earlier sprints:** Cross-cutting, finalized after Sprints 7–18 expose stable identifiers/events.
- **Risks:** Telemetry leakage, vendor cost, alert fatigue, excess label cardinality, and regional data-handling constraints.
- **Complexity:** High.
- **Priority:** P0 for beta/launch.
- **Estimated implementation order:** Schemas/redaction, correlation, metrics/traces, domain audit, consent/privacy, SLOs/alerts, migration/retention, then incident drills.
- **Deliverables:** Observability libraries/schema, end-to-end traces, SLO/alert catalog, privacy center, audit pipeline/UI, retention policy, and redaction tests.
- **Definition of Done:** Launch-critical journeys are observable within privacy/cardinality budgets, audit/security events are complete, and alert/privacy/retention drills pass.

### Sprint 20 — Production Deployment for 10,000 Users

- **Business objective:** Deploy a recoverable, secure, cost-understood platform sized from measured workloads and able to scale horizontally.
- **Why this sprint is necessary:** The all-in-one development/self-host topology is not an acceptable paid SaaS topology even after Phase 0 hardening.
- **Current technical problems:** Dockerfile, Dockerfile.dev, docker-compose.yml, nginx.conf, and start.js bundle substantial runtime concerns; local SQLite/app-data/export assumptions and root startup behavior do not define HA, backup, pooling, or rolling migration.
- **Evidence from the repository:** Dockerfile and start.js launch Next.js/FastAPI and prepare runtimes; docker-compose.yml is a local topology; servers/fastapi/services/database.py supports SQLite/PostgreSQL but no pooler deployment; nginx.conf is a single proxy configuration.
- **User-facing problems caused by the current design:** A host/process failure can interrupt work, maintenance can create downtime, and recovery objectives are undefined.
- **Security implications:** Production needs TLS, secret management, non-root workloads, network segmentation, image provenance, least privilege, backup encryption, migration controls, and hardened readiness.
- **Scalability implications for approximately 10,000 users:** Stateless web/API replicas, pooled PostgreSQL, Redis, classed worker pools, object storage, CDN, and measured autoscaling address the stated assumptions without premature Kubernetes.
- **Provider-agnostic implications:** Infrastructure configuration selects replaceable managed/self-hosted PostgreSQL, Redis, S3-compatible, observability, email, and conversion endpoints behind existing contracts.
- **Scope:** Web/API instances, PostgreSQL/pooler, Redis, workers, object storage, reverse proxy/TLS/CDN, backups/PITR, secrets, migrations, rolling deploy, health/readiness, measured autoscaling, capacity/cost, disaster recovery, and no-Kubernetes decision.
- **Explicit out-of-scope items:** Multi-region active-active, Kubernetes absent evidence, custom database/cache/object implementations, and global regional launch.
- **Existing files to modify:** Dockerfile, Dockerfile.dev, docker-compose.yml, nginx.conf, start.js, servers/fastapi/api/lifespan.py, servers/fastapi/services/database.py, .github/workflows/docker-release.yml, .github/workflows/test-all.yml, and the Phase 0 deployment/security runbooks under docs.
- **Existing files to split:** All-in-one start.js into role-specific image commands; Dockerfile into reproducible web, API, worker, export, and conversion targets where resource isolation requires.
- **Existing files to deprecate:** Root all-in-one production container, production SQLite, instance-local assets/exports, in-process workers, and mutable startup dependency installation.
- **Existing files to delete:** Root/all-in-one entry paths only after role images and local developer replacement are documented/tested; keep Docker Compose for development.
- **New files to create:** deploy/compose/production-reference.yml, deploy/reverse-proxy/*, deploy/images/* entrypoints, deploy/migrations/run.py, deploy/health/*, config/production-schema.json, docs/operations/deploy.md, backup-restore.md, disaster-recovery.md, capacity-plan.md, and runbooks/*.
- **Database models and migrations:** No product model; enforce PostgreSQL migration locks, backward-compatible expand/contract checks, statement/lock timeouts, indexes, partition/retention plans, and connection budget.
- **API changes:** Liveness, readiness, startup, and internal dependency health separated; public health reveals no sensitive topology.
- **Frontend changes:** Maintenance/degraded-mode, retry-safe submissions, region-neutral static/CDN assets, and status/support diagnostic links.
- **Background-job changes:** Deploy worker pools by AI/image/export/conversion/webhook/maintenance class with independent concurrency, graceful drain, autoscaling signals, and dead-letter operations.
- **Storage changes:** S3-compatible production adapter, CDN for public immutable assets only, lifecycle/replication/versioning policy, restore tests, and no shared local volume as authority.
- **Security controls:** Non-root/read-only containers, dropped capabilities/seccomp where supported, egress segmentation, TLS/HSTS, external secret manager, signed/scanned images/SBOM, firewall, backup encryption, admin path controls, and fail-closed config.
- **Observability requirements:** Instance/dependency saturation, pool connections, Redis/queue health, worker resources, object errors, CDN/cache, SLOs, deploy markers, cost by service, and capacity headroom.
- **Migration strategy:** Build staging parity, restore anonymized backup, deploy role services, canary web/API, drain workers, run expand migration, shift traffic, validate, then contract later.
- **Backward-compatibility strategy:** Rolling-safe API/event/job/document versions and N-1 workers during deploy; no migration requires simultaneous global restart.
- **Feature flags:** traffic canary, worker_pool_by_class, direct_object_upload, read_only_maintenance, and per-operation emergency switches.
- **Testing strategy:** Reproducible image build/SBOM/signature, PostgreSQL/Redis/object integration, rolling deploy, connection exhaustion, dependency outage, backup/PITR restore, worker drain, load/soak, and disaster simulation.
- **Acceptance criteria:** Measured test workload meets approved SLO/headroom/cost; restore meets documented RPO/RTO; no production role runs root or uses SQLite/local identity; deployment is rolling and reversible.
- **Rollback strategy:** Automated traffic rollback to prior compatible image, worker drain/requeue, forward-fix database under expand/contract, and documented restore only for true disaster.
- **Dependencies on earlier sprints:** Sprints 7–19, especially durable jobs, object storage, and observability.
- **Risks:** Managed service availability in region, connection storms, migration locks, capacity underestimation, secret/config drift, and cost surprises.
- **Complexity:** Very high.
- **Priority:** P0 before public launch.
- **Estimated implementation order:** Staging role images, managed dependencies/secrets, health/pooling, backups/restore, rolling pipeline, load/cost tuning, then launch topology.
- **Deliverables:** Production reference architecture, role images, CI/CD, migration runner, capacity/cost model, backup/PITR/DR runbooks, and completed drills.
- **Definition of Done:** The approved topology survives load, instance/dependency failure and restore drills within measured SLO/RPO/RTO, with signed reproducible artifacts and no Kubernetes absent a decision record.

### Sprint 21 — Complete QA, Security, Performance, and Launch

- **Business objective:** Prove the product is safe, reliable, usable, bilingual, supportable, and commercially ready through evidence-based release gates.
- **Why this sprint is necessary:** Passing component tests is not proof that tenant, money, provider, export, recovery, and Arabic workflows work together under failure and load.
- **Current technical problems:** The repository has substantial backend unit/integration tests, Next tests/Cypress component coverage, Electron tests, and CI, but no complete future-system launch matrix or measured SaaS load/security results.
- **Evidence from the repository:** .github/workflows/test-all.yml, servers/fastapi/tests, servers/nextjs/tests, servers/nextjs/cypress, electron/tests, scripts/package-metadata.test.mjs, scripts/scan_secrets.py, and SBOM/integrity scripts provide the baseline suite.
- **User-facing problems caused by the current design:** Cross-feature regressions, Arabic/export differences, outage behavior, and recovery gaps may only be discovered after users lose time or money.
- **Security implications:** Launch requires penetration testing and regression coverage for tenant isolation, uploads, prompt injection, SSRF, XSS, auth, limits, payments, credits, desktop, and supply chain.
- **Scalability implications for approximately 10,000 users:** Load, soak, queue backlog, provider outage, pool exhaustion, and restore measurements validate or revise the planning assumptions.
- **Provider-agnostic implications:** Contract and chaos tests run against fakes for every provider class, and launch is not blocked by one provider when policy permits a safe alternative.
- **Scope:** Unit/integration/E2E/RTL/export/payment/credit/tenant/upload/prompt/SSRF/XSS/limit tests; load/backlog/outage/restore; penetration testing; accessibility; alpha/beta gates; Syrian launch checklist.
- **Explicit out-of-scope items:** Unmeasured multi-region expansion, unsupported providers/formats, and acceptance of unresolved Critical/High launch risks.
- **Existing files to modify:** .github/workflows/test-all.yml, .github/workflows/secret-scan.yml, servers/fastapi/pyproject.toml, servers/nextjs/cypress.config.ts, servers/nextjs/package.json, electron/package.json, package.json, docker-compose.yml, docs/security/*, and all existing test directories as defects are found.
- **Existing files to split:** CI into fast PR, integration, security/supply-chain, export compatibility, nightly load/soak, and release-gate workflows with explicit ownership.
- **Existing files to deprecate:** Flaky tests, real-provider tests in gating CI, broad skips, snapshots without semantic assertions, and manual-only launch checks that can be automated.
- **Existing files to delete:** Tests only when duplicate/obsolete behavior is proven and replacement coverage is stronger; never delete tests merely to make CI green.
- **New files to create:** tests/e2e/*, tests/security/*, tests/performance/*, tests/chaos/*, tests/fixtures/*, .github/workflows/nightly.yml, release-gate.yml, docs/quality/test-matrix.md, launch-gates.md, and docs/launch/syria-checklist.md.
- **Database models and migrations:** No product schema; seed factories generate stable workspaces, plans, ledger/payment/jobs/documents/assets; migration rehearsal covers every supported release path.
- **API changes:** Only fixes discovered by testing; freeze launch API/document/job/event versions and publish compatibility/support windows.
- **Frontend changes:** Only verified defects, accessibility, localized copy, degraded-mode, and support diagnostics; no late unscoped redesign.
- **Background-job changes:** Failure injection validates crash, retry, cancellation, backlog fairness, poison jobs, provider outage, worker drain, and settlement invariants.
- **Storage changes:** Validate direct upload, malware/quarantine, lifecycle, tenant capability, object outage, checksum, export/receipt privacy, backup and restore.
- **Security controls:** Independent threat-model review, SAST/dependency/secret/container/IaC scans, DAST, manual penetration test, abuse exercises, signing/SBOM verification, and closure/accepted-risk register.
- **Observability requirements:** Every gate emits comparable reports; test traffic is labeled; SLO, queue, cost, security and restore dashboards demonstrate detection and response.
- **Migration strategy:** Progress internal development to private alpha, closed beta, Syrian commercial launch, then broader regional launch only when each signed gate passes.
- **Backward-compatibility strategy:** Test N-1 clients/workers/documents/jobs, desktop upgrade, in-flight jobs, migration rollback/forward-fix, and old links/catalog versions.
- **Feature flags:** Cohort/release gates for every high-risk domain; freeze flag semantics, owners, defaults, expiry, and emergency procedure before launch.
- **Testing strategy:** Risk-based pyramid plus realistic E2E, RTL and visual matrices, deterministic fakes, fuzz/property tests, load/soak/chaos, restore drill, and external penetration/accessibility review.
- **Acceptance criteria:** Zero open Critical/High unauthenticated issues; agreed High risks disabled or fixed; all launch suites green; capacity/SLO/cost and RPO/RTO approved; legal/privacy/payment/operations owners sign off.
- **Rollback strategy:** Predefined release rollback, feature disable, queue drain, payment pause, export/provider isolation, forward-compatible database path, communication template, and staffed incident command.
- **Dependencies on earlier sprints:** All earlier sprints; this sprint is a gate, not a substitute for their Definition of Done.
- **Risks:** Compressed launch schedule, flaky environments, false confidence from synthetic load, late legal/provider findings, and unresolved manual operations.
- **Complexity:** Very high.
- **Priority:** P0 final gate.
- **Estimated implementation order:** Test matrix/data, continuous feature qualification, full staging rehearsal, alpha exit, closed-beta soak/pen test, launch drill, then signed go/no-go.
- **Deliverables:** Complete evidence pack, test/security/performance reports, compatibility matrix, restore and incident records, accepted-risk register, release notes, and Syrian launch checklist.
- **Definition of Done:** A cross-functional go/no-go review approves measured evidence; all mandatory gates are green or explicitly non-launching; rollback/on-call/support teams complete the rehearsal.

### Delivery sequence and release gates

The sprint numbers are the recommended implementation order, not a license to run twenty-one isolated waterfalls. Security, testing, legal review, observability, and documentation continue in every sprint. Sprints 1–4 establish boundaries and the canonical contract; Sprints 5–9 establish safe state, tenant, job, and asset foundations; Sprints 10–12 migrate product generation; Sprints 13–15 make commercial state explicit; Sprints 16–17 harden export/conversion products; Sprints 18–20 establish operations and deployment; Sprint 21 is the final evidence gate.

Private alpha must not begin until Sprints 1, 3–10, and 19 have their alpha acceptance criteria. Closed beta additionally requires revision recovery, entitlements in shadow mode, object storage, durable exports for the offered formats, tenant isolation, and staffed operations. No paid transaction may be accepted before Sprints 13–15 and ledger/payment failure drills pass. No Syrian commercial launch occurs before Sprints 16, 18, 19, 20, and 21 pass their launch gates.

## Existing files to retain

The entries below remain valuable. Retain does not mean freeze; the future changes column is part of the decision.

| Path | Current purpose | Why it remains valuable | Required future changes | Sprint responsible |
|---|---|---|---|---|
| LICENSE | Repository license | Defines the upstream code license and cannot be replaced by rebranding | Preserve verbatim; have counsel evaluate derivative/commercial obligations | 2 and 21 |
| NOTICE | Third-party/upstream notices | Required provenance and attribution baseline | Generate reviewed additions from SBOM/assets without removing existing required notices | 2, 16, 21 |
| package.json and package-lock.json | Root scripts and locked Node toolchain/export dependencies | Reproducible orchestration and metadata source | Reduce duplicated scripts, keep deterministic version/SBOM/integrity commands, enforce package policy | 1, 20, 21 |
| servers/fastapi/pyproject.toml and uv.lock | Python 3.11 dependency and tool lock | Reproducible backend environment with current tests/dev tools | Maintain safe index policy, split optional worker/provider groups if measurement supports it, audit every release | 1, 8, 20, 21 |
| servers/nextjs/package.json and package-lock.json | Web application dependencies/scripts | Reproducible Next.js build and test boundary | Add localization, generated-client, architecture, RTL, E2E, and release checks; remove unused packages with evidence | 1, 3, 21 |
| electron/package.json and package-lock.json | Desktop build/runtime dependency lock | Desktop distribution remains a supported channel | Preserve IPC/security tests, generate identity/version metadata, maintain signed update and artifact policy | 2, 16, 20, 21 |
| servers/fastapi/alembic/env.py and alembic/versions | Database migration mechanism/history | Existing installations and future PostgreSQL migrations require a continuous history | Make PostgreSQL CI authoritative, use expand/backfill/contract discipline, remove placeholder file fallback safely | 1 and every schema sprint |
| servers/fastapi/api/v1/auth/* | Username/session/bootstrap authentication | Phase 0 removed public bootstrap claim and established a usable identity baseline | Separate identity from workspace authorization, add step-up/service scope, preserve secure bootstrap | 7, 18, 21 |
| servers/fastapi/api/operation_security.py | Distributed-capable rate/concurrency policy | Central Phase 0 admission and emergency-control point | Consume entitlements/budgets, expose classed metrics, integrate every expensive operation | 8, 13, 14, 17, 19 |
| servers/fastapi/utils/outbound_http.py | Central SSRF-safe outbound HTTP | Essential shared defense for providers, webhooks, imports, and remote assets | Add adapter-specific allowlists, network policy hooks, trace metrics, and continuous rebinding tests | 9, 10, 17, 19 |
| servers/nextjs/lib/safe-markdown.ts | Central safe Markdown policy | Prevents divergent XSS handling in multiple renderers | Keep one sink contract, add localization/RTL fixtures and canonical rich-text adapters | 3–5, 21 |
| servers/nextjs/lib/security-headers.mjs and next.config.mjs | Web security-header policy and application configuration | Central CSP/header enforcement is a launch requirement | Move to nonce/hash CSP where needed, account for approved CDN/object endpoints, retain strict tests | 2, 3, 9, 19, 21 |
| servers/nextjs/lib/telemetry-privacy.mjs and utils/mixpanel.ts | Phase 0 privacy-safe analytics gating | Establishes opt-in/off defaults and a replaceable control seam | Integrate a versioned consent domain and provider-neutral event schema | 19 |
| electron/app/ipc/security.ts and electron/tests/* | Electron IPC validation and security regressions | Narrow desktop trust boundary is worth preserving | Apply to every new IPC channel, add canonical document/object capability contracts and signed update tests | 5, 9, 16, 21 |
| config/artifact-integrity.json | Pinned artifact integrity and trust policy | Prevents silent execution of unverified downloads | Maintain through release automation, legal review, signatures/provenance, and fail-closed runtime policy | 16, 20, 21 |
| scripts/sync-presentation-export.cjs and electron/scripts/sync-export-runtime.cjs | Verified export-runtime acquisition/validation | Existing export behavior can be audited behind an adapter | Keep only if exporter decision approves it; generate provenance and move execution to isolated worker | 16 |
| scripts/generate-sbom.mjs and scripts/scan_secrets.py | Reproducible SBOM and secret detection | Core supply-chain and repository controls | Run in release gates, archive attestations, add policy thresholds and canary regressions | 19–21 |
| servers/fastapi/templates/v2/* | Current structured template schema and generation knowledge | Valuable source for canonical schema migration and template compatibility | Separate authoring schema from canonical document, remove executable layouts, add RTL/provenance fixtures | 4, 5, 16 |
| templates/*/template.json and reviewed static assets | Built-in presentation templates | Valuable product content and migration/export corpus | Inventory licenses, convert to canonical templates, add Arabic variants and compatibility metadata | 2–5, 16 |
| servers/nextjs/components/slide-editor/* | Konva editor primitives and interaction logic | Significant product/editor investment | Refactor into canonical commands/renderers, split oversized files, add RTL/performance/visual coverage | 4–6 |
| servers/fastapi/tests, servers/nextjs/tests, servers/nextjs/cypress, electron/tests | Existing regression suites | Preserve learned behavior and Phase 0 security checks | Organize by risk/module, add PostgreSQL/E2E/RTL/export/payment/load/chaos coverage; never weaken to pass CI | Every sprint, final owner 21 |
| Dockerfile, Dockerfile.dev, and docker-compose.yml | Reproducible build and local topology | Useful build foundation and developer workflow | Build role-specific non-root images, retain Compose for local integration, attach SBOM/signatures | 8, 16, 20 |

## Existing files to refactor

| Path | Current problems | Target responsibility | Required split or redesign | Sprint responsible | Migration risk |
|---|---|---|---|---|---|
| servers/fastapi/api/v1/ppt/endpoints/presentation.py | Very large route module mixes validation, generation, persistence, SSE, assets, templates, background work, and export | Thin versioned presentation/generation HTTP adapters | Extract application commands/queries, typed job submission, canonical serializers, revision preconditions, and export facade | 1, 4, 6, 8, 11, 16 | Very high: central happy path and legacy clients |
| servers/fastapi/api/v1/ppt/endpoints/template.py | Large import/create/query/task and conversion surface | Thin template API over declarative canonical templates | Split import validation, template repository, preview, font/assets, and durable creation handlers | 1, 4, 5, 8 | High: imported-template corpus |
| servers/fastapi/services/chat/memory_layer.py | Multi-thousand-line editing/memory/tool integration with presentation knowledge | Chat application service producing authorized canonical commands | Split context, prompt policy, tool registry, command translation, provider call, persistence, and memory adapters | 1, 4, 5, 10, 11 | Very high: subtle editing behaviors |
| servers/fastapi/services/chat/tools.py and slide_ui_helpers.py | Tools mutate renderer-shaped slide UI and contain extensive helper logic | Provider-neutral chat tools operating canonical elements/commands | Separate tool schemas, authorization, command handlers, canonical adapters, and compatibility layer | 4, 5, 10 | High: provider tool-call compatibility |
| servers/fastapi/services/image_generation_service.py | Provider selection, errors, placeholders, generation, and path persistence are coupled | Image plan/application service over ImageAIProvider and Asset service | Split provider adapter, validator, durable handler, binding, and settlement | 9, 10, 12, 14 | High: cost and partial results |
| servers/fastapi/services/export_task_service.py | Large local subprocess/path/URL/cookie runtime orchestration | Isolated ExportProvider adapter and capability client | Split canonical mapper, scoped capability, process sandbox, result validator, and object persistence | 8, 9, 16 | Very high: launch-critical output |
| servers/fastapi/services/documents_loader.py and document_conversion_service.py | Extraction/conversion and local file assumptions overlap | Document ingestion client and FileConversionProvider adapter | Separate scanned-asset ingestion, extraction, conversion operations, provider execution, and result validation | 9, 17 | High: parser/file compatibility |
| servers/fastapi/services/temp_file_service.py | Temporary local paths cross request boundaries | Ephemeral local StorageProvider/quarantine implementation only | Replace API path identity with upload session and asset IDs; retain bounded scratch lifecycle | 9, 17 | High: legacy uploads/in-flight work |
| servers/fastapi/services/database.py and utils/db_utils.py | Supports SQLite and PostgreSQL but commercial pooling/transaction ownership is diffuse | Core PostgreSQL session/transaction infrastructure with local SQLite adapter | Centralize unit of work, pool policy, timeouts, migration checks, and test factories | 6–8, 20 | High: every persistence path |
| servers/fastapi/models/sql/presentation.py and slide.py | Renderer/source/path fields coexist; owner is user-specific; mutable rows lack revisions | Persistence mappings for canonical presentation metadata/current revision | Add workspace/revision/document references; migrate and later remove content/ui/html/path truth | 4, 6, 7, 9 | Very high: all stored decks |
| servers/fastapi/models/sql/async_task.py | Generic status/data lacks durable attempt, lease, cancel, idempotency semantics | Compatibility view over durable Job domain | Migrate IDs/status, normalize payload versions, then retire table/model after retention | 8 | High: in-flight task visibility |
| servers/fastapi/models/sql/provider_settings.py and services/provider_settings.py | Global JSON singleton can combine secrets and provider policy | Encrypted workspace/system provider accounts and routing policy | Normalize accounts/capabilities/secrets/snapshots; migration redacts and verifies before deletion | 10 | Very high: secret availability |
| servers/fastapi/api/v1/admin/router.py | Monolithic/coarse superuser administration | Versioned policy-protected platform administration adapters | Split users, workspaces, jobs, providers, billing, payments, storage, security and audit queries/commands | 7, 18 | High: privilege boundary |
| servers/fastapi/api/main.py and api/lifespan.py | Central wiring/startup for many concerns | Composition root and explicit lifecycle/readiness | Register module routers/providers/workers, validate production config, separate liveness/readiness | 1, 8, 19, 20 | Medium: startup ordering |
| servers/nextjs/app/(presentation-generator)/presentation/components/Chat.tsx | Multi-thousand-line conversation/editor orchestration | Feature shell composed from chat state, messages, tools, and presentation context | Split feature services/hooks/components and consume canonical commands/job events | 1, 5, 8, 11 | High: core interaction |
| servers/nextjs/components/slide-editor/surface/nodes.tsx | Multi-thousand-line all-element rendering | Registry of small typed canonical element renderers | Split text/image/shape/chart/table/group renderers and safe unknown fallback | 5 | Very high: visual fidelity |
| servers/nextjs/components/slide-editor/surface/TemplateV2KonvaSlide.tsx | Stage, events, selection, layout, and rendering are intertwined | Konva renderer shell over document store/commands | Separate stage lifecycle, overlays, interaction controller, viewport, and element registry | 5 | Very high: editing behavior |
| servers/nextjs/components/slide-editor/model/model.ts | Large renderer-centric model overlaps backend/template schema | Generated canonical types plus editor-only view/session models | Move persistent types to generated binding; isolate derived geometry/session state | 4, 5 | Very high: serialization |
| servers/nextjs/lib/template-v2-json-to-html.ts | Large independent renderer/serializer with security and fidelity burden | Browser/export compatibility adapter from canonical document | Split element serializers, style policy, asset resolution, direction/font logic; retire if exporter no longer needs HTML | 4, 5, 16 | High: preview/export parity |
| servers/nextjs/app/(presentation-generator)/presentation/hooks/useAutoSave.tsx | Network save, timing, diff, and UI semantics share a hook | Revision persistence client plus local recovery state | Split journal, debounce, conflict/ETag, transport, acknowledgement, multi-tab coordinator | 6 | High: lost-edit risk |
| servers/nextjs/app/(presentation-generator)/upload/components/UploadPage.tsx | Form and generation request logic are component-driven | Structured generation feature shell | Generate typed form from specification; split sections, estimate, draft, validation, submission | 3, 11 | Medium: conversion of saved drafts |
| servers/nextjs/app/(presentation-generator)/(dashboard)/admin/AdminPanel.tsx | One large panel cannot scale permissions/domains | Admin layout and feature routes | Split into paginated domain pages with typed permission/action controls | 18 | High: data exposure/actions |
| servers/nextjs/utils/providerConstants.ts, providerUtils.ts, and storeHelpers.ts | Provider names/config branches leak into UI validation and defaults | Capability-driven provider UI adapter | Consume registry metadata and stable capability keys; remove business routing from client | 10 | Medium: setup compatibility |
| electron/app/main.ts and app/ipc/index.ts | Desktop composition and channels remain a sensitive broad boundary | Minimal window/lifecycle composition and explicit IPC registry | Keep security helper, split feature channel registration, version canonical/API contract | 5, 9, 16, 21 | High: desktop compatibility |
| start.js | All-in-one bootstrap, configuration, and multi-service process management | Development/self-host convenience only | Split role commands, remove production authority and runtime installation, preserve deterministic local workflow | 1, 20 | Medium: self-host users |
| nginx.conf | Single static reverse-proxy configuration | Generated/reference edge policy | Split local and production reference, add health/routing/limit/TLS/CDN policy without provider lock-in | 17, 20 | Medium: route/header behavior |

## Existing files to deprecate

| Path | Reason for deprecation | Replacement | Deprecation timeline | Compatibility strategy | Removal sprint |
|---|---|---|---|---|---|
| servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx | Renderer-specific V1 path conflicts with one canonical renderer | Canonical browser/Konva adapters | Read-only after Sprint 4 conversion; warn in alpha; remove after two stable releases with zero fallback | Convert V1 documents and retain safe unknown-element fallback | 5, final removal gated by 21 |
| servers/nextjs/app/(presentation-generator)/components/V1SelectEdit.tsx | Separate V1 editing semantics cannot share commands/revisions | Unified canonical editor commands | Disable V1 writes after canonical parity; retain read-only correction window | V1-to-canonical adapter and migration snapshot | 5–6 |
| servers/fastapi/models/sql/presentation_layout_code.py | Persisted executable layout source is unsafe and not a canonical product model | Declarative canonical template/layout schema | Production already disabled in Phase 0; migrate supported layouts during Sprints 4–5 | Preserve original source in quarantined admin-only migration record, never execute | 5 |
| servers/fastapi/templates/custom_layout_from_db.py | Loads legacy custom code and must not be long-term template execution | Declarative template repository and canonical renderer | Keep production-off through conversion; no new writes | Safe parser/converter for supported subset; static fallback preview | 5 |
| servers/nextjs/app/hooks/compileLayout.ts | Dynamic layout compilation is incompatible with CSP and untrusted SaaS content | Declarative canonical renderer | Production-off in Phase 0; delete after custom template parity | Feature remains unavailable rather than executing legacy code | 5 |
| servers/fastapi/services/concurrent_service.py | Process-local task tracking cannot provide durability or cross-instance coordination | Durable Job workers/leases/outbox | Stop new uses operation by operation in Sprint 8 | Compatibility task status maps active legacy tasks; drain before removal | 8 |
| servers/fastapi/models/sql/provider_settings.py | Global plaintext-like JSON singleton lacks tenant scope and secret lifecycle | Encrypted provider accounts/secrets/routing policies | Shadow import in Sprint 10; read-only for one release; purge secrets after verification | Legacy key mapper and explicit pinned compatibility policy | 10 |
| servers/fastapi/services/temp_file_service.py | Raw local paths cannot identify cross-instance assets | Asset/upload session and StorageProvider | Read-through during Sprint 9 backfill; no new production path identities | Temporary path-to-asset mapping with checksum reconciliation | 9 |
| servers/fastapi/services/export_task_service.py legacy URL/cookie path | General session cookies and internal URL rendering exceed least authority | Canonical ExportProvider with one-time object capabilities | Phase 0 safe-disabled until verified; remove URL mode after export corpus parity | Adapter only for approved migrated documents under monitored flag | 16 |
| servers/nextjs/app/(export)/pdf-maker | Route is tied to the current browser PDF implementation rather than provider contract | Export/conversion feature pages and worker APIs | Retain for compatibility while Sprint 16/17 clients cut over | Redirect old deep links and preserve supported parameters | 17 |
| servers/nextjs/public/Logo.png, logo-white.png, logo-with-bg.png, Presenton_Splash.png | Old product branding cannot remain the independent commercial identity | Approved versioned brand assets | Dual-serve for one web cache/release cycle after Sprint 2 approval | Immutable old URLs and redirects until telemetry shows no supported references | 2 |
| electron/resources/ui/assets/images/presenton_logo.png and presenton_short_filled.png | Old desktop branding must transition without breaking upgrades | Generated approved desktop identity assets | Replace in Sprint 2; retain only where installer upgrade identity requires | Preserve application ID/signing/update compatibility separately from visual brand | 2 |
| start.js production all-in-one mode | Couples roles and root/process/local assumptions | Role-specific production images and commands | Mark self-host/development-only in Sprint 20; remove production recommendation immediately | Keep a documented local Compose wrapper | 20 |

## Existing files to delete

No additional source deletion is authorized at the Phase 0 handoff. The generated
artifacts below were already removed during Phase 0; legacy product code remains in
the deprecation table until its migration proves it obsolete.

| Removed path | Evidence it was not required | Replacement | Completed deletion condition | Tests proving safe removal |
|---|---|---|---|---|
| servers/nextjs/tsconfig.tsbuildinfo | TypeScript incremental compiler build metadata, not source | Ignored, locally regenerated cache | Ignore rule added and clean build/type checks passed | Next tests, lint, and production build |
| servers/fastapi/.coverage | SQLite-backed test coverage cache, not source | Ignored local coverage output | Ignore rules added and the test suite passed without the tracked cache | Full pytest suite and repository secret/generated-artifact scan |
| servers/fastapi/placeholder | Empty SQLite sentinel created by the Alembic fallback URL | In-memory CLI sentinel plus explicit deployment database resolution | Zero application rows confirmed, fallback changed, and migration/import tests passed | FastAPI tests, OpenAPI generation, and Compose validation |

## New files and modules to create

Paths are proposed to match the existing FastAPI, Next.js, Electron, scripts, config, docs, and test structure. Directory stars denote a cohesive module whose exact internal file count should follow the boundary rules from Sprint 1.

| Proposed path | Purpose | Main classes/functions/schemas | Inputs | Outputs | Database dependencies | Provider dependencies | Security responsibilities | Tests | Sprint responsible |
|---|---|---|---|---|---|---|---|---|---|
| docs/architecture/module-boundaries.md | Define module ownership and allowed dependencies | Dependency rules, route/table owners, ADR links | Current import/route/model inventory | Enforceable architecture map | Lists table owners | None | Identify trust boundaries and authorization owner | Boundary script fixtures/review | 1 |
| config/product-identity.json and generated identity modules | Single approved product metadata source | ProductIdentity schema and generators | Legal/product-approved names/assets/URLs | Web/Electron/export/package metadata | Optional brand version only | Update/notification domains are configuration, not provider coupling | Approved domains, signing identity, no notice removal | Metadata, installer, link and snapshot tests | 2 |
| servers/nextjs/i18n/* and app/[locale]/* | Arabic/English routing, catalogs, formatting and RTL shell | Locale config, message loader, LocaleSwitcher, formatters | Request/user/workspace locale and message parameters | Escaped localized UI and lang/dir | User/workspace locale fields | None | No HTML catalogs; safe interpolation; bilingual security copy | Catalog, pseudolocale, accessibility, RTL E2E | 3 |
| schemas/presentation-document/v1.schema.json | Canonical versioned presentation contract | Document, Slide, Element, TextRun, AssetRef, ExportIntent schemas | Legacy documents and new commands | Valid canonical JSON | presentation_documents/revisions | None directly | Size/depth/protocol/reference constraints; no executable code | Cross-language goldens, fuzz, migration corpus | 4 |
| servers/fastapi/modules/presentations/* | Presentation domain, canonical validation, commands, migration, persistence and API | PresentationDocument, revision commands, converters, repositories | Authorized API commands/jobs/legacy records | Canonical revisions/domain events | Presentation/document/revision tables | Provider-neutral generation results only | Workspace policy, schema validation, optimistic concurrency | Unit, PostgreSQL integration, tenant and migration tests | 4 and 6 |
| servers/nextjs/generated/presentation-document.ts and lib/presentation-document/* | TypeScript binding and canonical document client utilities | Generated types, validator, patch/checksum adapters | API documents and editor commands | Valid typed state/patches | Via API only | None | Reject invalid/unsafe documents and unknown versions safely | Python/TS fixture parity, malicious documents | 4 |
| servers/nextjs/components/editor/commands/* and renderers/* | Unified editing commands and renderer adapters | Command registry, document store, Konva/browser renderers, asset resolver | Canonical document, authorized user input, asset capabilities | Patches and visual output | Revision API only | None | No eval/HTML; safe assets; complexity limits | Undo properties, RTL input, visual/performance/security | 5 |
| servers/nextjs/lib/indexeddb/recovery.ts and features/presentations/persistence/* | Durable local journal, ETag save and conflict recovery | RecoveryJournal, SaveClient, MultiTabCoordinator | Canonical patches/revisions/network events | Durable acknowledgements/conflict state | Revision API only | None | Workspace/user partitioning, no secret persistence, bounded retention | Offline/crash/multi-tab/conflict E2E | 6 |
| servers/fastapi/modules/workspaces/* | Workspace membership, roles, invitations, service scopes and policy | Workspace, Membership, Invitation, RolePolicy, authorize | Authenticated principal and resource/workspace IDs | Authorization decisions/audit events | Workspace/membership/invitation/service credential tables | None | Tenant isolation, least privilege, token hashing/expiry | Exhaustive role and cross-tenant tests | 7 |
| servers/fastapi/modules/jobs/* and workers/* | Durable jobs, attempts, outbox/inbox, leasing and handlers | Job, JobAttempt, Outbox, Inbox, WorkerRegistry, lease/cancel/retry | Versioned operation commands and object IDs | Durable status/events/results | Job/outbox/inbox/dead-letter tables | Handlers call provider interfaces | Idempotency, payload bounds, secret-free queues, least authority | Crash/lease/replay/cancel/outbox/Redis tests | 8 |
| servers/fastapi/modules/assets/* and providers/storage/* | Managed assets, direct uploads, object abstraction and lifecycle | Asset, UploadSession, StorageProvider, local/S3 adapters, lifecycle | Upload metadata/streams, workspace, object refs | Private assets/capabilities/thumbnails | Asset/object/reference/upload tables | S3-compatible adapter is replaceable | MIME/size/malware/quarantine/ownership/signed access | Provider contract, traversal, malicious file, lifecycle tests | 9 |
| servers/fastapi/modules/providers/* | Provider contracts, registry, encrypted config, routing, health and cost hooks | TextAIProvider, ImageAIProvider, SearchProvider, Registry, Router, Circuit | Normalized requests, capability/policy, encrypted references | Normalized results/usage/errors and snapshot | Provider account/secret/policy/health/snapshot tables | All AI/image/search adapters plug in here | Encryption, SSRF, TLS, redaction, timeouts, circuit/disable | Adapter contract and outage/security tests | 10 |
| schemas/generation-spec/v1.schema.json and modules/generation/* | Structured generation request, plan, constraints and verification | GenerationSpecification, Plan, ConstraintEngine, Verifier | User form, source assets, provider-neutral results | Canonical candidate commands and report | Generation request/plan tables | TextAIProvider via job handler | Prompt/data separation, schema/limit enforcement | Precedence, structured-output, partial-failure E2E | 11 |
| servers/nextjs/features/generation-form/* | Bilingual structured form and editable outline | Schema form, outline editor, estimate/progress clients | Locale, draft spec, entitlement estimate | Valid versioned generation submission | API only | Capability labels via registry API | Safe validation/interpolation and no secret fields | RTL/accessibility/E2E with fake providers | 11 |
| servers/fastapi/modules/images/* and workers/generate_image.py | Exact-count image planning, per-item jobs and stable bindings | ImagePlan, ImageRequest, ImageBinding, settle_result | Generation plan, asset refs, normalized image request | Validated asset bindings/progress/usage event | Image plan/request/binding and asset tables | ImageAIProvider/SearchProvider | SSRF/file validation/ownership/idempotent settlement | Exact-count, partial/retry, malicious source, race tests | 12 |
| servers/fastapi/modules/entitlements/* | Versioned plan catalog, subscriptions and entitlement evaluation | PlanVersion, Entitlement, Subscription state machine, Evaluator | Workspace, time, catalog and requested capability | Allow/deny/limit decision and transition events | Plan/entitlement/subscription/period tables | None; capabilities are provider-neutral | Server authority, admin RBAC, idempotent transitions | Matrix, boundary time, concurrent transitions | 13 |
| servers/fastapi/modules/credits/* and modules/usage/* | Immutable product-credit ledger, quotas, reservations and provider cost accounting | Ledger, Reservation, Settlement, UsageEvent, Budget | Authorized operation/job outcome/provider-normalized usage | Balanced entries, quota/cost decisions, reports | Wallet/ledger/reservation/usage/cost/budget tables | Normalized usage from any adapter | Append-only, precision, locking, anomaly and admin separation | Concurrency/replay/refund/reconciliation invariants | 14 |
| servers/fastapi/modules/payments/* | Provider-neutral intents, manual adapters, review, refund and reconciliation | PaymentProvider, PaymentIntent, Manual adapters, ReviewDecision | Price snapshot, private receipt, reference, reviewer command | Immutable status/events and activation/grant commands | Payment/decision/refund/reconciliation/fraud tables | Manual adapters now; official adapters only when real/reviewed | Receipt privacy, RBAC/step-up, dedupe/fraud/audit/idempotency | State machine, replay, privacy, reconciliation, fake adapters | 15 |
| servers/nextjs/features/payments/* and features/admin/payments/* | Customer payment flow and finance-review operations | Intent form/timeline, receipt upload, ReviewQueue/Detail | Localized instructions, payment API, private capabilities | Submitted evidence and audited reviewer commands | API only | Adapter capabilities from API | Never expose receipts publicly/secrets; safe copy/confirmations | RTL/accessibility, authorization, duplicate/concurrent review E2E | 15 and 18 |
| servers/fastapi/modules/exports/* and workers/export.py | Canonical revision export contract, capability and isolated worker | ExportProvider, ExportRequest, ScopedCapability, CompatibilityReport | Canonical revision, options, scoped assets/fonts | Validated PPTX/PDF Asset and report | Export request/result/capability tables | Current or replacement exporter adapter | One-time capability, sandbox, integrity, egress/resource bounds | OOXML/PDF/visual/RTL/replay/cancel corpus | 16 |
| servers/fastapi/modules/conversion/* and workers/conversion.py | FileConversionProvider and safe PDF/office utility jobs | FileConversionProvider, OperationSpec, Gotenberg/local adapter | Scanned input asset IDs and bounded options | Validated expiring output assets | Conversion job/input/output tables | Gotenberg/equivalent behind adapter; MalwareScanner | Sandbox, malware, MIME/decompression/page/resource limits | Malformed/malicious corpus, operation and outage tests | 17 |
| servers/nextjs/features/admin/* | Modular least-privilege operations dashboard | Domain query tables, action/approval forms, emergency controls | Paginated redacted admin APIs and operator roles | Audited typed commands/views | API only | Normalized provider health only | Step-up, redaction, approvals, no secret reveal | Permission/redaction/pagination/audit E2E | 18 |
| servers/fastapi/core/observability/* and config/telemetry-schema.json | Shared structured logging, metrics, traces, redaction and audit schemas | CorrelationContext, Redactor, metric/trace/audit emitters | Allowlisted identifiers/lifecycle events | Privacy-safe telemetry and audit | Consent/audit tables where applicable | Replaceable exporters only | Secret/PII/content exclusion, retention and access control | Canary-secret, cardinality, trace and consent tests | 19 |
| deploy/* and docs/operations/* | Role-specific production topology, migrations, health, backup, capacity and DR | Image entrypoints, migration runner, config schema, runbooks | Signed images/config/secrets and managed dependencies | Reproducible deploy, health, restore and capacity evidence | PostgreSQL/pooler/migration dependencies | Infrastructure adapters configured, not hardcoded | Non-root, TLS, secrets, network policy, signed SBOM, backup encryption | Build, rolling deploy, load, failover and restore drills | 20 |
| tests/e2e, tests/security, tests/performance, tests/chaos and release workflows | Cross-system launch evidence and gates | Stable fixtures, fake providers, load/chaos scenarios, report gates | Versioned builds and synthetic non-production data | Auditable pass/fail reports and launch evidence | Seeded PostgreSQL and migration corpus | Fakes/contract sandboxes; no paid real calls in gating CI | Tenant/payment/upload/prompt/SSRF/XSS/supply-chain/restore coverage | The directories themselves are the complete launch suite | 21 |

## Roadmap maintenance rules

- Update repository evidence and inventories whenever a sprint changes relevant paths; do not let this document become a speculative parallel architecture.
- Every sprint starts with an architecture/security/data-migration review and ends with measured acceptance evidence, updated runbooks, and an explicit deprecation-register decision.
- New providers must enter through the relevant interface and contract suite. A product deadline is not permission to add a provider-specific field to canonical, financial, job, workspace, or asset models.
- Database changes use expand, bounded/idempotent backfill with reconciliation, dual-read/write only when necessary, observed cutover, and delayed contract. Destructive rollback is not the default.
- Feature flags require owner, purpose, safe default, cohort, metrics, emergency procedure, and expiry/removal date. High-risk flags remain off in production until their named acceptance gate.
- Capacity values in this roadmap remain assumptions until Sprint 20/21 evidence replaces them. Scale the simplest topology that meets measured SLOs; do not adopt Kubernetes or microservices as a status symbol.
- Deletions require reachability evidence, replacement coverage, migration reconciliation, and rollback-window expiry. Unknown code is investigated or deprecated, never casually removed.

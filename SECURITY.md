# Bayanly security model

This document records protections and gaps present in the repository today. `MUST` and `MUST NOT` are invariants for future changes. A protection listed under “Known gaps” is not implemented merely because it is desirable or appears in the roadmap.

## Trust boundaries

Untrusted inputs include browser/API requests, cookies and bearer tokens, workspace/resource identifiers, presentation and Markdown content, uploaded files, templates/layouts, URLs and DNS, provider responses, web-search results, environment/user configuration, database rows created by older versions, Redis deliveries, object-store metadata, Electron renderer IPC, downloaded external runtimes, and child-process output.

The primary enforcement boundaries are:

- FastAPI authentication middleware and backend authorization/application services;
- SQL owner/workspace predicates and transaction boundaries;
- canonical Pydantic/JSON Schema validation for presentation data;
- secure outbound HTTP and provider adapters;
- durable job validation, idempotency, leases, and handler authority checks;
- managed asset validation/quarantine/storage providers;
- safe Markdown/declarative renderer policies and browser security headers;
- Electron trusted-origin/IPC/path/process validation;
- integrity-pinned external artifacts and locked dependencies.

## Authentication and sessions

### Current protections

- `SessionAuthMiddleware` protects all `/api/*` routes except the explicit status, verify, login, logout, and liveness/readiness paths. It also protects API documentation and `/app_data/*`.
- Login uses normalized username lookup, one generic invalid-credential response, a dummy password hash when the account is absent/inactive, and a bounded login rate limiter keyed by client/username inputs.
- Browser sessions are signed JWTs in the `presenton_session` cookie. The cookie is `HttpOnly`, `SameSite=Lax`, path `/`, has a 30-day maximum age, and is marked `Secure` when FastAPI observes HTTPS or `X-Forwarded-Proto: https`.
- JWTs carry `auth_version`; an inactive account or version mismatch invalidates an existing session. Password hash upgrades are applied after successful verification.
- The first administrator is provisioned at deployment startup. Public setup/claim, signup, password-reset, and verification routes are not exposed.
- Legacy administrator bearer tokens and feature-flagged service credentials are accepted by the same principal resolver. Service credentials are one-time-issued, digest-verified, workspace-bound, scoped, and revocable.

### Required rules

- Authentication decisions MUST remain server-side. Browser state, `AuthGate`, or server-layout redirects MUST NOT authorize an API operation.
- Production deployments MUST NOT set `DISABLE_AUTH=true`. Desktop/local bypass behavior MUST remain explicit and loopback-contained.
- Session and signing secrets MUST be cryptographically random, persistent across intended restarts, and unavailable to browser code/logs.
- Authentication responses MUST resist username/account-state enumeration. New signup, verification, recovery, or notification behavior MUST add rate, replay, purpose, expiry, and enumeration tests before exposure.
- Service accounts MUST NOT be enabled unless workspaces and workspace RBAC enforcement are enabled and the route-to-permission mapping covers their reachable APIs.

### Known gaps

- There is no startup fail-fast that rejects `DISABLE_AUTH` solely because the deployment labels itself production.
- Legacy administrator bearer tokens are stored as directly lookupable token values rather than a hashed credential record. Admin-only issuance mitigates exposure but this is not modern API-key storage.
- Public account signup, verified email, recovery, purpose-bound one-time challenges, and session-management UI are roadmap-only.

## Authorization, ownership, workspaces, and administration

- **MUST:** Every protected resource read/write, presentation export, async task, asset, provider account, job, invitation, and credential operation enforces the current owner or workspace in the backend query/application layer.
- **MUST:** When workspace rollout is active, membership must be active, the requested resource workspace must match, and the canonical `Permission` matrix or service scope must authorize the action.
- **MUST:** Cross-owner/workspace resource failures should return not-found where practical to resist enumeration. Logs may record safe actor/workspace/resource IDs but responses must not reveal another tenant's existence.
- **MUST:** Admin routes and key/font/model-management mutations remain restricted to an admin browser JWT unless an explicit narrower backend policy is designed and tested.
- **MUST NOT:** Client-supplied owner IDs, workspace headers/cookies, role labels, disabled controls, or route visibility may be trusted without database-backed validation.
- **MUST NOT:** New code may query tenant-owned tables by primary key alone when an owner/workspace predicate or authorized parent lookup is required.

Current owner isolation is active. The broader workspace/RBAC architecture exists but its rollout flags default off and the legacy owner bridge defaults on. This is a staged tenant migration, not evidence that production is already workspace-authoritative.

## Secrets and configuration

- Secrets MUST come from operator environment/configuration or the canonical encrypted provider-secret store when that architecture is enabled. `NEXT_PUBLIC_*`, checked-in files, URLs, analytics, job payloads, and browser state MUST NOT contain secrets.
- `start.js` writes local `userConfig.json` atomically with restrictive mode where supported. This is a local secret-adjacent store, not a production secrets manager.
- Provider registry secrets use AES-256-GCM envelope encryption with a per-secret data key and a separate 32-byte environment master key/version. Ciphertext in SQL is not sufficient if the master key is exposed.
- Master/signing/provider credentials MUST be rotated through established version/invalidation mechanisms. Values MUST NOT be printed during configuration validation.
- Durable job payload validation rejects common secret-shaped keys. New payload schemas MUST carry stable IDs/references, not credentials or provider response bodies.
- `scripts/scan_secrets.py` and its tests are mandatory, but pattern scanning does not replace review or incident response.

## Logging, telemetry, errors, and privacy

- Logs and telemetry MUST NOT include cookies, authorization headers, API keys, passwords, OAuth tokens, signed URLs, prompts, presentation titles/text/notes, uploaded content, raw provider responses, full local paths, or child-process stdout/stderr.
- Use bounded categories, stable codes, safe IDs, counts, duration, state, and bucketed sizes. Analytics errors use the existing sanitizers; Sentry defaults and breadcrumbs must remain privacy-reviewed.
- New APIs SHOULD use `StableAPIError` with a safe code/message/params envelope. Internal exceptions, SQL diagnostics, provider errors, and filesystem paths MUST NOT be reflected to clients.
- Error normalization MUST distinguish retryable dependency failure from validation/auth/authorization failure without exposing credentials or remote response bodies.

New modular APIs follow stable errors, but older routes still use heterogeneous `HTTPException`/detail responses. That inconsistency is a documented gap; do not claim a universal error contract.

## Outbound HTTP, URL validation, and SSRF

`utils/outbound_http.py` is the required boundary for user- or configuration-influenced server destinations.

- **MUST:** Allow only HTTP/HTTPS, reject URL credentials and disallowed ports, normalize internationalized hosts, resolve and validate every address, and connect only to the validated DNS answers.
- **MUST:** Block metadata, loopback, private, link-local, unspecified, multicast, and reserved addresses. Exact operator allowlists may permit private origins but never metadata/link-local classes.
- **MUST:** Revalidate every redirect, cap redirect count, strip credential headers on cross-origin transitions, ignore ambient proxy variables, and enforce connect/read/total-size bounds.
- **MUST NOT:** Validate one hostname and then allow a library to re-resolve it independently. DNS rebinding protections and the pinned resolver must stay coupled.
- **MUST NOT:** Add direct `aiohttp`, `urllib`, SDK URL, webhook, import, font, image, or search requests for untrusted/configurable destinations unless a reviewed adapter preserves equivalent policy.

The canonical provider adapters and web-search paths use the controlled client. Several legacy integrations still call network libraries or provider SDKs directly; their existence is migration debt, not permission for new bypasses.

## Browser security, CSRF, CORS, and redirects

- Next.js applies CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, MIME sniffing protection, referrer policy, permissions policy, DNS-prefetch disablement, and cross-origin opener policy to all routes.
- Safe return navigation accepts only same-origin absolute paths, rejects scheme-relative paths and API/internal destinations, and localizes the validated path.
- Session cookies use `SameSite=Lax`, and the Docker deployment is same-origin behind nginx.
- FastAPI CORS uses an exact `NEXT_PUBLIC_URL` when configured. Without it, standalone development falls back to `*`; this fallback MUST NOT be treated as a reviewed production origin policy.
- **MUST:** Production proxies provide the correct HTTPS scheme, restrict trusted proxy addresses, and set an exact browser origin. TLS/HSTS are external deployment requirements; nginx in this repository does not prove them.
- **MUST NOT:** Widen `connect-src`, script execution, frame policy, CORS, redirects, or remote image/font sources without a threat review and regression tests.

Known gaps:

- Cookie-authenticated mutation routes do not implement a general CSRF token or Origin/Referer middleware. SameSite and same-origin deployment provide partial protection. Any cross-site embedding, broader credentialed CORS, public account lifecycle, or sensitive browser mutation expansion requires explicit CSRF design and tests.
- The current CSP still permits inline scripts/styles for framework/legacy compatibility and broad HTTP(S) image/media/connect destinations. `unsafe-eval` is disabled in production unless the separate unsafe custom-layout flag is explicitly enabled, but nonce/hash CSP and narrower connect/media policy remain future hardening.
- HSTS and TLS termination are not implemented by the repository's nginx configuration.

## Untrusted content and rendering

- Ordinary React content MUST render as text. Markdown HTML sinks MUST use `lib/safe-markdown.ts`, which escapes raw HTML, validates protocols, escapes attributes/code, and adds safe link relations.
- Catalogs MUST contain plain text and reject HTML/script-shaped content. Interpolation values remain text nodes.
- Canonical presentation documents MUST remain declarative. Canonical browser/Konva renderers MUST NOT evaluate HTML, scripts, layout source, `eval`, or `new Function`.
- Legacy generated-slide/custom-layout rendering is a separate high-risk compatibility boundary. Executable custom layouts MUST remain disabled by default at both server and browser gates and MUST NOT be fed by normal-user writable source.
- Uploaded/document/provider content MUST be bounded and validated before rendering. Provider-returned URLs are not automatically trusted asset capability URLs.

## Database and migrations

- All SQL uses parameterized SQLAlchemy/SQLModel operations or static migration SQL. Dynamic identifiers/SQL from request input are forbidden.
- Tenant predicates and authorization occur before mutation; related revision/document/job/outbox state commits atomically.
- Alembic is the only schema evolution mechanism. Migrations MUST be reviewed for locks, destructive operations, default/backfill behavior, downgrade/compatibility, and tenant ownership.
- Migration smoke tests MUST target only empty/disposable PostgreSQL. Backups and rollback/forward-repair plans are required before production changes.
- Startup compatibility stamping exists for recognized legacy databases; extending it requires schema-evidence tests and must never guess across an unknown destructive state.

## Background jobs and retries

- Durable delivery is at least once. Handlers MUST be idempotent, use lease tokens, reject stale workers, revalidate current workspace authority and source revision, and commit effects with durable state correctly.
- Job payloads/results MUST remain within configured size limits and contain IDs/validated data, never secrets or large bytes.
- Attempts MUST be finite (the canonical submission boundary caps them), failures classified, backoff bounded/deterministic enough to test, and terminal work failed/dead-lettered. Provider fallback MUST NOT recursively multiply job retries.
- Cancellation and timeout MUST stop or quarantine late effects. A process-local task MUST NOT be represented as durable or restart-safe.
- Redis is transport, not job truth. Production durable work requires PostgreSQL plus a shared Redis transport and readiness; in-memory operation controls are not a distributed production substitute.

## Object/file storage and uploads

- Legacy `APP_DATA_DIRECTORY` and `TEMP_DIRECTORY` accesses MUST use existing containment/ownership helpers. User filenames never select an arbitrary filesystem path.
- Managed storage keys are private, workspace-scoped implementation details. Asset IDs are the durable API/document identity.
- The local storage adapter MUST retain traversal and symlink defenses. S3 endpoints outside explicit local development MUST use TLS; public buckets are not assumed.
- Presigned/capability URLs MUST be short-lived, method/resource/workspace-bound, and excluded from logs, persistence, analytics, and presentation documents.
- Uploads MUST verify declared/actual size, checksum, MIME, lifecycle state, and ownership. Managed assets remain quarantined until scanning succeeds.
- The deterministic development scanner is explicitly forbidden as a claim of production antivirus. A real production scanner is an unresolved deployment/integration requirement.
- Asset deletion MUST respect references, retention, quarantine, and idempotent worker cleanup. New code MUST NOT delete legacy originals during migration without a separately approved, dry-run-first policy.

## Rate limiting, abuse, and enumeration

- Login rate limiting and `OperationSecurityMiddleware` are the current central controls. Expensive operations MUST register/use the canonical rate/concurrency policy rather than local counters.
- Production distributed admission control SHOULD use the configured Redis backend and trusted-proxy policy. Admin bypass and emergency disabled-operation settings are privileged operator controls and must default safely.
- APIs SHOULD use bounded pagination/list sizes and uniform not-found/credential responses. New public/anonymous endpoints require explicit abuse budgets before exposure.

The repository does not yet implement the roadmap's public signup/recovery/anonymous-conversion abuse controls, commercial quotas, or a universal API rate limit. They remain gaps, not inferred protection.

## Electron and local-runtime security

- Browser windows retain context isolation, sandboxing, disabled renderer Node integration, trusted navigation/window-open policy, and a narrow preload API.
- Every privileged IPC path MUST call the trusted-sender check and validate inputs. Shell, filesystem, download, updater, and process actions require allowlisted operations and contained paths.
- Child-process execution MUST avoid shell interpolation, use bounded output/time/memory/lifecycle helpers, and clean temporary artifacts. Returned/logged failures must be sanitized.
- Downloaded export/browser/native artifacts MUST remain version/checksum pinned and verified before use. The unverified export opt-in must fail closed.

## Dependency and supply-chain handling

- npm and uv lockfiles are authoritative. CI audits high-severity npm and Python dependency findings and generates CycloneDX SBOMs.
- GitHub Actions MUST use full commit SHA pins with minimal permissions and checkout credentials disabled.
- External export, browser, model, and native artifacts MUST use the existing integrity/provenance manifests and fail on checksum mismatch. Unverified models/artifacts remain disabled by default.
- New dependencies require ownership, license/provenance, vulnerability, transitive, platform, and maintenance review. Do not add a runtime dependency for a check that standard-library tooling can perform.

## Production security invariants

Before production exposure, operators and reviewers MUST verify:

- authentication is enabled; bootstrap credentials and signing secrets are strong and persisted safely;
- exact external origins, trusted proxies, HTTPS forwarding, TLS/HSTS, and cookie `Secure` behavior are correct;
- database backups/migrations are rehearsed and PostgreSQL is used where rollout assumptions require locking/distribution;
- distributed operation controls, Redis workers, object storage, provider master key, and real malware scanner exist before enabling their dependent flags;
- workspace, RBAC, service-account, durable-job, asset, and provider flags are enabled only in tested compatible combinations;
- unsafe custom layouts and unverified export/model/artifact flags remain off unless their separate acceptance gates are satisfied;
- secret scan, dependency audits, SBOM/provenance, authorization/tenant tests, and relevant manual abuse tests pass;
- logs/telemetry, retention, incident response, and rollback controls have named operational owners outside this codebase.

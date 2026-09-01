# Implementation Plan: Public Accounts, Verification, Recovery, and Unified Access

- **Feature identifier**: `001-public-account-lifecycle`
- **Sprint**: 10.10
- **Repository branch**: `dev` (no feature branch created or switched)
- **Date**: 2026-09-01
- **Specification**: [spec.md](spec.md)

**Input**: Approved feature specification at `specs/001-public-account-lifecycle/spec.md`

## Summary

Implement Bayanly's public email/password lifecycle by extending the existing FastAPI Users-backed `User`, adaptive password helper, versioned cookie JWT, personal-workspace provisioner, operation controls, job/outbox system, and localized Next.js shell. Registration creates only a time-bounded non-authenticatable pending registration and accepts no password. A one-time verified activation transaction creates the public `User`, persists the token holder's first password, transfers the email claim, and creates/reconciles the deterministic personal workspace and owner membership atomically. Verification/recovery use purpose-bound HMAC-derived opaque tokens with a frozen timestamp-free byte contract, a minimal provider-neutral SMTP notification boundary on the canonical job system, Redis-backed multi-window abuse controls including unified login and authenticated password change, strict same-origin mutations, and additive EN/AR routes/catalogs. Authenticated password change verifies the current credential and atomically rotates the hash plus `auth_version`, signs out every browser session including the caller, and adds no session store.

Existing username login, six-character legacy password acceptance, PBKDF2 hash upgrade, administrator user creation/reset, deployment bootstrap/recovery, cookie name/strategy, owner isolation, workspace rollout defaults, and the absence of `/auth/setup` remain compatible. All public lifecycle capabilities default off and cannot enable in production until schema, Redis, notification worker, sender/origin, key, localization, and security readiness pass.

## Technical Context

- **Language/Version**: Python 3.11; TypeScript 5; React 19.2.6; Next.js 16.2.12
- **Primary Dependencies**: FastAPI >=0.116.1, FastAPI Users >=14.0.1, SQLAlchemy/SQLModel, Alembic, pwdlib/Argon2 through the existing password helper, Redis, Next.js App Router, Cypress; planned direct dependencies are `email-validator` (already locked transitively) and development-only `axe-core`
- **Storage**: One SQL database and SQLModel metadata graph; SQLite development/test compatibility and PostgreSQL production/concurrency evidence; Redis for production operation controls and canonical job transport
- **Testing**: pytest, disposable PostgreSQL migration/integration checks, Redis integration tests, Node's test runner, Cypress component/E2E, ESLint, Next build, localization/canonical generators, root governance/security/architecture checks
- **Target Platform**: Existing self-hosted Docker/same-origin Bayanly deployment, with FastAPI/Next.js and optional canonical workers supervised by current runtime scripts; current Electron auth bypass behavior remains separate
- **Project Type**: Brownfield web application with a FastAPI modular monolith and Next.js App Router frontend
- **Performance Goals**: Public UI acknowledgment/state within 2 seconds at the agreed service target; under healthy controlled delivery, 99% of accepted messages terminal-delivered within 2 minutes; no request waits indefinitely or waits for SMTP
- **Constraints**: Enumeration-resistant responses; no durable credential or `User` before email proof; fixed 72-hour pending-registration lease and 30-day terminal purge ceiling; 24-hour maximum verification TTL; 30-minute maximum reset TTL; frozen 256-bit timestamp-free token derivation; 12–128 characters for first/reset passwords; 60-second resend cooldown and five per 24 hours; distributed login/lifecycle controls; no raw email/token/password/provider content in logs/jobs/audit/public errors; backend authority; no public user without exactly one personal workspace/owner membership
- **Scale/Scope**: One global account namespace across all tenants; horizontally safe API/worker operation through PostgreSQL constraints/locks and Redis controls; eight public lifecycle routes plus the existing login/account surfaces; EN/AR parity only for this sprint

All technical context decisions are resolved.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-evaluated after Phase 1 design.*

| Principle / source | Pre-design gate | Post-design evidence | Result |
| --- | --- | --- | --- |
| I. Brownfield Truth and Preservation | Repository code, tests, migrations, flags, branch/status, and roadmap classification were required before choosing design. | [research.md](research.md) separates **CURRENT IMPLEMENTATION**, **FEATURE-FLAGGED FOUNDATION**, **LEGACY COMPATIBILITY**, and **ROADMAP-ONLY** and preserves the user's untracked specification work. | PASS |
| II. Canonical Architecture and Domain Integrity | The plan must extend current auth, workspace, job/outbox, provider/outbound, and App Router boundaries. | Existing `User`, FastAPI Users helper/JWT, `ensure_personal_workspace`, operation controls, jobs/outbox, and safe-return/i18n helpers remain canonical. New identity/notification modules own only missing domain behavior. | PASS |
| III. Backend Security and Tenant Authority | FastAPI must remain sole identity/authorization/workspace authority; public and cross-tenant errors must resist enumeration. | Pending submissions are non-user/no-credential records; verified activation creates the user/hash/claim/workspace atomically; pending login is generic; unified login/lifecycle controls are distributed and backend-owned. | PASS |
| IV. Controlled External and Durable Effects | Email must not create a second provider executor, queue, retry system, or secret-bearing payload. | A minimal SMTP transport sits behind `modules/notifications`; canonical jobs gain a narrowly registered system authority and notification queue. Payload is `{notificationId}`; canonical jobs alone retry. | PASS |
| V. Reversible State and Contract Evolution | Use one Alembic graph, safe defaults, compatibility windows, data minimization, and operational rollback. | Two linear expand/backfill/enforce revisions follow `d4f6a8c0e2b3`; pending claims have a fixed reclaim/redaction/purge path; public flags default off; collision checks refuse merge; rollback retains required state, continues cleanup, and drains accepted work. | PASS |
| VI. Bilingual Product Integrity | Every account and email state needs equivalent EN/AR, RTL/LTR, accessible/responsive behavior without canvas impact. | Route/catalog/template contracts cover every state, 320px/200% zoom/keyboard/axe/manual review, bidi isolation, and explicitly exclude presentation geometry. | PASS |
| VII. Evidence and Honest Quality Gates | Requirements must map to deterministic tests and known gaps must remain visible. | [quickstart.md](quickstart.md), the test strategy, and criterion-level task traceability separate automated gates from controlled/human artifacts for SC-001, SC-006, SC-010, and BA-004; they also cover pre-hijack races, reclamation, multi-instance login, token vectors, password-change races/session invalidation, OpenAPI, E2E, privacy, and migration. No human or delivery result is claimed before measurement. | PASS |
| VIII. Repository and Supply-Chain Stewardship | Dependencies and generated contracts must use owning manifests/generators; Git history must remain untouched. | Only two justified direct dependencies are planned and must be locked/audited. OpenAPI/localization are generator/check owned. No branch/history action is part of this plan. | PASS |

### Gate Outcome

The original pre-design gate found no architecture exception. Security clarification corrected credential pre-hijacking, indefinite pending retention, process-local login authority, and timestamp-dependent token derivation. The pre-implementation remediation then added the previously unowned authenticated password-change lifecycle, separated public capabilities from authenticated account state, moved lifecycle eligibility repositories before notification workers, made story-local EN/AR ownership explicit, separated foundation configuration from final readiness, and added honest controlled/human acceptance evidence. The reconciled design passes the post-remediation gate without a competing queue, user, session, limiter, email-catalog, or tenant authority. No Complexity Tracking exception is required.

## Project Structure

### Planning Artifacts (This Feature)

```text
specs/001-public-account-lifecycle/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- http-api.md
|   |-- notification-provider.md
|   `-- frontend-routes.md
`-- checklists/
    `-- requirements.md
```

`tasks.md` is present and is reconciled after this remediation so its ordering and criterion-level traceability match the approved design.

### Planned Backend Source Ownership

```text
servers/fastapi/
|-- api/
|   |-- main.py                              # production readiness/CORS/middleware wiring
|   |-- middlewares.py                       # explicit public auth paths; no auth authority change
|   |-- operation_security.py                # multi-window/scoped central policies
|   |-- runtime_capabilities.py              # authenticated additive capabilities if retained
|   `-- v1/
|       |-- auth/
|       |   |-- router.py                    # thin lifecycle/session transport adapters
|       |   |-- schemas.py                   # bounded versioned request/response models
|       |   |-- users.py                     # existing password/JWT foundation, additive serialization
|       |   |-- principal.py                 # display identifier compatibility
|       |   |-- bootstrap.py                 # bootstrap identifier claim synchronization
|       |   `-- config.py                    # existing cookie plus reviewed key/origin helpers
|       `-- admin/router.py                  # calls shared identity create/reset policy
|-- models/sql/user.py                       # existing User, additive lifecycle/email fields
|-- modules/
|   |-- identity/
|   |   |-- domain/                          # states, normalization, password/token/redirect rules
|   |   |-- application/                     # pending registration, activation, login, recovery, passwords, sessions
|   |   |-- persistence/                     # pending claims, identifiers, challenges, lifecycle audit
|   |   |-- workers/                         # canonical bounded pending reconciliation handler
|   |   |-- resources/                       # reviewed common-password digest data
|   |   `-- observability.py                 # finite allowlisted metrics/events
|   |-- notifications/
|   |   |-- domain/                          # transport request/outcome contracts
|   |   |-- application/                     # delivery revalidation/rendering
|   |   |-- adapters/                        # SMTP + in-memory capture
|   |   |-- persistence/                     # delivery state
|   |   |-- templates/                       # canonical EN/AR email catalogs/rendering
|   |   `-- workers/                         # registered canonical notification handler
|   |-- jobs/                                # system authority + notification queue extension
|   `-- workspaces/                          # reuse personal workspace/audit/invitation boundaries
|-- alembic/versions/                        # two linear Sprint 10.10 revisions
|-- migrations.py                            # new head/schema recognition
|-- scripts/
|   `-- check_account_identity_collisions.py # privacy-safe shadow/preflight check
|-- tests/                                   # unit/integration/security/migration evidence
|-- pyproject.toml                           # direct email-validator declaration
|-- uv.lock                                  # owning lock update
`-- openai_spec.json                         # generated only after API implementation
```

### Planned Frontend Source Ownership

```text
servers/nextjs/
|-- app/
|   |-- page.tsx                             # existing unified login composition
|   |-- layout.tsx                           # retains locale shell; token-route analytics policy
|   |-- MixpanelInitializer.tsx              # analytics-dark token routes
|   |-- (public-account)/
|   |   |-- layout.tsx
|   |   |-- loading.tsx
|   |   |-- error.tsx
|   |   |-- register/page.tsx
|   |   |-- check-email/page.tsx
|   |   |-- verification-required/page.tsx
|   |   |-- resend-verification/page.tsx
|   |   |-- verify/page.tsx
|   |   |-- forgot-password/page.tsx
|   |   |-- reset-password/page.tsx
|   |   `-- recovery-complete/page.tsx
|   `-- (presentation-generator)/(dashboard)/account/
|       `-- AccountPage.tsx                  # identity/recovery/locale/session integration
|-- features/account-lifecycle/
|   |-- api.ts
|   |-- types.ts
|   |-- error-state.ts
|   |-- return-target.ts
|   |-- token-handoff.ts
|   `-- components/                          # shared scaffold/forms/status components
|-- components/Auth/AuthGate.tsx             # compatibility wrapper/refactor to shared sign-in
|-- components/product-shell/SessionMonitor.tsx
|-- lib/product-navigation.ts                # hardened existing safe return helper
|-- messages/en.json
|-- messages/ar.json
|-- tests/                                   # unit/privacy/route/catalog tests
|-- cypress/component/account-lifecycle.cy.tsx
|-- cypress/e2e/account-lifecycle.cy.ts
|-- package.json                             # direct dev axe-core declaration
`-- package-lock.json                        # owning lock update
```

**Structure decision**: Use the repository's current FastAPI modular-monolith and Next.js App Router layout. New domain logic belongs in `modules/identity` and `modules/notifications`; current auth/admin routes remain adapters, and current `User`, JWT cookie, workspace, jobs, and localization structures remain authoritative.

## Design and Implementation Sequence

This section defines dependency order and ownership, not executable `tasks.md` work.

### Phase A — Expand Schema and Establish Compatibility Seams

1. Add the expand/backfill Alembic revision and ORM imports for verified user fields, pending-registration retention, reservable identifier claims, subject-bound challenges, per-challenge delivery generations, invitation identity classification, and system-scoped job rows.
2. Freeze one normalization implementation shared by migration/runtime tests; add the privacy-safe collision checker and abort behavior.
3. Backfill existing users, identifiers, jobs, and invitations while preserving all current data/authority.
4. Make serializers/principal/workspace naming tolerate nullable activated-public username, and make login resolvers ignore pending-owned claims, before any public flag can enable.
5. Deploy/read the additive state with all public capabilities off, then run the shadow collision gate.

### Phase B — Identity Domain, Password Policy, and Challenges

1. Add identity enums/models/repository helpers, the global identifier resolver, and the minimum shared challenge/subject/lease eligibility read contract needed by notification workers before any worker integration.
2. Centralize email normalization and the 12–128 first/reset local common-password policy while preserving legacy login acceptance/hash upgrade; registration has no password input.
3. Add the versioned challenge key ring, exact `ba1` wire parser, frozen timestamp-free binary derivation, golden vectors, verifier storage, expiry/replay/generation rules, same-token redelivery, and emergency revocation behavior.
4. Implement application-owned pending registration, fixed-lease lazy reclamation, resend/redelivery, verification user/credential/claim/workspace activation, forgot/reset, authenticated password change, admin create/reset integration, global session revoke, and deactivation invariants with explicit transaction ownership and lock order.
5. Extend bootstrap rename/provisioning to synchronize the primary username claim under its existing lock.

### Phase C — Central Abuse, CSRF, Redirect, and Observability Controls

1. Extend operation security to multi-window/outcome policies and privacy-safe IP/identity/combined/challenge scopes, with Redis fail-closed production behavior.
2. Move login admission and five-failure semantics into the canonical distributed controller, add the identifier-wide failure window, retain dummy password work and safe `Retry-After`, prove multi-instance behavior, then remove the process-local limiter/request calls before public email login can enable.
3. Register route/application policies for signup, resend, verification, forgot/reset, and challenge failures without copying or retaining a second limiter.
4. Add the strict JSON/header/Origin/Fetch-Metadata auth mutation policy and exact-origin production readiness.
5. Add backend return-target resolution and harden the existing frontend helper against loops, internal paths, encoding tricks, and fragments.
6. Add append-only lifecycle audit, aggregate-only abandoned cleanup metrics, allowlisted telemetry, Sentry body/header/query filtering, and job payload secret-key hardening.

### Phase D — Canonical Notification Delivery

1. Add the constrained system authority and notification queue inside `modules/jobs`, preserving all existing workspace-job defaults, APIs, and authority tests; register both notification delivery and singleton bounded pending reconciliation.
2. Add notification persistence, the single canonical owner of deterministic EN/AR email catalogs/rendering, the provider-neutral transport protocol, in-memory test adapter, and reviewed async-safe SMTP adapter.
3. Register `account.notification.deliver.v1` with `{notificationId}`, finite job retry, deterministic per-delivery Message-ID, exact token golden-vector reconstruction, pre-effect subject/lease revalidation through the shared Phase B eligibility repository, and ambiguous-terminal handling.
4. Register hourly `account.pending.reconcile.v1` with a non-identifying singleton/bounded-batch contract that calls the same identity reclamation transition as lazy paths and never selects users.
5. Wire challenge/delivery/job creation into registration/resend/forgot transactions so accepted state and durable work commit together; resend of a current verification challenge creates a delivery generation, not a token generation.
6. Extend worker/startup/readiness/reconciliation-backlog configuration and health without adding a second worker, scheduler authority, or queue abstraction.

### Phase E — HTTP Contracts and Compatibility Cutover

1. Expose the public unauthenticated lifecycle-capability projection from the shared foundation before any public UI depends on it; disclose only product-availability booleans, never dependency or account state.
2. Add bounded lifecycle schemas/routes—including authenticated password change—and explicit middleware allowlisting while keeping `/auth/setup` absent and `/auth/verify` dedicated to session verification.
3. Extend login to user-owned identifier resolution with `username` request alias compatibility, pending-owned claims routed through generic dummy-work invalid credentials, canonical distributed failure recording, and backend return path.
4. Extend authenticated status/serialization with account lifecycle/display/workspace context and retain all existing fields for legacy/admin clients without taking ownership of the already-available public capability projection.
5. Apply same-origin policy to login/logout/lifecycle/locale/password/session mutations and preserve the existing cookie attributes.
6. Generate/check the canonical OpenAPI artifact through `scripts/generate_openapi_spec.py`.

### Phase F — Localized Frontend Lifecycle

1. Refactor the current AuthGate into the shared account-lifecycle feature while keeping `/` the one login page and the current cookie/status client.
2. Add the public route group, localized `loading.tsx`/`error.tsx` boundaries, and every success/loading/error/rate/delivery state from the frontend contract; registration collects email/locale only and verification owns first-password setup.
3. Implement analytics-dark fragment handoff, immediate history scrub, no-store/no-referrer token pages, and memory-only POST submission.
4. Make each story add its matching EN/AR UI keys with the UI it creates; final convergence owns parity/terminology/unused-key/RTL checks only. Backend email catalogs remain solely owned by the notification foundation.
5. Extend `/account` with backend-issued account identifier, email/admin-managed recovery state, locale, authenticated password change, current logout, and revoke-all; a successful password change clears client-protected state and returns to localized sign-in. Keep `/settings` and presentation geometry unchanged.

### Phase G — Enforce, Validate, and Roll Out

1. After shadow evidence, apply the constraint revision and run SQLite plus disposable PostgreSQL migration, reservable-identifier, fixed-retention, uniqueness, and concurrency coverage.
2. Complete attacker/victim pre-hijack races, reclamation, multi-instance login, password-change generation races, golden/cross-database token vectors, backend, notification/job, frontend, security, privacy, accessibility, EN/AR, and compatibility tests described below and in [quickstart.md](quickstart.md).
3. Rehearse expand/backfill/enforce, pre-data downgrade, operational rollback, key rotation, Redis/provider outage, SMTP ambiguous handoff, and workspace-provisioning failure.
4. Produce the separate controlled/human SC-001, SC-006, SC-010, and BA-004 artifacts only after the integrated implementation and automated gates; do not infer these outcomes from unit/Cypress results.
5. Enable in controlled environments only after distributed-login cutover, reconciliation, token-vector readiness, and every automated plus controlled/human acceptance artifact passes; then notification infrastructure, staff/staging challenge issuance, recovery/verification evidence, and finally public signup. Anonymous production traffic is last.
6. Keep destructive cleanup, username retirement, session inventory, email change, and permanent vendor choices outside Sprint 10.10.

## API and Transaction Decisions

The exact planning contract is [contracts/http-api.md](contracts/http-api.md). Key boundaries are:

- registration 202 is constant-shape, accepts no password, and creates only a fixed-lease pending registration/claim/challenge/delivery with no `User`, cookie, or workspace;
- `/auth/email-verification/consume` avoids conflict with existing session `/auth/verify`;
- first successful verification accepts the first password and atomically creates the user/hash, transfers the claim, activates/provisions, consumes the token, and may issue the existing cookie;
- reset atomically changes hash, consumes/revokes reset challenges, rotates `auth_version`, and requires sign-in;
- authenticated password change verifies the current password, rejects the current value as the replacement, atomically replaces the hash, revokes reset challenges, rotates `auth_version`, deletes the caller cookie, and requires sign-in without issuing a replacement session;
- login accepts preferred `identifier` or compatible `username`, resolves only user-owned claims, treats pending claims generically, and uses only canonical distributed abuse controls;
- public status capabilities are a shared foundation available before public pages; authenticated status later adds account-owned lifecycle/display/workspace context;
- logout revokes only current cookie; revoke-all rotates the shared version;
- return paths are backend-resolved and capability-authorized.

## Database and Migration Strategy

The detailed schema is [data-model.md](data-model.md). The migration is one linear two-revision path from current head `d4f6a8c0e2b3`:

- **Expand/backfill** adds nullable verified-user lifecycle/email state, pending registrations/retention, reservable identifier ownership, subject-bound purpose challenges, per-challenge notification delivery generations, lifecycle audit, system-scoped notification/reconciliation jobs, and invitation identity fields; backfills current data and refuses ambiguous case-fold collisions.
- **Shadow/reconcile** runs with all public flags off and reports safe counts/categories/user UUIDs only; no automatic merge/rename/email invention.
- **Enforce** adds user/pending state, identifier-owner exclusivity/transfer, fixed-retention/redaction, subject-current, per-delivery-generation, unique/partial-unique constraints, makes username nullable for activated public accounts, and preserves one graph head.

Existing account IDs, usernames, hashes, activity, roles, locales, session versions, ownership, workspaces, memberships, and admin bootstrap are preserved. Normal current users become `ADMIN_PROVISIONED`; primary/historical superusers become `GRANDFATHERED`; all have `email_state=UNSET` and no false email claim.

Physical downgrade refuses after public pending/user lifecycle or system-job data exists. Production rollback is flag/application rollback with reclamation/redaction still enabled, never destructive schema reversal.

## Token and Session Strategy

- Exact `ba1.<ev|pr>.<kid>.<22-char locator>.<43-char secret>` wire form with 32-byte/256-bit HMAC-SHA256 output and a random UUID locator.
- Dedicated versioned key ring; no JWT/invitation/provider secret reuse.
- Frozen HMAC context is domain+NUL, one-byte format/purpose, length-prefixed ASCII key ID, RFC challenge UUID bytes, one-byte subject kind, RFC pending/user UUID bytes, and unsigned 64-bit big-endian binding generation. `issued_at`, expiry, issue generation, locale, email, timezone, JSON, and database strings are excluded.
- Persist only subject/context fields, key version, and lowercase-hex SHA-256 verifier of the ASCII token; raw/encrypted raw token is never stored.
- Verification bound to live pending registration + claim generation; <=24 hours and <= fixed 72-hour `reclaim_after`.
- Reset bound to account + issuance-time `auth_version`; <=30 minutes.
- One current challenge per subject/purpose, same-token redelivery while live, row-locked one-time consumption, expiry/reclamation/success invalidation, five-failure revocation, constant-time verifier comparison.
- Verification/reset golden vectors in [research.md](research.md) must match independent-process and SQLite/PostgreSQL round trips exactly.
- Previous key versions retained beyond maximum token TTL plus clock skew.
- Verification first winner creates the user/credential/workspace and may issue the existing cookie; replay may not issue a cookie or change the password.
- Reset/admin reset/authenticated password change/revoke-all/deactivation rotate `auth_version`; reset and password change do not auto-login, and password change deletes the caller cookie.

## Email and Durable-Work Strategy

The exact boundary is [contracts/notification-provider.md](contracts/notification-provider.md). `modules/notifications` supplies a minimal SMTP/in-memory transport and deterministic EN/AR transactional templates; it is independent of the AI provider registry. `modules/jobs` gains an allowlisted system lifecycle authority and notification queue because pending registrations have no workspace. Notification jobs contain only the notification UUID and own retry/backoff/dead-letter; an hourly non-identifying reconciliation job owns bounded privacy cleanup. Delivery rows contain only safe status/category/timing data.

Provider calls are bounded and async-safe. Known pre-acceptance transient failures retry up to three canonical attempts; permanent failures terminate; ambiguous post-dispatch outcomes become terminal unknown rather than blind resend. An allowed resend creates a new delivery/Message-ID for the same still-current verification token; only expiry creates a new challenge. SMTP duplicate physical copies cannot be ruled out after ambiguous handoff, but they share one effective challenge.

## Rate-Limit and Abuse Strategy

Only the central operation-control boundary is extended:

- login admission retains 10 submissions per trusted IP per minute with burst 5 plus the explicit global ceiling;
- login failures allow no more than 5 per privacy-safe IP/identifier scope per 5 minutes and 10 per privacy-safe identifier per 15 minutes, with matching failure scopes cleared only after successful credential verification;
- 5 registration/recovery requests per IP per 15 minutes;
- 3 per privacy-safe normalized-identity HMAC per hour;
- 10 token validations per IP per 15 minutes;
- 5 failed validations per challenge, enforced by central admission plus durable atomic count;
- resend no more than once per 60 seconds and five per rolling 24 hours, plus IP/global controls;
- authenticated password change no more than five failed-current-password attempts per safe user/IP pair per 15 minutes, plus IP/global controls;
- finite global/concurrency ceilings and emergency operation disables.

Production requires shared Redis and fails closed for login and lifecycle operations. Raw username/email/locator never becomes a control key or log label; identifier and combined scopes use purpose-separated HMACs. Denial uses the greatest applicable bounded `Retry-After` without naming scope/state. The old process-local login limiter may exist only during a flags-off rolling compatibility deployment and is removed from the request path before public email login/readiness; it is never the final authority. Frontend timers are UX only.

## Frontend and Localization Strategy

The route/state contract is [contracts/frontend-routes.md](contracts/frontend-routes.md). Public pages live outside the protected presentation layout and reuse the current locale proxy, account shell styling, API URL/timeouts, status/session cookie, error mapping, and safe navigation. `/register` collects email/locale only; `/verify` scrubs the token then owns the first-password form and atomic activation submission. `/` remains login and never reveals a pending claim. `/account` gains identity/recovery/session actions plus current-password-verified password change; a successful change signs the caller out with every other browser session. `/settings` remains presentation preferences.

Every story owns matching EN LTR and AR RTL catalog entries when its UI is introduced. Every state has equivalent variables, layout, keyboard, focus, accessible announcement, reduced-motion, 320px, 200%-zoom, loading, timeout, success, failure, invalid/expired/used, duplicate-submit, delivery-delayed, and rate-limit behavior. Public route-group loading/error boundaries render safe localized recovery without becoming authorization. Email values use bidi isolation. Token routes are analytics-dark and no presentation renderer/canvas file changes.

## Test Strategy

### Backend Unit and Integration

- Registration/pre-hijack: email/locale only, no User/hash/session/workspace, attacker-before-victim, victim repeat, attacker-after-victim, concurrent registration, same-token resend, expired-generation replacement, and duplicate/active/disabled/primary/alias generic responses.
- Normalization/uniqueness: Unicode/IDNA/control cases, plus/dot preservation, case-fold username/email collisions, pending-to-user claim transfer, stale claim reuse, SQLite constraints, and PostgreSQL concurrent insert/activation winner behavior.
- Pending retention: fixed non-extendable 72-hour lease, challenge expiry cap, lazy/hourly equivalence, email redaction/claim release, 30-day terminal purge, terminal-job precondition, verification/reclaim race, SQLite serialized-CAS behavior, PostgreSQL row locks, and proof no actual user origin/state is selectable.
- Verification/first credential: exact wire parser; verification/reset golden vectors; independent-process and SQLite/PostgreSQL reconstruction; no timestamp context; policy/hash only with valid token; malformed/wrong-purpose/revoked/reused tokens; expiry replacement; five failures; concurrent different-password consume; user/claim/workspace/cookie only for winner.
- Recovery/reset: eligibility matrix, generic forgot response, 30-minute expiry, concurrent issuance/current generation, reused/concurrent consume, password/hash change, sibling revocation, `auth_version` invalidation, old/new password behavior.
- Sessions/accounts: pending-claim/absent/disabled/wrong-password generic login with dummy/real work; authenticated password change correct/incorrect/unchanged/policy/disabled/rate/concurrent-generation cases; revoke-all; admin reset; legacy six-character login; PBKDF2 upgrade; cookie attributes; status compatibility; primary admin exclusion; `/auth/setup` permanent absence.
- Workspace/tenant: user/credential/claim/workspace activation rollback on injected insertion/provisioning/audit failure, retry same token, exactly one deterministic workspace/owner membership, no pre-activation authority, invitation email/legacy matching with separate token, no auto-accept, cross-tenant not-found/denial.
- Notification/jobs: system authority cannot be public or used by unregistered operations; payload secret rejection; pending/user/lease revalidation; same-challenge delivery generations; exact token reconstruction; deterministic Message-ID; safe retry/dead letter; ambiguous terminal; stale/reclaimed suppression; bounded reconciliation; fake SMTP failure/recovery; no second retry/scheduler.
- Abuse/CSRF/redirect: shared Redis multi-instance login admission/failure/clear and lifecycle windows, legacy local-limiter removal assertion, privacy-safe keys, generic maximum `Retry-After`, cooldown/daily ceilings, exact Origin/JSON/header/Fetch-Metadata rules, wildcard readiness failure, malicious return paths and backend role/capability authorization.
- Privacy/observability: canary email/password/token/cookie/body/provider response absent from logs, Sentry events, metrics, audit, job payload/result/events, public errors, and generated OpenAPI examples.

### Migration

- Single-head check and current-head recognition.
- SQLite upgrade/backfill/constraints/pre-data downgrade/idempotency.
- Disposable PostgreSQL full-chain upgrade, collision refusal, pending/user owner-exclusivity and claim transfer, fixed-retention/redaction constraints, partial unique indexes, nullable system-job scope constraints, concurrent registration/verification/reclaim behavior, token round-trip reconstruction, and downgrade refusal after lifecycle data.
- SQLite full-chain and state-machine evidence proves serialized-writer compare-and-set/uniqueness produces the same terminal outcomes and exact token reconstruction without relying on timestamp precision.
- Fixtures prove preservation of every current account/auth/owner/workspace field and both workspace rollout modes.

### Frontend

- Node tests for contract types, stable error-to-state mapping, capability gating, token parser/secrecy, safe-return hardening, route placement, account/settings separation, and EN/AR key/variable parity.
- Privacy tests prove Mixpanel/page views do not initialize on token handoff routes and source code does not place tokens in search params/storage/console/telemetry/DOM.
- Cypress component tests cover every EN/AR form/state, labels/errors/live regions/focus/keyboard, disabled/loading/timeout/duplicate behavior, bidi isolation, RTL/LTR, reduced motion, 320px, 200% zoom, and automated axe checks.
- Cypress product E2E uses a controlled fake mailbox/API for EN/AR email-only registration → token scrub → first-password activation → Dashboard, generic pending login, resend without link rotation, stale-registration recovery, verification expiry/replay, forgot/reset/completion, old-session expiry, malicious/safe redirects, network/provider failures, and no canvas geometry change.

### Controlled and Human Acceptance

Automated suites remain required but do not establish human usability, language quality, reading order, assistive-technology behavior, controlled notification latency, or production-build usable-state timing by themselves. After the converged build and automated gates, the acceptance owner records:

- `artifacts/account-lifecycle/acceptance/sc-001-usability-matrix.csv` and `sc-001-usability-summary.json`: at least 20 independent participants per locale, privacy-safe participant IDs, both measured journey durations, per-locale 95% calculations, environment/build, owner, and result;
- `artifacts/account-lifecycle/acceptance/sc-006-delivery-run.json`: at least 100 accepted controlled fake/staging messages through the canonical worker path, accepted/delivered timestamps or safe aggregates, the 99%/120-second calculation, retry/redelivery counts, duplicate-effective-generation count, environment/build, owner, and result;
- `artifacts/account-lifecycle/acceptance/sc-010-ui-timing.json`: at least 20 cold-start production-build measurements per required public route/state family and locale, agreed service profile, precise usable-state definition, every duration, threshold result, build, and owner; and
- `artifacts/account-lifecycle/acceptance/ba-004-human-bilingual-review.md`: recorded English, fluent-Arabic, and accessibility reviewer roles with per-locale wording/meaning, bidi, RTL/LTR reading order, keyboard, focus, semantics, and assistive-technology findings and disposition.

These artifacts contain no real address, password, cookie, bearer token/link, rendered message body, provider reply, or participant personal data. They are evidence to be produced during implementation validation, not results asserted by this plan.

### Mandatory Repository Gates

Run the exact root, FastAPI, Next.js, migration, localization, Cypress, security, and generated-contract checks from `TESTING.md`. No real SMTP/paid provider/production secret or production database is used. Skips/failures are reported exactly.

## Requirement Traceability

| Requirement(s) | Planned design/evidence |
| --- | --- |
| FR-001 | Email/locale-only registration transaction creates a fixed-lease pending registration, not a User/password/session/workspace. |
| FR-002 | Central email normalizer and frozen migration fixtures. |
| FR-003 | Unique global reservable identifier registry, pending→user atomic transfer, normalized-email index, and SQLite/PostgreSQL races. |
| FR-004–005 | Constant 202; live repeat re-delivers the same token; no password/User, link rotation, or retention extension. |
| FR-006–008 | Pending registration is distinct from User/account/email state, has no authority, and has a fixed 72-hour reclaim lease. |
| FR-009–010 | Row-locked token+password user/hash/claim/workspace/audit transaction with complete injected rollback/retry. |
| FR-011–014 | Dedicated key ring, exact `ba1` wire/canonical bytes, no timestamp serialization, digest only, TTL/lease caps, same-token redelivery, one-time consume. |
| FR-015 | Persisted resend eligibility, same-token delivery generations, no lease extension, and central 60-second/five-per-day budgets. |
| FR-016–018 | Minimal notification transport; system canonical notification/reconciliation jobs; safe IDs; bounded SMTP; deterministic minimal EN/AR templates. |
| FR-019–020 | Fragment handoff, analytics suppression, history scrub, no-store/no-referrer, memory-only POST, all localized verification states. |
| FR-021–023 | User-owned identifier login, compatible username field, generic dummy-work pending/absent failures, distributed admission, unchanged cookie/JWT checks. |
| FR-024–025 | First password only with valid verification token; existing adaptive helper/legacy upgrade; centralized 12–128 first/reset/admin policy. |
| FR-026–030 | Generic forgot contract; purpose/auth-version reset challenge; 30-minute expiry; atomic reset/session rotation; concurrent generation/consume tests. |
| FR-031–033 | Current logout semantics; reset/admin reset/authenticated password change/revoke-all/deactivation version rotation; primary administrator remains deployment-only. |
| FR-034–035 | Canonical multi-window Redis login/lifecycle controls for IP, identity/combined HMAC, challenge, and global scopes; local limiter removed. |
| FR-036 | Backend JSON/header/exact-Origin/Fetch-Metadata enforcement and direct cross-origin tests. |
| FR-037 | Hardened client pre-filter plus backend return-path authorization and Dashboard fallback. |
| FR-038–040 | Stable schemas/codes; allowlisted audit/telemetry; Sentry/log/job/public-response redaction; aggregate-only abandoned cleanup and no anonymous identity ledger. |
| FR-041–043 | Global identifiers; personal-workspace-only activation; verified-email invitation match plus separate token; backend ignores/rejects authority fields and retains tenant predicates. |
| FR-044–049 | Public route contract; canonical UI/email EN/AR catalogs; RTL/logical layout/bidi; bounded async states; keyboard/a11y/responsive/zoom/reduced-motion; no canvas change. |
| FR-050–052 | Two linear Alembic revisions, pending/retention/reservable-claim and verified-user lifecycle tables, conservative backfill, collision refusal, SQLite/PostgreSQL evidence. |
| FR-053–055 | Four default-off flags, cleanup independent of issuance, login/reconciliation readiness, accepted-token drain, non-destructive rollback. |
| FR-056 | Additive versioned API schemas, compatibility alias, `/auth/verify` preservation, generated OpenAPI workflow. |
| FR-057 | Pre-hijack, reclaim, multi-instance login, golden/cross-database token, and full strategy above plus [quickstart.md](quickstart.md). |
| FR-058 | Finite privacy-safe request/rate/challenge/delivery/workspace/session metrics and lifecycle events. |
| FR-059–060 | Public capability foundation plus additive authenticated account/status context and localized `/account` identity/recovery/locale/password/logout/revoke-all UX. |
| FR-061 | Same-origin current-password-verified atomic password change, reset-challenge revocation, `auth_version` race handling, caller-cookie deletion, and sign-in-again contract. |
| SR-001–014 | Constitution/security check, no credential before proof, fixed pending minimization, canonical token bytes, distributed login, session/CSRF/privacy/tenant/migration/flag designs, and adversarial tests. |
| BA-001–003, BA-005–008 | Story-owned identical catalogs/templates; `/en` and `/ar`; locale preservation; keyboard/focus; 320px/200%; state parity; canvas exclusion. |
| BA-004 | Automated bidi/parity checks plus the separate recorded human bilingual/accessibility review artifact; automated evidence alone cannot pass it. |
| CR-001–008 | Username and six-character login compatibility, hash upgrades, cookie/JWT/auth_version routes, bootstrap/RESET_AUTH, admin/workspace preservation, default-off foundations, no stock FastAPI Users routes. |
| SC-001 | Controlled human usability matrix and summary, at least 20 independent participants per locale, with the existing 95%/two-minute/five-minute thresholds measured separately. |
| SC-002–005 | Automated normal-only/pre-hijack, enumeration/distributed-login, token/race/replay, and reset/admin-reset/password-change/deactivation session-revocation evidence. |
| SC-006 | Controlled 100-message canonical-worker delivery artifact proving at least 99% delivered within 120 seconds and zero duplicate effective challenge generations. |
| SC-007–009 | Automated atomic user/workspace, retention/migration, bilingual route/catalog/accessibility evidence plus required human review where BA-004 applies. |
| SC-010 | Controlled production-build timing artifact with at least 20 cold-start samples per route/state family and locale, all within the existing two-second threshold. |
| SC-011 | Automated/static/runtime secrecy tests plus manual sampled security review. |

## Rollout and Rollback

### Rollout Sequence

1. Merge/deploy expand/backfill schema and compatible reads with all lifecycle flags off.
2. Run privacy-safe collision/reconciliation and migration checks on supported databases.
3. Deploy canonical multi-window login/lifecycle control, remove the local login request path after all nodes cut over, and prove shared-Redis failure/`Retry-After` behavior; keep public issuance off.
4. Deploy exact-origin/CSRF, pending lazy/hourly reclamation, system jobs, notification delivery, canonical token/golden-vector key readiness, and email templates; keep public issuance off.
5. Exercise attacker/victim races, 72-hour reclamation, authenticated password-change races/session invalidation, token cross-database vectors, fake/local SMTP, and staff/staging accounts in EN/AR, including Redis/provider/workspace failures and key rotation.
6. Apply enforcement revision and verify one graph head, OpenAPI, security, accessibility, and full automated quality gates.
7. Produce and review the SC-001, SC-006, SC-010, and BA-004 controlled/human evidence artifacts without real customer data or secrets.
8. Enable `notification_delivery`, then verification/recovery issuance for a controlled environment, then `public_signup` only after automated and controlled/human release evidence plus sender/domain/privacy/legal approval.

### Ordinary Rollback

- Disable new signup, resend, and forgot issuance first.
- Keep existing active login/admin provisioning and username compatibility available.
- Keep notification workers and challenge consumption available long enough for accepted uncompromised work to finish/expire.
- Keep lazy/hourly pending reclamation and terminal redaction/purge enabled; public issuance flags do not control privacy cleanup.
- Retain schema, actual users/user-owned identifiers, accepted challenge/delivery state, audit, workspace, and membership data while allowing the specified stale pending-claim release, PII redaction, and terminal purge.
- Preserve previous challenge key versions through their TTL window.
- Use the separate emergency consumption disable/revocation only for an active security incident.
- Do not downgrade/drop schema after public data exists and never restore `/auth/setup`.

## Technical Risks and Mitigations

| Risk | Mitigation / release gate |
| --- | --- |
| Pending-registration persistence could accidentally become a second account model. | No password/session/role/workspace fields or auth adapter; login accepts only user-owned claims; activation creates the canonical User once; architecture/security tests forbid pending authority. |
| Re-registration/resend could reintroduce pre-hijack or link-invalidation races. | Registration has no password; unexpired challenge is re-delivered unchanged; fixed lock order/unique claim; concurrent different-password consume has one atomic winner; full attacker/victim matrix gates release. |
| Cleanup cadence could fail or race verification. | Identifier reuse uses lazy reconciliation and never depends on schedule; hourly canonical job is privacy maintenance; fixed 72-hour lease/expiry cap, claim-first lock/CAS, bounded backlog readiness, and 30-day terminal purge evidence. |
| Mixed-version login nodes could enforce different failure counters. | Public email flags remain off; central multi-window code is deployed/tested first; all nodes cut over; local limiter path is removed; readiness requires two-instance Redis tests before enablement. |
| Token reconstruction could diverge across database timestamp formats. | `issued_at` is excluded; exact byte/wire contract and two golden vectors; independent-process plus SQLite/PostgreSQL round-trip gates; no fallback serialization. |
| Canonical jobs are workspace-only today. | Explicit system lifecycle authority, nullable scope constraints, registry allowlist, no public API, pre-effect revalidation, focused migration/security tests. |
| Workspace audit cannot represent pending registrations. | Purpose-limited append-only identity audit with no arbitrary metadata; workspace audit remains unchanged for tenant events. |
| SMTP cannot atomically prove exactly-once delivery. | Deterministic Message-ID/effective token generation, bounded safe-pre-acceptance retry, ambiguous terminal state, user resend after cooldown, documented staging observation. |
| Token key rotation can invalidate links. | Versioned key ring, retain old versions for TTL+skew, readiness/preflight and emergency-only removal semantics. |
| Current wildcard CORS/missing Origin policy is unsafe for public lifecycle. | Exact HTTPS origin, strict JSON/custom header/Origin/Fetch-Metadata, production readiness fail-closed and direct cross-origin tests. |
| Identifier backfill may find case-fold collisions allowed by current DB uniqueness. | Shadow checker and migration abort with safe IDs/counts; no merge/rename; owner reconciliation before enforcement. |
| Nullable public username touches current serializers/workspace naming. | Compatibility serializers/principal helper deployed before flags; neutral personal-workspace name; full current/admin fixture tests. |
| Enumeration can persist through timing despite identical bodies. | Equivalent password work, lookup-independent control order, asynchronous provider, controlled repeated timing distributions and release review. |
| Global analytics currently initializes on all routes. | Route-level analytics suppression before token read, fragment scrub, no-referrer/no-store, static/runtime privacy tests. |
| Common-password data or new accessibility tooling introduces supply-chain/provenance risk. | Reviewed digest-only local dataset with documented provenance; one explicit locked/audited `axe-core` dev dependency; no online password service. |
| Public flags could be enabled in a partial deployment. | Backend service checks plus startup/readiness dependency matrix; safe defaults off; staged enablement and emergency disables. |
| Automated suites could be misreported as human usability/language or controlled performance evidence. | Separate artifact contracts, owners, sample minima, ordering after the converged build, and a final evidence-recording task that cannot pass when any producer is absent or failed. |

There are no unresolved technical design questions. Operator inputs and approval evidence listed in the risks are production enablement gates, not missing design decisions.

## Complexity Tracking

No constitution violation requires an exception. `PendingRegistration` is a bounded pre-account claim with no authentication authority, not a second user model. The new identity and notification modules fill repository-confirmed missing domains; the same system job scope owns notification and hourly reconciliation, and identity audit narrowly covers transitions that cannot truthfully use workspace audit before activation.

---

description: "Dependency-ordered Sprint 10.10 implementation tasks for Bayanly's public account lifecycle"
---

# Tasks: Public Accounts, Verification, Recovery, and Unified Access

**Feature**: `001-public-account-lifecycle`

**Sprint**: 10.10

**Input**: Approved artifacts in `specs/001-public-account-lifecycle/`
**Authority**: FastAPI remains the sole identity, credential, session, authorization, workspace, and administrator authority.

**Tests**: Tests are mandatory. In each phase, create the listed failing tests before implementing the behavior they cover, then make those tests pass without weakening existing assertions.

**Classification**: Existing auth/session/user/admin foundations are **CURRENT IMPLEMENTATION**; workspace/jobs foundations and rollout flags are **FEATURE-FLAGGED FOUNDATION**; username login, legacy hashes, cookie names, and admin provisioning are **LEGACY COMPATIBILITY**; public registration, verification, recovery, lifecycle email, and their UI are **ROADMAP-ONLY** until these tasks and rollout gates complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel because the task owns different files and has no dependency on another incomplete task in its phase.
- **[Story]**: Maps the task to one of the seven approved user stories.
- Every task names its primary file set and an observable completion condition.

---

## Phase 1: Setup (Shared Tooling and Test Support)

**Purpose**: Lock the only approved dependencies and establish deterministic, non-production test support used by later phases.

- [X] T001 Add the directly imported `email-validator` runtime dependency, lock it with the existing uv toolchain, and document its ownership/provenance review in `servers/fastapi/pyproject.toml` and `servers/fastapi/uv.lock`; completion requires `uv sync --locked --dev` to resolve without an unreviewed additional runtime package.
- [X] T002 [P] Add development-only `axe-core`, lock it with npm, and expose it only to the Cypress account-lifecycle harness in `servers/nextjs/package.json`, `servers/nextjs/package-lock.json`, and `servers/nextjs/cypress/support/component.ts`; completion requires the focused accessibility harness to load without production bundle usage.
- [X] T003 [P] Add deterministic clocks, lifecycle key fixtures, disposable identity builders, and an injectable in-memory mailbox fixture with no HTTP/file/console sink in `servers/fastapi/tests/conftest.py` and `servers/fastapi/tests/support/account_lifecycle.py`; completion requires two isolated tests to receive no shared token, recipient, or counter state.
- [X] T004 [P] Add controlled account-lifecycle API/mailbox fixtures and secret-safe screenshot/trace defaults for browser tests in `servers/nextjs/cypress/support/e2e.ts`, `servers/nextjs/cypress/fixtures/account-lifecycle/`, and `servers/nextjs/tests/helpers/account-lifecycle.mjs`; completion requires EN and AR fixtures to use only reserved example addresses and redacted tokens.

**Checkpoint**: Dependency ownership is locked and all later tests can run without production credentials, paid providers, or persistent bearer values.

---

## Phase 2: Foundational (Blocking Schema, Token, Security, and Durable-Work Prerequisites)

**Purpose**: Build shared foundations that every user story consumes while all public lifecycle capabilities remain off.

**Critical**: No user-story implementation begins until this phase passes. This phase extends the existing `User`, Alembic graph, operation controller, jobs/outbox, workspace, cookie/JWT, and localization boundaries; it does not create competing authorities.

### Schema, identifier ownership, and compatibility seams

- [X] T005 Write failing expand/backfill and data-preservation tests for current users, primary/admin accounts, username claims, invitations, workspace memberships, existing jobs, SQLite, and disposable PostgreSQL in `servers/fastapi/tests/unit/test_account_lifecycle_migration.py` and `servers/fastapi/tests/integration/test_postgresql_account_lifecycle_migration.py`; completion requires fixtures to assert no historical `is_verified` value becomes verified-email proof.
- [X] T006 Extend the canonical `User` mapping and add `PendingRegistration`, `AccountLoginIdentifier`, `AccountPurposeChallenge`, and `AccountLifecycleAuditEvent` persistence mappings with the approved state/check/index metadata in `servers/fastapi/models/sql/user.py`, `servers/fastapi/modules/identity/persistence/models.py`, and `servers/fastapi/models/sql/__init__.py`; completion requires pending rows to contain no password/session/role/workspace authority and identifiers to have exactly one owner kind.
- [X] T007 [P] Add the `NotificationDelivery` mapping and extend existing invitation and canonical job/outbox mappings for delivery generation, normalized identity kind, `SYSTEM_ACCOUNT_LIFECYCLE` authority, nullable workspace only for allowlisted system jobs, system idempotency, and the notification queue in `servers/fastapi/modules/notifications/persistence/models.py`, `servers/fastapi/modules/workspaces/persistence/models.py`, `servers/fastapi/modules/jobs/persistence/models.py`, and `servers/fastapi/modules/jobs/domain/models.py`; completion requires all existing workspace-job defaults and predicates to remain unchanged.
- [X] T008 Create the first linear Alembic expand/backfill revision after `d4f6a8c0e2b3` in `servers/fastapi/alembic/versions/` to add the approved nullable fields/tables/indexes and conservative account, username-claim, invitation, and job backfills; completion requires one graph head, preservation of every legacy identifier/hash/role/session/workspace field, and a downgrade that refuses once lifecycle/system-job data exists.
- [X] T009 [P] Write failing normalization-collision preflight tests for case-folded usernames, candidate emails, Unicode/IDNA variants, privacy-safe UUID/count output, and refusal to merge/rename in `servers/fastapi/tests/unit/test_account_identity_collision_check.py`; completion requires fixtures for both clean and ambiguous databases.
- [X] T010 Implement the read-only collision shadow/preflight command in `servers/fastapi/scripts/check_account_identity_collisions.py`; completion requires deterministic exit codes, no raw identifier output, no writes, and passing T009 on SQLite and disposable PostgreSQL.
- [X] T011 Update migration-head recognition and graph assertions for the expand revision in `servers/fastapi/migrations.py` and `servers/fastapi/tests/unit/test_migrations.py`; completion requires exactly one linear flags-off rollout head and rejection of a divergent or unknown graph, with T107 later advancing the recognized head to the enforcement revision.
- [X] T012 Make nullable public usernames and user-owned identifier lookup compatible across serializers, principals, workspace naming, and existing auth responses in `servers/fastapi/api/v1/auth/users.py`, `servers/fastapi/api/v1/auth/principal.py`, `servers/fastapi/modules/workspaces/application/personal.py`, and `servers/fastapi/tests/integration/test_auth_endpoints.py`; completion requires current username clients and deterministic personal-workspace behavior to remain unchanged while pending-owned claims never resolve to a user.
- [X] T013 Add identifier-claim plus minimum pending/challenge repository operations with one documented lock/CAS order and a shared authoritative challenge/subject/lease delivery-eligibility read contract in `servers/fastapi/modules/identity/persistence/identifiers.py`, `servers/fastapi/modules/identity/persistence/pending_registrations.py`, `servers/fastapi/modules/identity/persistence/challenges.py`, and `servers/fastapi/modules/identity/persistence/repositories.py`; completion requires owner exclusivity, equivalent PostgreSQL row-lock/SQLite serialized-writer outcomes, and an eligibility API that notification workers can call without duplicating lifecycle queries.

### Canonical token, normalization, and password foundations

- [ ] T014 [P] Write failing exact-parser, wrong-purpose, malformed/oversized input, and deterministic `ev`/`pr` golden-vector tests using the approved two vectors in `servers/fastapi/modules/identity/tests/test_account_tokens.py`; completion requires exact five-component `ba1` parsing and byte-for-byte token/digest assertions.
- [ ] T015 Implement the canonical token wire/parser/derivation/verifier boundary in `servers/fastapi/modules/identity/domain/tokens.py`; completion requires 256-bit HMAC-SHA256 secrets, lowercase SHA-256 token digests only, purpose/subject/generation binding, constant-time verification, and the exact timestamp-free byte context from `research.md`.
- [ ] T016 [P] Write failing key-ring/version/rotation/readiness tests for missing, duplicate, malformed, retired-too-early, and previous-key TTL cases in `servers/fastapi/modules/identity/tests/test_account_token_keys.py`; completion requires no key/token material in failure messages.
- [ ] T017 Implement the versioned account-token key ring and startup validation in `servers/fastapi/modules/identity/domain/token_keys.py` and `servers/fastapi/api/v1/auth/config.py`; completion requires separate reviewed configuration from the browser JWT secret and retention of previous key IDs through maximum TTL plus skew.
- [ ] T018 Add independent-process plus SQLite/PostgreSQL persistence reconstruction tests in `servers/fastapi/tests/integration/test_account_token_reconstruction.py`; completion requires both golden vectors to survive timestamp timezone/precision round trips unchanged and proves `issued_at` never enters derivation.
- [ ] T019 [P] Write failing email normalization and new-password policy tests for NFC, whole-address case-folding, IDNA domains, whitespace/control rejection, plus/dot preservation, 12-128 Unicode characters, spaces, and the local compromised-password digest set in `servers/fastapi/modules/identity/tests/test_identity_policies.py`.
- [ ] T020 Implement the single email normalizer and first/reset/admin password policy using the existing adaptive password helper in `servers/fastapi/modules/identity/domain/identifiers.py`, `servers/fastapi/modules/identity/domain/passwords.py`, and `servers/fastapi/modules/identity/resources/common_password_digests.txt`; completion requires documented dataset provenance, no online password service, and unchanged legacy six-character login/hash-upgrade compatibility.

### Canonical abuse, CSRF, redirect, and privacy controls

- [ ] T021 [P] Write failing unit/Redis tests for multi-window admission/outcome policies, purpose-separated HMAC identity/IP-identity keys, challenge/global scopes, maximum safe `Retry-After`, production fail-closed behavior, and successful-credential failure-scope clearing in `servers/fastapi/tests/unit/test_operation_security.py` and `servers/fastapi/tests/integration/test_operation_security_redis.py`.
- [ ] T022 Extend the existing canonical controller—without a second limiter—with lifecycle policies, multiple windows, outcome recording, concurrency ceilings, privacy-safe Redis keys, and explicit global budgets in `servers/fastapi/api/operation_security.py`; completion requires the approved signup/recovery/verification/resend/login ceilings and memory/Redis contract parity.
- [ ] T023 [P] Write failing JSON/content-size/custom-header/exact-Origin/Fetch-Metadata/CORS tests for login, logout, registration, resend, verification, forgot/reset, authenticated password change, locale mutation, and revoke-all in `servers/fastapi/tests/security/test_account_mutation_csrf.py`.
- [ ] T024 Implement the shared account-mutation policy and exact credentialed production-origin readiness in `servers/fastapi/api/middlewares.py` and `servers/fastapi/api/main.py`; completion requires rejection before domain mutation, retention of `SameSite=Lax`, and no claim that unrelated repository-wide CSRF gaps are closed.
- [ ] T025 [P] Write failing backend return-destination tests for absolute, scheme-relative, encoded-backslash, control, fragment, API/internal, auth-loop, unauthorized admin/workspace, and safe localized paths in `servers/fastapi/modules/identity/tests/test_account_return_paths.py`.
- [ ] T026 Implement backend-authoritative account return-path normalization and authorization in `servers/fastapi/modules/identity/domain/redirects.py`; completion requires login/activation callers to receive only an authorized localized path or Dashboard fallback.
- [ ] T027 [P] Harden the existing client pre-filter and add matching unit coverage in `servers/nextjs/lib/product-navigation.ts` and `servers/nextjs/tests/product-experience.test.mjs`; completion requires fragments and internal/auth-loop paths to be rejected while backend-returned paths remain the only navigation authority.
- [ ] T028 [P] Write failing lifecycle audit/metrics tests for finite schemas, safe IDs, aggregate-only anonymous cleanup, forbidden arbitrary metadata, and bounded labels in `servers/fastapi/modules/identity/tests/test_account_observability.py`.
- [ ] T029 Implement purpose-limited append-only lifecycle audit and allowlisted metrics/events in `servers/fastapi/modules/identity/persistence/audit.py` and `servers/fastapi/modules/identity/observability.py`; completion requires no anonymous email ledger and continued use of workspace audit for workspace creation.
- [ ] T030 Write failing canary-redaction tests covering email, password/hash, token/link, cookie, request body/header/query, rendered message, provider response, path, logs, Sentry, audit, metrics, and job payload/result/event data in `servers/fastapi/tests/security/test_account_lifecycle_redaction.py`.
- [ ] T031 Implement lifecycle Sentry/request filtering and extend canonical job payload secret-key rejection in `servers/fastapi/api/main.py`, `servers/fastapi/modules/identity/observability.py`, and `servers/fastapi/modules/jobs/application/submit.py`; completion requires T030 to prove every canary absent while safe IDs/categories remain observable.

### Canonical system jobs and minimum notification boundary

- [ ] T032 [P] Write failing authority/idempotency tests proving only registered handlers can use `SYSTEM_ACCOUNT_LIFECYCLE`, public callers cannot submit it, workspace jobs remain tenant-scoped, notification payloads contain only `notificationId`, and reconciliation is singleton/bounded in `servers/fastapi/modules/jobs/tests/test_account_lifecycle_jobs.py`.
- [ ] T033 Extend the canonical job registry, submit/outbox constraints, worker queue selection, and runtime wiring with the allowlisted system-lifecycle registration mechanism and `notification` queue in `servers/fastapi/modules/jobs/workers/registry.py`, `servers/fastapi/modules/jobs/application/submit.py`, `servers/fastapi/modules/jobs/outbox.py`, and `servers/fastapi/modules/jobs/workers/runtime.py`; completion requires finite canonical retry/dead-letter behavior and no second scheduler/queue, while T037 and T048 register the concrete delivery and reconciliation handlers.
- [ ] T034 [P] Write failing transport, SMTP-security, in-memory-isolation, deterministic EN/AR template, parity, bidi, URL-fragment, bounded-size, safe-error, and deterministic Message-ID tests in `servers/fastapi/modules/notifications/tests/test_transactional_email.py`.
- [ ] T035 Implement the provider-neutral notification request/outcome contract, the single canonical deterministic EN/AR transactional-email catalog/template owner, standard-library async-safe SMTP adapter with reviewed DNS/TLS/time/size controls, and injectable memory adapter in `servers/fastapi/modules/notifications/domain/contracts.py`, `servers/fastapi/modules/notifications/templates/`, and `servers/fastapi/modules/notifications/adapters/`; completion requires no second email catalog, adapter-owned retry, tracking, marketing, HTTP mailbox, or provider body logging.
- [ ] T036 Write failing notification state-machine/worker tests that use T013's shared authoritative eligibility contract for subject/lease/challenge revalidation, exact token reconstruction, delivery generations, same-token redelivery while live, replacement only after expiry/invalidation, deterministic Message-ID, three-attempt ceiling, known transient retry, permanent failure, stale dispatch to `UNKNOWN_TERMINAL`, suppression, and idempotent replay in `servers/fastapi/modules/notifications/tests/test_notification_delivery.py`.
- [ ] T037 Implement notification repository/application handling and register `account.notification.deliver.v1` in `servers/fastapi/modules/notifications/persistence/repositories.py`, `servers/fastapi/modules/notifications/application/delivery.py`, `servers/fastapi/modules/notifications/workers/deliver.py`, and `servers/fastapi/modules/jobs/workers/registry.py`; completion requires re-reading lifecycle authority through T013 immediately before effect, one bounded provider attempt per canonical job attempt, no duplicated challenge repository, and never persisting raw tokens, recipients in jobs, rendered bodies, or provider responses.

### Safe rollout foundations

- [ ] T038 Write failing foundation tests for the four default-off flags, safe configuration parsing, public unauthenticated capability serialization, omission of dependency/account/secret reasons, application-service gate enforcement, emergency consumption controls, and reusable dependency-health primitives in `servers/fastapi/tests/unit/test_account_lifecycle_capabilities.py`; completion requires flags-off startup and the public capability projection to work without claiming integrated production readiness.
- [ ] T039 Implement backend-owned `public_signup`, `email_verification`, `password_recovery`, and `notification_delivery` configuration, service gates, public unauthenticated `/auth/status` capability projection, emergency consumption controls, and reusable health primitives in `servers/fastapi/api/runtime_capabilities.py`, `servers/fastapi/api/v1/auth/config.py`, `servers/fastapi/api/v1/auth/schemas.py`, `servers/fastapi/api/v1/auth/router.py`, and `servers/fastapi/api/main.py`; completion requires public pages to receive only product-availability booleans before US1 begins, issuance to fail closed when its own gate is off, and pending reclamation to remain independent; T109 alone owns final integrated readiness evaluation.

**Checkpoint**: The additive foundation is deployable with every public capability off; token vectors, schema ownership, canonical distributed controls, system jobs, notification transport, privacy controls, and compatibility seams are testable before any public route is enabled.

---

## Phase 3: User Story 1 - Register, Verify, Set a Credential, and Activate (Priority: P1) MVP

**Goal**: A visitor registers with email/locale only, proves email possession, sets the first password after proof, and atomically receives one normal user, verified identifier, personal workspace, owner membership, and common cookie session.

**Independent Test**: With fake delivery and public flags enabled, registration creates no `User` or credential; valid token consumption creates exactly one fully provisioned normal account and redirects through the backend-approved path.

### Tests for User Story 1

- [ ] T040 [P] [US1] Write failing HTTP contract tests for generic email/locale-only registration, extra authority/password rejection, no cookie/user/workspace before proof, verification consume result codes, and cookie-after-commit in `servers/fastapi/tests/integration/test_public_account_registration.py`.
- [ ] T041 [P] [US1] Write failing anti-pre-hijacking tests for attacker-before-victim, victim re-registration, attacker-after-victim, unchanged live verification token, stale versus current links, concurrent registrations, and concurrent consume with different passwords in `servers/fastapi/tests/security/test_registration_pre_hijacking.py`; completion requires exactly one User/password/workspace winner whose password came from the winning valid-token request.
- [ ] T042 [P] [US1] Write failing fixed-retention tests for exactly 72 hours, no extension by registration/resend/retry/provider delay, expiry bounded by lease, lazy/hourly equivalence, claim release, PII redaction, child revocation/suppression, 30-day terminal purge, and verification/reclaim races on SQLite/PostgreSQL in `servers/fastapi/tests/integration/test_pending_registration_retention.py`.
- [ ] T043 [P] [US1] Write failing activation transaction tests with injected user/hash/identifier/audit/workspace/membership failures, same-token retry, replay, and PostgreSQL/SQLite concurrent winners in `servers/fastapi/tests/integration/test_public_account_activation.py`.

### Implementation for User Story 1

- [ ] T044 [US1] Extend T013's shared pending/challenge repositories with registration/activation mutation transitions for claim-first locking, compare-and-set generations, one-current-challenge semantics, failed-attempt ceilings, and terminal redaction/purge guards in `servers/fastapi/modules/identity/persistence/pending_registrations.py` and `servers/fastapi/modules/identity/persistence/challenges.py`; completion requires identical valid terminal states on PostgreSQL and SQLite without creating a second repository or changing the worker eligibility contract.
- [ ] T045 [US1] Implement email/locale-only registration, live-repeat same-token scheduling eligibility, expired-challenge replacement, stale lazy reclamation, and generic duplicate/collision behavior in `servers/fastapi/modules/identity/application/registration.py`; completion requires one atomic pending/claim/challenge/delivery/outbox transaction and no password/User/session/workspace write.
- [ ] T046 [US1] Implement verification consumption and first-password activation in `servers/fastapi/modules/identity/application/activation.py`; completion requires password policy/hash, User creation, identifier transfer, verified state, deterministic personal workspace/owner membership, both safe audits, challenge consumption/sibling revocation, and pending redaction to commit or roll back together.
- [ ] T047 [US1] Wire registration and verification delivery creation through the existing canonical outbox in `servers/fastapi/modules/identity/application/registration.py` and `servers/fastapi/modules/notifications/application/delivery.py`; completion requires `{notificationId}` as the only job payload and SMTP only after commit.
- [ ] T048 [US1] Implement lazy reclamation reuse plus the bounded hourly reconciliation and terminal purge handlers, and register `account.pending.reconcile.v1`, in `servers/fastapi/modules/identity/application/reclamation.py`, `servers/fastapi/modules/identity/workers/reconcile_pending.py`, and `servers/fastapi/modules/jobs/workers/registry.py`; completion requires atomic claim release/redaction/revocation/suppression, terminal-job preconditions, and a query that cannot select any `User`.
- [ ] T049 [US1] Add bounded request/response schemas and thin `POST /auth/register` and `POST /auth/email-verification/consume` adapters in `servers/fastapi/api/v1/auth/schemas.py` and `servers/fastapi/api/v1/auth/router.py`; completion requires stable errors, backend feature checks, no secret response fields, and `/auth/verify` remaining session verification.
- [ ] T050 [US1] Allowlist only the approved unauthenticated lifecycle paths and register their canonical operation policies in `servers/fastapi/api/middlewares.py` and `servers/fastapi/api/operation_security.py`; completion requires every direct route call to retain CSRF/origin, abuse, feature, and body-bound enforcement.
- [ ] T051 [P] [US1] Write failing frontend unit tests for lifecycle request/response types, stable error mapping, T039's already-available public unauthenticated capability gating, timeouts, duplicate-submit prevention, and generic registration states in `servers/nextjs/tests/account-lifecycle-api.test.mjs`.
- [ ] T052 [US1] Implement the common account-lifecycle API adapter and discriminated state mappings with same-origin JSON, CSRF header, credentials, bounded timeouts, and backend redirect consumption in `servers/nextjs/features/account-lifecycle/api.ts`, `servers/nextjs/features/account-lifecycle/types.ts`, and `servers/nextjs/features/account-lifecycle/error-state.ts`.
- [ ] T053 [P] [US1] Write failing token-handoff privacy tests for fragment parsing/bounds, immediate history scrub, memory-only lifetime, no query/storage/DOM/console/telemetry exposure, analytics suppression, no-store/no-referrer, and terminal erasure in `servers/nextjs/tests/account-token-handoff.test.mjs` and `servers/nextjs/tests/account-token-privacy.test.mjs`.
- [ ] T054 [US1] Implement analytics-dark verification/reset handoff and route security metadata in `servers/nextjs/features/account-lifecycle/token-handoff.ts`, `servers/nextjs/app/MixpanelInitializer.tsx`, `servers/nextjs/app/layout.tsx`, and `servers/nextjs/app/(public-account)/layout.tsx`; completion requires token scrub before analytics or first-password rendering.
- [ ] T055 [P] [US1] Write failing component tests for registration, check-email, verification-required, verification first-password/completed/already/expired/invalid/rate/retryable states, and shared public `loading.tsx`/`error.tsx` safe retry behavior in both locales in `servers/nextjs/cypress/component/account-registration.cy.tsx`.
- [ ] T056 [US1] Implement the public-account scaffold, localized route boundaries, registration/verification routes, and all US1 English/Arabic keys in `servers/nextjs/features/account-lifecycle/components/`, `servers/nextjs/app/(public-account)/loading.tsx`, `servers/nextjs/app/(public-account)/error.tsx`, `servers/nextjs/app/(public-account)/register/page.tsx`, `servers/nextjs/app/(public-account)/check-email/page.tsx`, `servers/nextjs/app/(public-account)/verification-required/page.tsx`, `servers/nextjs/app/(public-account)/verify/page.tsx`, `servers/nextjs/messages/en.json`, and `servers/nextjs/messages/ar.json`; completion requires registration to expose no password, verification to set it only after token scrub, and safe accessible RTL/LTR loading/error/retry boundaries that never authorize or expose internal state.

**Checkpoint**: US1 independently proves the anti-pre-hijacking invariant and all-or-nothing account/workspace activation using only canonical identity, session, job, and workspace boundaries.

---

## Phase 4: User Story 2 - Sign In Through One Account Entry Point (Priority: P1)

**Goal**: Verified public email users and existing username/admin users authenticate through the same backend contract and localized root page, with generic failures and distributed protection.

**Independent Test**: Email, legacy username, and bootstrap-admin login succeed through one route; pending/absent/wrong/disabled inputs are indistinguishable; normal users remain backend-denied from admin routes; two API instances share every production login budget.

### Tests for User Story 2

- [ ] T057 [P] [US2] Write failing login compatibility/security tests for email and username resolution, `identifier`/`username` alias conflicts, pending-owned claims, absent/wrong/disabled/deactivated identities, dummy/real password work, legacy six-character login, PBKDF2 upgrade, cookie attributes, and direct admin denial in `servers/fastapi/tests/integration/test_unified_login.py`.
- [ ] T058 [P] [US2] Write failing two-instance Redis tests for trusted-IP admission, five-per-IP/identifier failures per five minutes, ten-per-identifier failures per 15 minutes, global ceilings, formatting/route-instance bypass attempts, generic maximum `Retry-After`, privacy-safe keys, selective success clearing, and Redis production fail-closed behavior in `servers/fastapi/tests/integration/test_distributed_login_control.py`.

### Implementation for User Story 2

- [ ] T059 [US2] Implement active user-owned identifier resolution and dummy-work-compatible login application behavior in `servers/fastapi/modules/identity/application/login.py`; completion requires pending claims to be ineligible and existing username/admin/legacy hash behavior to remain canonical.
- [ ] T060 [US2] Extend the existing login schema/adapter for preferred `identifier`, compatible `username`, distributed outcome recording, generic credential/rate errors, and backend-approved return path in `servers/fastapi/api/v1/auth/schemas.py` and `servers/fastapi/api/v1/auth/router.py`; completion requires the existing JWT/cookie/auth-version strategy to remain unchanged.
- [ ] T061 [US2] Remove `servers/fastapi/api/v1/auth/rate_limit.py` and all process-local imports/calls/state-based tests after the distributed controller is wired, and add a source/readiness assertion in `servers/fastapi/tests/security/test_login_limiter_cutover.py`; completion requires the canonical operation controller to be the sole final production authority before public email login can enable.
- [ ] T062 [P] [US2] Write failing frontend tests for the single root login's email/username field, generic invalid/rate/unavailable/session-expired states, credentials, backend-approved redirects, and exact US2 EN/AR key parity in `servers/nextjs/tests/unified-login.test.mjs`.
- [ ] T063 [US2] Refactor the existing root `AuthGate` onto the shared account-lifecycle client and add its required English/Arabic login/session keys in `servers/nextjs/components/Auth/AuthGate.tsx`, `servers/nextjs/app/page.tsx`, `servers/nextjs/messages/en.json`, and `servers/nextjs/messages/ar.json`; completion requires one localized login entry point, no pending-account verification inference, and no second session store.
- [ ] T064 [US2] Add end-to-end login/cookie/return-path/admin-denial coverage across verified public, admin-provisioned, and bootstrap accounts in `servers/fastapi/tests/integration/test_unified_login.py` and `servers/nextjs/cypress/e2e/account-login.cy.ts`; completion requires the same server-issued authority and safe Dashboard fallback in both locales.

**Checkpoint**: US2 replaces split/process-local login behavior with one compatible, distributed, backend-authoritative account entry point.

---

## Phase 5: User Story 3 - Recover a Forgotten Password (Priority: P1)

**Goal**: Eligible verified-email users request an enumeration-resistant reset, consume one short-lived token, and invalidate all earlier browser sessions without auto-login.

**Independent Test**: Existing and ineligible/absent requests are publicly identical; one valid reset changes the password and `auth_version`; all other tokens and prior cookies fail; one concurrent consumer wins.

### Tests for User Story 3

- [ ] T065 [P] [US3] Write failing forgot-password tests for recoverable, absent, pending, username-only, disabled/deactivated, primary-admin, and alias-collision identities with equal 202 schema/headers/timing envelope and bounded issuance in `servers/fastapi/tests/integration/test_password_recovery.py`.
- [ ] T066 [P] [US3] Write failing reset tests for 30-minute expiry, wrong purpose/generation, malformed/revoked/reused token, policy/mismatch, concurrent issuance, concurrent consumption, sibling revocation, old/new passwords, `auth_version` rotation, no auto-login, and old-cookie rejection in `servers/fastapi/tests/integration/test_password_reset.py`.
- [ ] T067 [P] [US3] Write failing recovery delivery tests for one current reset generation, transactional challenge/delivery/outbox creation, bounded provider effects, token reconstruction, and disabled/deactivated suppression in `servers/fastapi/modules/notifications/tests/test_password_reset_delivery.py`.

### Implementation for User Story 3

- [ ] T068 [US3] Implement enumeration-resistant forgot issuance and atomic password-reset consumption in `servers/fastapi/modules/identity/application/recovery.py`; completion requires auth-version binding, one current reset generation, canonical hashing, challenge/sibling transition, `auth_version` increment, safe audit, no auto-login, and one concurrent winner.
- [ ] T069 [US3] Add bounded `POST /auth/password/forgot` and `POST /auth/password/reset` schemas/adapters and register their pre-lookup canonical policies in `servers/fastapi/api/v1/auth/schemas.py`, `servers/fastapi/api/v1/auth/router.py`, and `servers/fastapi/api/operation_security.py`; completion requires stable purpose-safe errors and identical public forgot acknowledgements.
- [ ] T070 [US3] Wire reset challenge/delivery/job creation atomically and delivery execution after commit in `servers/fastapi/modules/identity/application/recovery.py` and `servers/fastapi/modules/notifications/application/delivery.py`; completion requires no email/provider call in the request transaction.
- [ ] T071 [P] [US3] Write failing component/privacy tests for forgot, reset handoff/form, expired/used/invalid/rate/unavailable/completed states, token erasure, no reset cookie, and exact US3 EN/AR key parity in `servers/nextjs/cypress/component/account-recovery.cy.tsx` and `servers/nextjs/tests/account-token-privacy.test.mjs`.
- [ ] T072 [US3] Implement forgot-password, reset-password, and recovery-complete routes through the shared lifecycle adapter/handoff and add all required US3 English/Arabic keys in `servers/nextjs/app/(public-account)/forgot-password/page.tsx`, `servers/nextjs/app/(public-account)/reset-password/page.tsx`, `servers/nextjs/app/(public-account)/recovery-complete/page.tsx`, `servers/nextjs/messages/en.json`, and `servers/nextjs/messages/ar.json`; completion requires a completed reset to return to unified sign-in with equivalent LTR/RTL states.
- [ ] T073 [US3] Integrate auth-version/session-expiry recovery messaging without frontend authority in `servers/nextjs/components/product-shell/SessionMonitor.tsx` and `servers/nextjs/tests/session-monitor.test.mjs`; completion requires an old post-reset cookie to reach localized sign-in recovery after backend rejection.

**Checkpoint**: US3 independently proves enumeration resistance, one-time reset, appropriate session revocation, and no second recovery/session authority.

---

## Phase 6: User Story 4 - Resend Verification and Recover from Delivery Problems (Priority: P2)

**Goal**: A live pending registration can safely re-deliver the same current verification token or replace an expired challenge within its fixed lease, with bounded delivery and no state disclosure.

**Independent Test**: Fake provider transient/permanent/ambiguous outcomes and rapid resend requests remain bounded; a live resend preserves token and lease; an expired challenge is replaced only while the lease is live; stale work suppresses.

### Tests for User Story 4

- [ ] T074 [P] [US4] Write failing resend tests for generic all-state acknowledgement, 60-second cooldown, five-per-24-hour identity ceiling, IP/global limits, same-token live redelivery, expired-challenge replacement, no lease extension, consumed/reclaimed suppression, and registration-sharing-resend budgets in `servers/fastapi/tests/integration/test_verification_resend.py`.
- [ ] T075 [P] [US4] Write failing provider failure/recovery tests for deterministic per-delivery Message-ID, finite known-safe retry, terminal permanent failure, ambiguous terminal handoff, user-requested later delivery, and no duplicate effective challenge in `servers/fastapi/modules/notifications/tests/test_verification_delivery_failures.py`.

### Implementation for User Story 4

- [ ] T076 [US4] Implement resend eligibility, **same-token redelivery while live**, **replacement challenge only after expiry/invalidation** bounded by `reclaim_after`, stale lazy reclamation, and generic suppression in `servers/fastapi/modules/identity/application/resend_verification.py`; completion requires no password/User/session, no change to live challenge identity/token/binding/expiry, and no lease extension while `delivery_generation` may increase independently.
- [ ] T077 [US4] Add the bounded `POST /auth/email-verification/resend` schema/adapter and canonical policies in `servers/fastapi/api/v1/auth/schemas.py`, `servers/fastapi/api/v1/auth/router.py`, and `servers/fastapi/api/operation_security.py`; completion requires one generic response body and non-identifying `Retry-After`.
- [ ] T078 [US4] Implement per-challenge delivery-generation scheduling and stale/current revalidation for resend outcomes in `servers/fastapi/modules/notifications/application/delivery.py`; completion requires a new delivery/Message-ID to reconstruct the exact same live verification bearer.
- [ ] T079 [P] [US4] Write failing component tests for verification-required, resend idle/submitting/generic accepted/cooldown/rate/unavailable/delivery-delayed states, exact US4 EN/AR key parity, and no stored account data in `servers/nextjs/cypress/component/account-resend.cy.tsx`.
- [ ] T080 [US4] Implement resend-verification and delivery-recovery navigation and add all required US4 English/Arabic keys in `servers/nextjs/app/(public-account)/resend-verification/page.tsx`, `servers/nextjs/app/(public-account)/check-email/page.tsx`, `servers/nextjs/features/account-lifecycle/components/`, `servers/nextjs/messages/en.json`, and `servers/nextjs/messages/ar.json`; completion requires frontend timers to remain UX-only, never infer backend eligibility, and render equivalent LTR/RTL states.

**Checkpoint**: US4 keeps delivery failure recoverable while preserving fixed retention, same-token semantics, and canonical bounded retry authority.

---

## Phase 7: User Story 5 - Preserve Administrator-Provisioned Accounts (Priority: P1)

**Goal**: Existing/bootstrap/admin-provisioned username accounts retain identity, authority, recovery, workspace, and session semantics while public paths can create only normal verified accounts.

**Independent Test**: Upgrade representative current data, create/reset a normal user through the authorized admin route, and verify preserved IDs/hashes/roles/workspaces, administrator-managed recovery, session invalidation, primary-admin isolation, and permanent absence of public setup/framework routes.

### Tests for User Story 5

- [ ] T081 [P] [US5] Add upgrade fixture tests covering primary/historical superusers, normal current users, usernames, hashes, locales, auth versions, owner/workspace memberships, and `GRANDFATHERED`/`ADMIN_PROVISIONED`/`UNSET` email semantics in `servers/fastapi/tests/unit/test_account_lifecycle_migration.py`.
- [ ] T082 [P] [US5] Write failing admin create/reset compatibility tests for shared new-password policy, fixed non-superuser authority, atomic personal workspace, username claim, safe audit, reset challenge invalidation, and `auth_version` rotation in `servers/fastapi/tests/integration/test_admin_user_lifecycle.py`.

### Implementation for User Story 5

- [ ] T083 [US5] Implement shared authorized username-user creation and administrator password-reset application policies in `servers/fastapi/modules/identity/application/admin_accounts.py`; completion requires canonical User/password/workspace/session behavior and no public email-recovery enrollment.
- [ ] T084 [US5] Adapt the existing administrator user endpoints to the shared identity policies without changing their authorization boundary in `servers/fastapi/api/v1/admin/router.py`; completion requires normal callers to remain denied and existing response compatibility to pass.
- [ ] T085 [US5] Synchronize the primary administrator's user-owned username claim during existing locked bootstrap create/rename/recovery in `servers/fastapi/api/v1/auth/bootstrap.py`; completion requires deployment recovery to remain authoritative and public flows unable to change or reveal the primary account.
- [ ] T086 [US5] Add contract regressions proving `/api/v1/auth/setup` stays 404 and stock FastAPI Users registration/verification/reset routers remain unmounted in `servers/fastapi/tests/integration/test_auth_endpoints.py`; completion requires no second auth lifecycle to be reachable.

**Checkpoint**: US5 proves Sprint 10.10 is additive for current administrators and users and cannot elevate public accounts.

---

## Phase 8: User Story 6 - Maintain Unified Account, Session, and Workspace Behavior (Priority: P2)

**Goal**: Authenticated identity, recovery eligibility, locale, session actions, invitations, and personal/workspace authority remain consistent across backend contracts and `/account`.

**Independent Test**: A verified public and username-only account see correct additive status/account data, both workspace rollout modes preserve isolation, invitation rules require the correct identifier proof/token, logout ends only the current cookie, and revoke/reset/deactivate reject every earlier cookie.

### Tests for User Story 6

- [ ] T087 [P] [US6] Write failing status/session/password-change tests for additive authenticated account fields over T039's public capabilities, legacy response preservation, current logout, authenticated revoke-all, correct/incorrect current password, unchanged new password, policy/mismatch, disabled account, canonical rate limits, concurrent same-generation changes, reset-challenge revocation, exactly one `auth_version` winner, all prior-cookie rejection, success cookie deletion/no replacement, admin reset/deactivation invalidation, and primary API credential separation in `servers/fastapi/tests/integration/test_account_sessions.py`.
- [ ] T088 [P] [US6] Write failing workspace/invitation/tenant tests for exactly one personal workspace, both rollout modes, verified-email plus separate-token invitation acceptance, legacy username compatibility, no auto-accept, no replacement of personal workspace, and cross-tenant enumeration resistance in `servers/fastapi/tests/integration/test_account_workspace_invitations.py`.

### Implementation for User Story 6

- [ ] T089 [US6] Extend authenticated status/session serialization and display-identifier compatibility in `servers/fastapi/api/v1/auth/users.py`, `servers/fastapi/api/v1/auth/principal.py`, `servers/fastapi/api/v1/auth/schemas.py`, and `servers/fastapi/api/v1/auth/router.py`; completion requires authoritative `account_identifier`, origin/state/email state/recovery eligibility/workspace context with all existing fields retained while reusing—not reimplementing—T039's unauthenticated capability projection.
- [ ] T090 [US6] Implement authenticated password change, global browser-session revocation, and deactivation challenge invalidation through the existing password helper and `auth_version`/activity in `servers/fastapi/modules/identity/application/passwords.py`, `servers/fastapi/modules/identity/application/sessions.py`, `servers/fastapi/api/v1/auth/schemas.py`, `servers/fastapi/api/v1/auth/router.py`, and `servers/fastapi/api/operation_security.py`; completion requires lock-time active/generation/current-password rechecks, distinct-policy-compliant hash replacement, reset-challenge revocation, one version increment, safe audit, caller-cookie deletion with no replacement, stable errors, one concurrent winner, and no session inventory, password subsystem, or limiter.
- [ ] T091 [US6] Implement normalized invitation identity-kind matching and verified-email acceptance inside the existing workspace boundary in `servers/fastapi/modules/workspaces/application/invitations.py`; completion requires the existing invitation token and workspace authorization in addition to identity match.
- [ ] T092 [P] [US6] Write failing frontend tests for `/account` identity/recovery states, password-change current/new/confirmation fields, incorrect/unchanged/policy/rate/stale-session/failure/success states, sign-in-again behavior, locale, current logout, revoke-all confirmation/result, legacy/admin-managed recovery, capability display-only behavior, exact US6 EN/AR key parity, and `/settings` separation in `servers/nextjs/tests/account-page.test.mjs`.
- [ ] T093 [US6] Implement the backend-driven identity/recovery/locale/password-change/logout/revoke-all account surface and all required US6 English/Arabic keys in `servers/nextjs/app/(presentation-generator)/(dashboard)/account/AccountPage.tsx`, `servers/nextjs/app/(presentation-generator)/(dashboard)/account/page.tsx`, `servers/nextjs/messages/en.json`, and `servers/nextjs/messages/ar.json`; completion requires clearing protected client state and returning to backend-approved localized sign-in after password-change success, with no client-derived verification, role, workspace, recovery, or session authority.
- [ ] T094 [US6] Align protected-route/session-expiry/logout navigation with the shared safe-return and lifecycle states in `servers/nextjs/components/product-shell/SessionMonitor.tsx`, `servers/nextjs/components/Auth/LogoutButton.tsx`, and `servers/nextjs/lib/product-navigation.ts`; completion requires normal logout to make no global-revocation claim.

**Checkpoint**: US6 proves one account/session/workspace interpretation across compatibility and staged workspace modes.

---

## Phase 9: User Story 7 - Complete Every Flow in English and Arabic (Priority: P1)

**Goal**: Every lifecycle state and email is equivalent in English LTR and Arabic RTL, keyboard accessible, responsive, bidi safe, and isolated from presentation geometry.

**Independent Test**: Complete registration-to-Dashboard and forgot/reset journeys in `/en` and `/ar` at desktop/320px/200% zoom by keyboard, with no serious/critical automated accessibility violations and equivalent state/actions.

### Tests for User Story 7

- [ ] T095 [P] [US7] Write failing convergence tests for story-owned identical `accountLifecycle.*` UI keys/variables and T035-owned backend email subject/body keys/variables, safe interpolation, locale-preserving links, unused-key/terminology drift, and missing-copy failures in `servers/nextjs/tests/account-lifecycle-i18n.test.mjs` and `servers/fastapi/modules/notifications/tests/test_template_localization.py`.
- [ ] T096 [US7] Converge the already story-owned English/Arabic UI catalogs for terminology, parity, unused keys, bidi-safe variables, and RTL regression without becoming the first owner of any story string in `servers/nextjs/messages/en.json` and `servers/nextjs/messages/ar.json`; completion requires equivalent actions/states and no edits that duplicate T035's transactional-email catalog ownership.
- [ ] T097 [P] [US7] Write failing shared-component tests for semantic headings, labels/descriptions/errors, autocomplete, error-summary focus, live announcements, visible focus, Enter submission, duplicate prevention, bounded timeout/recovery, reduced motion, bidi isolation, and no keyboard traps in `servers/nextjs/cypress/component/account-lifecycle-accessibility.cy.tsx`.
- [ ] T098 [US7] Implement shared lifecycle form/status scaffolds and logical-direction responsive styles in `servers/nextjs/features/account-lifecycle/components/AccountLifecycleForm.tsx`, `servers/nextjs/features/account-lifecycle/components/AccountLifecycleStatus.tsx`, and `servers/nextjs/features/account-lifecycle/components/account-lifecycle.css`; completion requires operability at 320 CSS pixels and 200% zoom in LTR/RTL.
- [ ] T099 [P] [US7] Add automated `axe-core` component coverage for every loading/success/validation/generic/rate/expired/invalid/used/delivery/offline state in `servers/nextjs/cypress/component/account-lifecycle.cy.tsx`; completion requires zero serious or critical violations.
- [ ] T100 [US7] Add the controlled English registration -> token scrub -> first-password activation -> Dashboard and forgot -> reset -> old-session rejection product journey in `servers/nextjs/cypress/e2e/account-lifecycle.cy.ts`; completion requires safe redirects, provider/network failure recovery, and no secret-bearing artifacts.
- [ ] T101 [US7] Extend the same product journey with Arabic RTL state/action parity, keyboard-only use, bidi addresses, focus/live-region assertions, 320px viewport, and 200% zoom in `servers/nextjs/cypress/e2e/account-lifecycle.cy.ts`.
- [ ] T102 [P] [US7] Add a regression assertion that account-lifecycle code does not import or mutate presentation renderer/canvas geometry boundaries in `servers/nextjs/tests/account-lifecycle-boundaries.test.mjs`; completion requires unchanged presentation element order and physical coordinates.
- [ ] T103 [US7] Extend the canonical localization checker to include backend notification catalogs and lifecycle interpolation parity in `scripts/check-localization.mjs` and `servers/nextjs/tests/i18n-coverage.test.mjs`; completion requires the root localization gate to fail on either UI or email EN/AR drift.

**Checkpoint**: US7 makes bilingual, accessible behavior a tested release invariant rather than a post-implementation translation pass.

---

## Phase 10: Polish, Enforcement, Rollout, and Cross-Cutting Convergence

**Purpose**: Apply post-shadow constraints, converge security/contract evidence, document the implemented posture, and run every release gate without broadening Sprint 10.10.

- [ ] T104 [P] Add the consolidated adversarial security suite for registration/forgot enumeration shape and timing, malformed/wrong-purpose/replay tokens, attacker/victim races, authenticated password-change incorrect/unchanged/disabled/concurrent/stale-generation cases, CSRF/origin bypass, return redirects, tenant probes, authority-field injection, and rate-limit bypass in `servers/fastapi/tests/security/test_public_account_security.py`; completion requires stable bounded public errors, exactly one password-change race winner, and no unauthorized protected state mutation.
- [ ] T105 [P] Add static/runtime secrecy tests proving raw email/token/password/cookie/provider content never enters Redis keys, SQL job payloads/results/events, audit, logs, Sentry, analytics, browser storage/history/referrers/DOM, OpenAPI examples, or captured artifacts in `servers/fastapi/tests/security/test_account_lifecycle_redaction.py` and `servers/nextjs/tests/account-token-privacy.test.mjs`.
- [ ] T106 Write failing enforcement-migration tests for user/account/email constraints, nullable public username, global normalized-email uniqueness, identifier owner exclusivity, pending fixed-retention/redaction, one-current challenge per subject/purpose, delivery generation uniqueness, job authority/workspace scope, invitation identity, collision refusal, and post-data downgrade refusal in `servers/fastapi/tests/unit/test_account_lifecycle_migration.py` and `servers/fastapi/tests/integration/test_postgresql_account_lifecycle_migration.py`.
- [ ] T107 Create the second linear Alembic constraint-enforcement revision in `servers/fastapi/alembic/versions/` only after the shadow checker is clean and advance the recognized head in `servers/fastapi/migrations.py`; completion requires one head, supported SQLite/PostgreSQL constraints, no destructive merge/rename, and downgrade limited to the approved pre-lifecycle-data window.
- [ ] T108 Rehearse empty/current-fixture upgrade, backfill, clean/blocked shadow gate, enforcement, idempotency, pre-data downgrade, and post-data operational rollback on SQLite and disposable PostgreSQL using `servers/fastapi/scripts/check_migrations.py`, `servers/fastapi/scripts/check_account_identity_collisions.py`, and `servers/fastapi/tests/integration/test_postgresql_account_lifecycle_migration.py`; completion requires preserved legacy data and documented exact failures/skips.
- [ ] T109 Implement the sole final integrated production-readiness evaluator and test it against the already-built configuration/health primitives: migration/enforcement state, worker/queue health, hourly singleton reconciliation schedule, backlog thresholds, token/abuse keys and vectors, exact origin/sender, distributed-login cutover, template parity, flags-off cleanup, and contradictory combinations in `servers/fastapi/api/main.py`, `servers/fastapi/api/runtime_capabilities.py`, `servers/fastapi/modules/jobs/workers/main.py`, and `servers/fastapi/tests/integration/test_account_lifecycle_readiness.py`; completion requires no reimplementation of T038/T039 configuration/capability primitives and one authoritative integrated pass/fail result.
- [ ] T110 Regenerate the checked-in API contract only through `servers/fastapi/scripts/generate_openapi_spec.py`, update `servers/fastapi/openai_spec.json`, and make backend/frontend contract tests cover every approved route/schema/error/cookie rule including public capabilities and authenticated password change; completion requires the generator `--check` mode and typed lifecycle adapter tests to pass.
- [ ] T111 Prepare pre-validation documentation and evidence checklists—without recording results—in `ARCHITECTURE.md`, `SECURITY.md`, and `TESTING.md`; completion requires implemented/current versus feature-flagged/legacy/disabled-roadmap wording, operator flags/secrets/readiness/rollback commands, SMTP exactly-once limits, and explicit automated versus human/controlled evidence producers while leaving final quickstart evidence to T121.
- [ ] T112 Run the focused identity/auth/admin/workspace/job/notification/security suites—including authenticated password-change and session-version races—then the full FastAPI pytest, compileall, migration graph, OpenAPI check, and disposable PostgreSQL/Redis integration gates specified in `TESTING.md`; completion requires exact pass/skip/failure evidence and no real provider or production resource.
- [ ] T113 Run the Next.js unit, i18n, canonical, locale/product E2E, and account-lifecycle component suites from `servers/nextjs/package.json`; completion requires EN/AR route/state/password-change parity, route loading/error boundaries, token privacy, safe navigation, account/settings separation, and automated accessibility evidence without claiming human acceptance.
- [ ] T114 Run Next.js ESLint and the production build with controlled local origins from `servers/nextjs/package.json`; completion requires strict TypeScript boundary checks and proves no lifecycle dependency entered the production bundle unexpectedly.
- [ ] T115 Run the root governance, architecture, localization, canonical, product metadata, brand, secret-scanner unit/full, Compose, and `git diff --check` gates from `package.json` and `TESTING.md`; completion requires exact reporting of every skipped or environment-blocked command and final review for unrelated Sprint 10.11+, payment, provider, dashboard, or canvas changes.
- [ ] T116 Rehearse staff/cohort rollout and ordinary rollback with fake SMTP/Redis/disposable databases, including flags off -> distributed-login cutover -> cleanup/vector readiness -> notification -> verification/recovery -> public signup, then disabling new issuance while consuming/expiring accepted challenges and continuing reclamation; record safe operator evidence in `artifacts/account-lifecycle/acceptance/rollout-rehearsal.json` for migration, backlog, sender/domain, privacy/legal, key retention, ambiguous delivery, workspace failure, and emergency-disable behavior without modifying final quickstart evidence.
- [ ] T117 [P] Execute the controlled SC-006 canonical-worker delivery measurement after T112-T116 and write `artifacts/account-lifecycle/acceptance/sc-006-delivery-run.json`; completion requires at least 100 accepted fake/staging messages, at least 99% terminal-delivered within 120 seconds, zero duplicate effective challenge generations, exact failed/skipped evidence, and no recipient/token/link/body/provider content.
- [ ] T118 [P] Execute the controlled SC-010 production-build usable-state measurement after T112-T116 and write `artifacts/account-lifecycle/acceptance/sc-010-ui-timing.json`; completion requires at least 20 cold-start samples per required public route/state family and locale, every sample at or below 2000 ms, configured-timeout recovery evidence, exact failures/skips, and no secret-bearing browser artifact.
- [ ] T119 Conduct the SC-001 human usability protocol after the converged build and write `artifacts/account-lifecycle/acceptance/sc-001-usability-matrix.csv` plus `artifacts/account-lifecycle/acceptance/sc-001-usability-summary.json`; completion requires at least 20 independent privacy-safe participants per locale and at least 95% separately in EN and AR below 120 seconds for registration and 300 seconds from message availability to Dashboard, with no fabricated or personally identifying result.
- [ ] T120 Conduct the BA-004 human bilingual/accessibility review after automated accessibility and locale gates and write `artifacts/account-lifecycle/acceptance/ba-004-human-bilingual-review.md`; completion requires recorded English product, fluent Arabic, and accessibility reviewer roles and explicit per-locale disposition for wording, meaning parity, bidi, RTL/LTR reading order, keyboard flow, visible focus, semantics, and assistive-technology behavior, with every blocker resolved or the gate reported failed.
- [ ] T121 Record the final post-validation evidence index only after T112-T120 in `specs/001-public-account-lifecycle/quickstart.md` and `artifacts/account-lifecycle/acceptance/README.md`; completion requires command/run IDs, artifact paths/hashes, threshold calculations, reviewer dispositions, and exact failures/skips, and forbids claiming readiness when any automated, controlled, or human gate is absent or failed.

**Final Checkpoint**: All seven stories, both databases, shared Redis controls, canonical jobs/outbox, EN/AR UX/email, migrations, compatibility paths, security invariants, rollback behavior, repository gates, controlled measurements, and human acceptance have the required recorded evidence. Public enablement remains an explicit operator decision after these gates.

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; T002-T004 may proceed in parallel with T001.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks every story. Within it, write the relevant test before its implementation; T008 depends on T005-T007, T010 on T009, T011-T013 on T008, T015 on T014, T017 on T016, T018 on T008/T015/T017, T020 on T019, T022 on T021, T024 on T023, T026 on T025, T029 on T028, T031 on T030, T033 on T032/T007, T035 on T034, T036 on T013/T034, T037 on T013/T033/T035/T036, and T039 on T024/T038. T013's lifecycle eligibility repository therefore exists before notification-worker integration, and T039's public capability projection exists before any public frontend task.
- **Phase 3 (US1)**: Depends on Phase 2 including T039; it is the MVP and establishes pending registration, verified activation, lazy/hourly reclamation, and the public registration/verification UI. T044 extends rather than duplicates T013's repositories.
- **Phase 4 (US2)**: Depends on Phase 2 and may begin alongside US1, but public email login cannot enable until T061 and T058 pass; its end-to-end public-email case uses an activated US1 fixture.
- **Phase 5 (US3)**: Depends on Phase 2 and may begin with a prebuilt verified-user fixture; full browser/session evidence uses US2's unified login/session path.
- **Phase 6 (US4)**: Depends on US1 registration/challenge ownership plus the Phase 2 notification foundation.
- **Phase 7 (US5)**: Depends on Phase 2 and may run alongside US1-US4; it must pass before enforcement/rollout.
- **Phase 8 (US6)**: Depends on US1 activation, US2 login, US3 session revocation, and US5 compatibility behavior; it owns authenticated password change and its account UI.
- **Phase 9 (US7)**: Depends on the public routes/states from US1-US4 and the account surface from US6; its test scaffolds/copy parity work may start earlier, but the story completes only after all flows exist.
- **Phase 10 (Convergence)**: Depends on all desired stories; T107 requires clean shadow evidence, T108 follows T107, T109 alone owns integrated readiness, T110 follows route/schema completion, T111 prepares documentation/checklists without results, T112-T116 run only against the converged implementation, T117-T120 produce controlled/human evidence only afterward, and T121 records the final evidence index after every producer completes.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 (MVP) ---------> US4 -----+
                       |                      |          |
                       +-> US2 -> US3 --------+-> US6 ---+-> US7 -> Convergence
                       |                                 |
                       +-> US5 --------------------------+
```

- **US1** is independently testable after shared foundations and is the suggested MVP.
- **US2** is independently testable with seeded public/legacy/admin users; its public-email E2E later consumes US1.
- **US3** is independently testable with a seeded verified-email user; session UX integrates with US2.
- **US4** deliberately reuses US1's pending/challenge state and never creates a separate resend token system.
- **US5** is an independent compatibility gate over current administrator/bootstrap behavior.
- **US6** integrates the completed identity/session/workspace semantics from US1-US3 and US5.
- **US7** is the bilingual/accessibility convergence layer for every prior public state; each UI story already owns its required EN/AR strings, and T035 alone owns the transactional-email catalog.

### Critical Path

`T001-T004 -> T005-T013 -> T014-T020 -> T021-T039 -> T040-T056 -> (T057-T064 || T081-T086) -> T065-T080 -> T087-T103 -> T104-T111 -> T112-T116 -> (T117 || T118) -> T119-T121`

The public enablement gate additionally requires T041-T043 (pre-hijack/retention/activation races), T058/T061 (distributed login authority and local limiter removal), T014/T018 (golden/cross-database token reconstruction), T087/T090/T092-T093 (password change and all-session invalidation), T104-T105 (adversarial privacy/security convergence), and T117-T121 (controlled/human acceptance plus final evidence record).

---

## Parallel Execution Examples

### Shared foundation

After Phase 1, separate owners may write these non-overlapping failing tests concurrently:

```text
T014 token wire/golden vectors
T019 normalization/password policy
T021 canonical operation controls
T023 CSRF/origin policy
T025 return destinations
T032 canonical system jobs
T034 notification transport/templates
```

Do not parallelize T006-T013 across the same model/migration/auth compatibility boundary, T021-T022 with login cutover T059-T061, or T032-T037 across the same job/notification persistence boundary without coordinating ownership.

### User Story 1

```text
T040 registration/consume contract tests
T041 attacker/victim pre-hijacking races
T042 fixed-lease reclamation races
T043 activation transaction failures
T051 frontend API/state tests
T053 token privacy tests
T055 registration/verification component tests
```

### Stories after the foundation

US2, a seeded-fixture version of US3, and US5 may proceed in parallel only where their files do not overlap; story implementation tasks that edit `messages/en.json` and `messages/ar.json` must serialize. US4 waits for US1's pending/challenge service; US6 waits for completed session/activation semantics; US7 test scaffolding can proceed early but final journeys wait for all routes.

---

## Requirement Traceability

Traceability is criterion-level. A listed task must implement, test, measure, or record the named requirement; related work is not counted as full coverage when the required evidence producer is absent.

### Functional requirements

| Requirement | Concrete implementation/test/evidence tasks |
| --- | --- |
| FR-001 | T040, T045, T049, T055-T056 |
| FR-002 | T001, T009-T010, T019-T020 |
| FR-003 | T005-T013, T041-T046 |
| FR-004 | T040, T045, T049, T104 |
| FR-005 | T041, T045, T074, T076, T078 |
| FR-006 | T005-T008, T044-T046 |
| FR-007 | T012, T057, T059-T060 |
| FR-008 | T006, T042, T044-T045, T048 |
| FR-009 | T043, T046, T049 |
| FR-010 | T043, T046 |
| FR-011 | T014-T018, T044, T066-T068 |
| FR-012 | T014-T018, T030-T031, T105 |
| FR-013 | T014-T015, T042, T044, T074 |
| FR-014 | T041, T044-T045, T074-T078 |
| FR-015 | T021-T022, T074, T076-T078 |
| FR-016 | T007, T032-T037, T047, T070 |
| FR-017 | T036-T037, T067, T075, T078 |
| FR-018 | T034-T035, T095, T103, T120 |
| FR-019 | T030-T031, T053-T054, T105 |
| FR-020 | T040, T049, T055-T056 |
| FR-021 | T057, T059-T064 |
| FR-022 | T057, T059-T060, T104 |
| FR-023 | T023-T024, T057, T060, T064 |
| FR-024 | T019-T020, T041, T043, T046, T066, T068, T082-T083, T087, T090 |
| FR-025 | T019-T020, T043, T046, T066, T068, T082-T083, T087, T090 |
| FR-026 | T065, T068-T069 |
| FR-027 | T014-T018, T066-T070 |
| FR-028 | T066, T068-T069 |
| FR-029 | T066, T068-T069, T104 |
| FR-030 | T066-T070 |
| FR-031 | T066, T073, T082, T087, T090, T092-T094 |
| FR-032 | T057, T067, T087, T090, T104 |
| FR-033 | T005, T065, T081, T085-T086 |
| FR-034 | T021-T022, T050, T058-T061, T069, T074, T077, T087, T090, T104 |
| FR-035 | T021-T022, T058, T074, T087, T090 |
| FR-036 | T023-T024, T050, T069, T077, T090, T104 |
| FR-037 | T025-T027, T052, T060, T064, T104 |
| FR-038 | T030-T031, T040, T049, T060, T069, T077, T090, T104, T110 |
| FR-039 | T030-T031, T053-T054, T105 |
| FR-040 | T028-T029, T048, T068, T090, T104 |
| FR-041 | T005-T013, T043, T046, T088, T091 |
| FR-042 | T081, T088, T091 |
| FR-043 | T040, T049, T057, T064, T088, T091, T104 |
| FR-044 | T051-T056, T062-T063, T071-T072, T079-T080, T092-T101 |
| FR-045 | T034-T035, T056, T063, T072, T080, T093, T095-T096, T103 |
| FR-046 | T056, T063, T072, T080, T093, T097-T103 |
| FR-047 | T051-T056, T062-T063, T071-T072, T079-T080, T092-T099 |
| FR-048 | T055-T056, T062-T063, T071-T072, T079-T080, T092-T101, T120 |
| FR-049 | T034-T035, T053-T056, T095-T105, T120 |
| FR-050 | T005-T013, T106-T108 |
| FR-051 | T005, T008, T012, T081, T108 |
| FR-052 | T009-T010, T106-T108 |
| FR-053 | T038-T039, T109 |
| FR-054 | T038-T039, T058, T061, T109, T111-T121 |
| FR-055 | T048, T109, T116 |
| FR-056 | T040, T049, T060, T069, T077, T087, T089-T090, T110 |
| FR-057 | T003-T004, T005, T014, T018-T021, T023, T025, T030, T032, T034, T036, T040-T043, T057-T058, T065-T067, T074-T075, T081-T082, T087-T088, T092, T095, T097, T099-T105, T106, T108, T110, T112-T121 |
| FR-058 | T028-T031, T048, T104-T105, T109, T121 |
| FR-059 | T038-T039, T087, T089, T092-T093 |
| FR-060 | T087, T089-T090, T092-T094 |
| FR-061 | T021-T024, T087, T090, T092-T093, T104, T110, T112 |

### Security invariants

| Requirement | Concrete implementation/test/evidence tasks |
| --- | --- |
| SR-001 | T012-T013, T024, T039, T046, T049-T050, T059-T060, T068-T069, T083-T090, T104 |
| SR-002 | T040-T041, T046, T049, T081-T086, T104 |
| SR-003 | T021-T022, T040, T045, T049, T057-T060, T065, T069, T074, T077, T104 |
| SR-004 | T014-T018, T030-T031, T036-T037, T053-T054, T105 |
| SR-005 | T014-T018, T041-T045, T066-T068, T074-T078, T104 |
| SR-006 | T019-T020, T041, T043, T046, T066, T068, T082-T083, T087, T090, T105 |
| SR-007 | T057, T066, T068, T073, T082, T087, T090, T092-T094, T104, T112 |
| SR-008 | T021-T022, T050, T058-T061, T069, T074, T077, T087, T090, T104, T109 |
| SR-009 | T023-T027, T050, T053-T054, T069, T077, T090, T104-T105 |
| SR-010 | T005-T013, T043, T046, T088, T091, T104 |
| SR-011 | T028-T031, T034-T037, T053-T054, T095, T103-T105, T115, T117-T121 |
| SR-012 | T030-T031, T040, T049, T060, T069, T077, T090, T104, T110 |
| SR-013 | T005-T013, T042, T044-T048, T106-T108, T116 |
| SR-014 | T038-T039, T048, T109, T116, T121 |

### Bilingual acceptance

| Requirement | Concrete implementation/test/evidence tasks |
| --- | --- |
| BA-001 | T034-T035, T056, T063, T072, T080, T093, T095-T096, T103 |
| BA-002 | T004, T055-T056, T062-T064, T071-T073, T079-T080, T092-T101, T113 |
| BA-003 | T040, T047, T056, T063-T064, T070, T072-T073, T080, T093-T101 |
| BA-004 | T034-T035, T053-T056, T095-T103, T120-T121 |
| BA-005 | T055-T056, T062-T063, T071-T072, T079-T080, T092-T101, T120 |
| BA-006 | T055-T056, T071-T072, T079-T080, T092-T102, T113-T114, T120 |
| BA-007 | T051-T056, T062-T063, T071-T072, T079-T080, T092-T101, T113 |
| BA-008 | T102, T115, T120 |

### Compatibility requirements

| Requirement | Concrete implementation/test/evidence tasks |
| --- | --- |
| CR-001 | T005, T008, T012, T057-T064, T081-T086, T108 |
| CR-002 | T019-T020, T057, T059-T060, T082-T083 |
| CR-003 | T012, T057, T059-T060 |
| CR-004 | T012, T023-T024, T057, T060, T064, T087, T089-T090, T110 |
| CR-005 | T005, T008, T081, T085-T086, T108 |
| CR-006 | T005, T008, T012, T081-T085, T088-T091, T108 |
| CR-007 | T005, T007-T008, T012, T039, T046, T088-T091, T109 |
| CR-008 | T012, T015, T017, T020, T046, T059, T068, T083, T086, T090, T110 |

### Measurable success criteria

| Criterion | Concrete implementation/test/evidence tasks |
| --- | --- |
| SC-001 | T004, T055-T056, T100-T101, T119, T121 |
| SC-002 | T040-T043, T046, T049, T081-T086, T104 |
| SC-003 | T021-T022, T040, T045, T049, T057-T061, T065, T069, T074, T077, T104 |
| SC-004 | T014-T018, T041-T044, T066, T068, T074-T078, T104 |
| SC-005 | T057, T066, T068, T073, T082, T087, T090, T092-T094, T104, T112 |
| SC-006 | T032-T037, T047, T067, T070, T075, T078, T117, T121 |
| SC-007 | T043, T046, T048, T088, T108 |
| SC-008 | T005, T008-T013, T042, T081, T106-T108 |
| SC-009 | T002, T004, T034-T035, T055-T056, T062-T063, T071-T072, T079-T080, T092-T103, T113-T114, T120-T121 |
| SC-010 | T051-T056, T062-T063, T071-T072, T079-T080, T097-T101, T114, T118, T121 |
| SC-011 | T003-T004, T028-T031, T034-T037, T053-T054, T095, T103-T105, T115, T117-T121 |

---

## Implementation Strategy

### MVP first

1. Complete Phase 1 and the full blocking Phase 2 with all public flags off.
2. Complete US1, including attacker/victim, fixed-retention, token, workspace rollback, and fake-delivery evidence.
3. Stop and validate the email-only registration -> verified first-password activation -> Dashboard journey independently.
4. Do not expose the MVP publicly until distributed login cutover, enforcement migration, security convergence, and rollout gates also pass.

### Incremental delivery

1. Deploy expand/backfill and compatibility seams with flags off.
2. Cut login to the canonical distributed controller and remove the local limiter while public email login stays off.
3. Add US1/US4 verification, US3 recovery, and US5 compatibility behind backend flags.
4. Add US6 account/session integration and complete US7 EN/AR/accessibility evidence.
5. Apply the enforcement revision after a clean shadow gate, run convergence, then enable notification, verification/recovery, and public signup in the approved order.

### Guardrails

- Never create a second user, authentication, browser-session, limiter, queue, scheduler, email-provider, workspace, or migration authority.
- Public registration accepts no password; only the current valid verification-token consumer can establish the durable User credential.
- A pending registration has a fixed 72-hour lease and no authenticatable or tenant authority; cleanup never selects a real User.
- Raw verification/reset tokens, email addresses, passwords/hashes, cookies, provider responses, rendered mail, and presentation content never enter logs, analytics, durable job payloads, audit metadata, or public errors.
- All protected identity, role, invitation, workspace, membership, and redirect decisions are re-authorized by FastAPI.
- Every implementation task stays within Sprint 10.10; presentation canvas geometry, branding, subscriptions, payments, credits, quotas, social login/SSO, organization redesign, and generation-form/provider work remain out of scope.

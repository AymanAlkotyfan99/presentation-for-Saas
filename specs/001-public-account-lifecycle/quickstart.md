# Validation Guide: Public Account Lifecycle

- **Feature**: `001-public-account-lifecycle`
- **Sprint**: 10.10 — Public Accounts, Verification, Recovery, and Unified Access
- **Status**: Planning artifact; commands and scenarios apply after implementation

This guide defines the minimum evidence needed to validate the implementation against [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), and the contracts in [contracts/](contracts/). It does not authorize use of production data, credentials, email recipients, or paid providers.

## 1. Safe validation environment

Use a disposable test environment with:

- a supported PostgreSQL database created only for this validation;
- Redis when exercising distributed rate limits and canonical notification jobs;
- the in-memory notification transport for automated tests;
- a local SMTP capture service only for manual template and transport checks;
- non-production signing keys dedicated to account verification and password reset;
- `NEXT_PUBLIC_URL` and API origin values set to the local test origins; and
- all account-lifecycle rollout flags disabled by default until the relevant scenario explicitly enables one.

Never use real customer addresses, production JWT/token keys, production cookies, or a live delivery provider. Test output, screenshots, traces, and fixtures must not contain raw verification/reset tokens, password values, cookie values, recipient addresses, or provider response bodies.

## 2. Baseline and migration validation

From `servers/fastapi`, validate the existing migration graph before applying feature revisions:

```powershell
uv sync --locked --dev
uv run --locked python scripts/check_migrations.py
uv run --locked alembic heads
```

Expected baseline: one Alembic head descended from `d4f6a8c0e2b3`. The feature must add two linear revisions: the additive/backfill revision followed by the constraint-enforcement revision. Validate both an empty database and a representative upgraded database containing an administrator, a primary superuser, a normal existing user, invitations, workspaces, memberships, and canonical job rows.

Required migration assertions:

- all current users retain their identifiers, password hashes, roles, active state, and workspace memberships;
- existing usernames are backfilled into the canonical login-identifier registry without collisions;
- pending-registration rows, owner-exclusive identifier reservations, fixed retention/redaction constraints, subject-bound challenges, and per-challenge delivery generations work identically on SQLite and PostgreSQL;
- existing normal administrator-created users use the planned compatibility semantics;
- primary/historical superuser treatment matches the grandfathering rule in the data model;
- no raw purpose token or plaintext recipient is present in database rows;
- the migration graph still has exactly one head;
- downgrade is tested only before lifecycle data is accepted; and
- once lifecycle data exists, operational rollback uses feature flags and draining rather than a destructive schema downgrade.

Run the repository's PostgreSQL migration smoke path against an explicitly disposable empty database after the revisions exist:

```powershell
$env:MIGRATION_TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/DISPOSABLE_DB"
uv run --locked python scripts/check_migrations.py
Remove-Item Env:MIGRATION_TEST_DATABASE_URL
```

## 3. Backend validation

Run the full backend suite required by [TESTING.md](../../TESTING.md), then the focused lifecycle, identity, workspace, notification, job, and security suites added by the implementation. The focused command should resolve to the actual test paths created during implementation; a representative grouping is:

```powershell
uv run --locked python -m pytest tests/integration/test_public_account_lifecycle.py tests/integration/test_auth_sessions.py tests/integration/test_workspaces.py modules/jobs/tests/test_account_notifications.py tests/security/test_public_account_security.py -q
```

Then run the exact complete FastAPI checks with disposable paths as required by `TESTING.md`:

```powershell
$env:APP_DATA_DIRECTORY = "C:\Temp\bayanly-tests\app-data"
$env:TEMP_DIRECTORY = "C:\Temp\bayanly-tests\temp"
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/Temp/bayanly-tests/test.db"
$env:DISABLE_ANONYMOUS_TRACKING = "true"
$env:DISABLE_IMAGE_GENERATION = "true"
uv run --locked python -m pytest --verbose --tb=short
uv run --locked python -m compileall -q api models services utils
uv run --locked python scripts/generate_openapi_spec.py --check
```

The backend evidence must cover:

| Scenario | Required observable result |
|---|---|
| Register a new normalized email | Generic accepted response; pending registration, pending-owned identifier, current verification challenge, notification, and system job/outbox commit atomically; no User, password/hash, session, or workspace |
| Register an equivalent normalized email while live | Same public status/body/timing; no User/credential; allowed delivery reuses the same token and does not extend the 72-hour lease |
| Register an email colliding with any canonical identifier | Generic accepted response; no second identity |
| Login for pending claim with any password | Dummy password work and the same generic invalid-credential response as absent; no session or verification-state disclosure |
| Incorrect password, unknown identifier, disabled account | Generic authentication failure after applicable dummy/real work without disclosing account state |
| Consume valid verification token with compliant password | Exactly one transaction creates the normal User/hash, transfers/verifies the email claim, provisions one personal workspace/owner membership, consumes the token, redacts the pending row, and emits safe audit data; session is issued only after commit |
| Concurrent consume with different passwords | Exactly one User/hash/claim/workspace winner; loser cannot replace the credential and receives safe already-completed state |
| Verification transaction failure | No partial User, hash, claim transfer, activation, membership, workspace, or token consumption; retry remains possible |
| Expired, malformed, failed-limit, or superseded verification token | Generic invalid/unavailable result; no state change and no secret in logs |
| Replay consumed verification token | Deterministic already-complete result; no second cookie, workspace, membership, or audit transition |
| Repeated resend requests | Public responses remain generic; cooldown/daily limits apply centrally; at most one current challenge remains; allowed live redelivery creates only a delivery generation |
| Attacker registers before/after victim | Attacker cannot persist a password, rotate the victim's unexpired link, extend retention, or activate without the emailed token; victim's token-submitted password is the only winning credential |
| Reclaim stale pending registration | At exactly 72 hours, lazy/hourly transition releases identifier, redacts email, revokes/suppresses child work, permits fresh registration, and never selects an actual user |
| Verification versus reclamation race | Fixed lock/CAS order permits fully committed pre-deadline activation or full abandonment, never both or partial state, on SQLite and PostgreSQL |
| Forgot password for existing/nonexistent/disabled identities | Indistinguishable public response; only eligible active account receives a current reset challenge and notification |
| Concurrent reset requests | Locks/constraints leave one current challenge; older tokens cannot win after supersession |
| Consume valid reset token | Password changes through the canonical password helper; `auth_version` increments; outstanding reset challenges are revoked; no automatic login |
| Replay/expire/malformed reset token | Generic invalid/unavailable result; password and session generation remain unchanged |
| Existing sessions after reset or revoke-all | Old cookies fail authorization because the JWT auth generation no longer matches |
| Authenticated password change succeeds | Current password verifies; distinct new password passes policy; hash replacement, reset-challenge revocation, audit, and one `auth_version` increment commit atomically; caller cookie is deleted; no replacement session is issued; every old cookie fails and the new password signs in |
| Authenticated password change is rejected | Incorrect current password, same old/new password, policy/mismatch, disabled account, rate denial, or stale session changes no hash, challenge, or `auth_version` state and returns only its stable safe code |
| Concurrent authenticated password changes | Two requests with one initial JWT generation have at most one hash/version winner; the loser cannot overwrite the credential and must authenticate again |
| Administrator create/reset user | Existing admin authority, password helper, workspace provisioning, and session invalidation remain canonical |
| Invitation acceptance | Username invitations remain compatible; email invitations require the verified normalized identity plus the separate invitation token |
| Cross-tenant probes | Workspace, invitation, audit, and job access cannot reveal another tenant's account or membership |
| Delivery provider failure | Registration/recovery state remains recoverable; bounded canonical retries or terminal ambiguity policy applies without duplicate effective tokens |
| Multi-instance login/lifecycle rate-limit race | Shared Redis enforces IP, privacy-safe identifier/combined failure, challenge, and global windows across instances; successful login clears only matching failure scopes; `Retry-After` is generic/bounded; production denies safely when coordination is unavailable |
| Public status capability projection | An unauthenticated client receives only the four product-availability booleans needed before lifecycle page rendering; no dependency reason, topology, configuration, account state, or identifier is exposed, while authenticated account fields remain additive and backend-authoritative |
| Canonical token vectors | Verification/reset golden vectors match exact context/token/digest in independent processes and after SQLite/PostgreSQL timestamp round trips; changing datetime precision/timezone cannot change token bytes |

## 4. Frontend validation

From `servers/nextjs`:

```powershell
npm ci
$env:PYTHON = (Resolve-Path '..\fastapi\.venv\Scripts\python.exe').Path
npm.cmd test
npm.cmd run check:i18n
npm.cmd run check:canonical
npm.cmd run test:locale-e2e
npm.cmd run test:product-e2e
npm.cmd run test:cypress
npm.cmd run lint
$env:NEXT_PUBLIC_FAST_API = "http://localhost:8000"
$env:NEXT_PUBLIC_URL = "http://localhost:3000"
npm.cmd run build
```

Run the lifecycle route tests in both `en` and `ar` for:

- `/register`;
- `/check-email`;
- `/verification-required`;
- `/resend-verification`;
- `/verify`;
- `/forgot-password`;
- `/reset-password`;
- `/recovery-complete`;
- login integration at `/`;
- identity/security controls under `/account`; and
- preserved presentation preferences under `/settings`.

Registration tests must prove only email/locale fields exist and password-like extra fields are rejected. Verification tests must prove the fragment is scrubbed before the accessible first-password form appears, the token remains only in transient memory through submission, validation errors leave the token unconsumed, and only a successful backend activation sets a session. Login must never map a pending claim to a verification-required account state.

The `/account` tests must cover current-password input, distinct new password and confirmation, incorrect-current/unchanged/policy/mismatch/rate/disabled/stale-session states, duplicate submission, and a concurrent winner. On success, protected client state is cleared and the user returns to localized sign-in because all sessions—including the caller—were invalidated; the frontend never attempts to mint or preserve a session.

For every public route, verify loading, success, validation failure, generic failure, rate-limited, expired/invalid, disabled-account-safe, and offline/provider-unavailable states where applicable. English must render LTR and Arabic RTL with equivalent meaning and actions. Validate logical spacing, `bdi` or equivalent isolation for email-like values, error association, focus movement, visible focus, keyboard-only completion, screen-reader status announcements, mobile widths down to 320 px, and zoom to 200%.

The automated accessibility run must include the planned `axe-core` checks and have no serious or critical violations in the lifecycle surfaces. Manual checks remain required for reading order, focus restoration, live-region behavior, and Arabic pronunciation/context.

## 5. Browser security scenarios

Validate these scenarios against the running local application:

1. Mutating lifecycle requests without the required JSON content type, `X-Bayanly-CSRF: 1`, exact trusted `Origin`, or acceptable fetch metadata are rejected before domain mutation.
2. A safe same-origin return path is preserved through login; absolute, protocol-relative, backslash-normalized, control-character, auth-loop, fragment-bearing, or privilege-inappropriate targets fall back safely.
3. Verification/reset token fragments are read only in memory, removed from browser history before further navigation, and never sent in referrers, analytics, server-rendered markup, query strings, screenshots, or error telemetry.
4. The root analytics integration remains inactive for secret-bearing routes.
5. Public registration, live/stale resend, and forgot-password requests remain enumeration-resistant across status, response body, headers, redirect behavior, and an approved timing envelope.
6. Login/lifecycle rate limits cannot be bypassed by alternating application instances, locale, route aliases, username/email forms, or superficial identifier formatting; raw identifiers never appear in Redis/log evidence and the local login limiter is absent from the final request path.
7. Browser cookies retain the existing secure production attributes and are never issued by failed/replayed verification or password-reset consumption.

## 6. Email and delivery validation

Using only the memory adapter in automation and a local capture server for manual checks, verify:

- each supported account email has an English and Arabic subject/body template;
- messages contain only the minimum account-lifecycle context and never a password, presentation content, internal path, tenant detail, or provider response;
- the URL uses the approved frontend origin and places the secret in a fragment;
- logs and traces use safe notification/challenge identifiers, not addresses or raw tokens;
- a deterministic message identifier is retained across a known-safe retry of one delivery; an allowed live resend creates a new delivery/Message-ID but reconstructs the exact same current verification token;
- permanent failures stop retrying; ambiguous delivery becomes terminal for that delivery rather than being sent blindly again; and
- a user can request a new delivery of the same live challenge after a terminal delivery outcome; a new challenge appears only after expiry and never survives pending reclamation.

For the production SMTP adapter, separately verify strict TLS, certificate/hostname validation, timeouts, approved address resolution/redirect behavior, credential redaction, and bounded provider responses. Do not invoke the production provider during repository validation.

## 7. Automated versus human/controlled acceptance evidence

Automated suites are required evidence for contracts, state machines, accessibility rules, privacy, and regressions. They are not a substitute for human usability/language/accessibility acceptance or controlled delivery/browser timing measurements. Prepare the evidence checklist before validation, but record final results only after the converged implementation and all producing runs complete.

Expected privacy-safe evidence under `artifacts/account-lifecycle/acceptance/`:

| Gate | Required artifact and protocol | Passing rule |
|---|---|---|
| SC-001 | `sc-001-usability-matrix.csv` contains pseudonymous participant ID, locale, registration-submit seconds, verification-to-Dashboard seconds measured from message availability, and completion flag; `sc-001-usability-summary.json` contains build/environment, date, owner, at least 20 independent participants per locale, aggregates, and result. No participant PII, address, password, token, cookie, screenshot, or free-form content. | Separately for EN and AR, at least 95% submit registration in under 120 seconds and complete message-available-to-Dashboard in under 300 seconds. |
| SC-006 | `sc-006-delivery-run.json` records build/configuration, date, owner, at least 100 accepted messages through disposable PostgreSQL/shared Redis/canonical workers/local capture, safe notification/challenge IDs or aggregates, accepted/delivered timing, retry/redelivery counts, duplicate-effective-generation count, and result. | At least 99% are `DELIVERED` within 120 seconds under the healthy profile and duplicate effective challenge generations equal zero. |
| SC-010 | `sc-010-ui-timing.json` records the production build/profile, date, owner, route/state family, locale, at least 20 cold-start samples for each required combination, the defined first usable heading/status/form/action mark, duration, and result. | Every recorded EN and AR public acknowledgement/token-state sample presents its usable state within 2000 ms; failure injection reaches the documented recovery action within its configured timeout. |
| BA-004 | `ba-004-human-bilingual-review.md` records the English product reviewer, fluent Arabic reviewer, and accessibility reviewer roles, build/date, and per-route/email-state findings for wording, meaning parity, bidi, RTL/LTR reading order, keyboard flow, visible focus, semantics, and assistive-technology-relevant behavior. Reviewers may overlap only when qualifications are recorded. | Every item for both locales is explicitly pass or has a resolved blocking finding; automated checks alone cannot mark the gate passed. |

The final evidence recorder cites each artifact, command/run identifier, threshold calculation, reviewer disposition, and any exact skip/failure. It must not invent missing measurements or turn an unavailable environment into a pass.

## 8. Rollout and rollback evidence

Before enabling any public surface, record evidence for the readiness gates in [plan.md](plan.md): migration health, absence of the local login request path, shared-Redis login/lifecycle evidence, pending-reconciliation backlog/retention evidence, exact token golden vectors, signing-key retention, queue/outbox health, delivery health, template parity, observability redaction, support runbooks, and per-route test results.

Exercise rollout in dependency order:

1. apply both schema revisions with all feature flags off;
2. enable internal/admin compatibility paths and shadow identifier checks;
3. cut login over to the canonical multi-window Redis controller on every instance and remove the local request path;
4. run lazy/hourly reclamation and token golden/cross-database gates with issuance off;
5. enable notification dispatch and monitor terminal/ambiguous outcomes;
6. enable verification/resend and recovery issuance for a controlled cohort;
7. enable public registration last; and
8. expand only while error, abuse, delivery, transaction, reclamation, and privacy metrics remain within approved thresholds.

Exercise operational rollback by disabling new registration/issuance first while leaving valid in-flight consume paths available through their maximum expiry plus clock-skew window. Keep lazy/hourly pending reclamation and redaction enabled, drain notification jobs, retain required token-key versions, and verify existing username login, administrator workflows, workspaces, invitations, and presentation behavior remain available.

## 9. Repository-wide completion checks

After implementation, run every mandatory command in [TESTING.md](../../TESTING.md) for the affected root, FastAPI, and Next.js scopes. At minimum, repository handoff must also include:

```powershell
npm.cmd run check:governance
npm.cmd run check:architecture
npm.cmd run localization:check
npm.cmd run canonical:check
npm.cmd run product:metadata:check
npm.cmd run brand:scan
python -m unittest scripts/tests/test_scan_secrets.py
python scripts/scan_secrets.py
docker compose config --quiet
git diff --check
git status --short
```

Review the final diff for accidental changes to presentation canvas geometry, unrelated providers, subscriptions/payments/credits/quotas, organization design, branding, generation forms, or dashboard surfaces. Any skipped check must be reported with its exact command and environment-specific reason.

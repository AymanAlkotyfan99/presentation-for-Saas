# Phase 0 Research: Public Account Lifecycle

- **Feature**: `001-public-account-lifecycle`
- **Date**: 2026-09-01
- **Repository branch inspected**: `dev` (the Spec Kit feature pointer names the feature; no Git branch was created or switched)

## Evidence Classification

| Classification | Repository-backed finding | Planning consequence |
| --- | --- | --- |
| **CURRENT IMPLEMENTATION** | `servers/fastapi/api/v1/auth/router.py`, `users.py`, and `models/sql/user.py` implement explicit username/password login on top of a custom FastAPI Users database, password helper, and versioned JWT strategy. The `presenton_session` cookie is the one browser-session authority. | Extend this foundation. Do not mount FastAPI Users' default verification/reset routes or create another user/session system. |
| **CURRENT IMPLEMENTATION** | Login uses a generic invalid-credential response, a dummy password hash for absent/inactive accounts, adaptive hash upgrades, `auth_version`, and activity checks. The route already has a canonical per-IP operation guard but also calls a raw client/username-keyed process-local five-failure limiter. | Preserve generic/dummy/hash/session behavior, move all login admission and failure scopes into the canonical distributed controller, and remove the local handler limiter before public email login enables. |
| **CURRENT IMPLEMENTATION** | The `user` table has no email; `hashed_password` is required; `is_verified` defaults true. The current manager's reset/verification secrets are intentional placeholders and public setup is absent. | Keep every pending registration outside `User`; create a normal user with its first canonical password hash only after email proof. Never interpret historical `is_verified` as verified email ownership or reuse placeholder secrets. |
| **CURRENT IMPLEMENTATION** | Authorized administrators create active normal username users and provision a personal workspace in one transaction; bootstrap provisions the primary administrator from deployment credentials. | Preserve admin creation, username login, bootstrap, and deployment recovery. Public registration can only create pending normal users. |
| **FEATURE-FLAGGED FOUNDATION** | `modules/workspaces` has deterministic personal workspaces and owner memberships, while workspace/RBAC flags default off. | Call the existing idempotent provisioner during public activation without claiming workspace/RBAC cutover. |
| **FEATURE-FLAGGED FOUNDATION** | `modules/jobs` owns SQL job truth, transactional outbox/inbox, Redis delivery, leases, idempotency, finite retry, and dead letters, but all job rows and worker authority are workspace-bound. | Extend the canonical job model with a narrowly registered system scope for pre-workspace lifecycle email. Do not invent a notification queue or borrow another tenant's workspace. |
| **CURRENT IMPLEMENTATION** | `api/operation_security.py` is the distributed-capable operation-control boundary. Production requires Redis; policies currently use one 60-second window, and login's additional failure limiter is process-local. | Extend the central policy model to multiple windows, privacy-safe identifier/combined scopes, and outcome recording. It becomes login's sole production authority; the process-local limiter is removed from the request path in Sprint 10.10. |
| **CURRENT IMPLEMENTATION / KNOWN GAP** | The Docker deployment is same-origin, cookies are `SameSite=Lax`, and CORS can use `NEXT_PUBLIC_URL`; there is no general Origin/Referer/CSRF check and CORS falls back to `*` when the origin is absent. | Add an auth-lifecycle same-origin mutation policy and make exact production origin readiness a public-feature prerequisite. Do not claim the repository-wide CSRF gap is closed. |
| **CURRENT IMPLEMENTATION** | The localized root `AuthGate` is the only login UI. Protected App Router layouts, account UI, safe return helper, session monitor, EN/AR catalogs, `lang`/`dir`, RTL styles, and tests already exist. | Keep `/` as the unified login and add public routes outside the protected presentation layout, using one account-lifecycle feature boundary and the same session/status contract. |
| **CURRENT IMPLEMENTATION** | Root layout initializes Mixpanel on every page and the global referrer policy is `strict-origin-when-cross-origin`. | Token handoff routes must be analytics-dark, use fragments, scrub history immediately, and set `no-referrer`. |
| **ROADMAP-ONLY** | Public signup, pre-account pending-registration retention/reclamation, email verification, recovery, notification/email adapters, lifecycle challenges, lifecycle flags, and lifecycle pages do not exist. | These are implementation scope, default-off, and require additive persistence and generated contract work. Pending registration must not become a second user or authentication system. |

## Security Clarification Amendments

The focused security review resolved four blocking issues without changing Bayanly's canonical authorities:

1. A pending submission is a temporary `PendingRegistration`, not a `User`; no user-selected password is accepted until a valid verification token is consumed.
2. Pending registrations have a fixed 72-hour lease, lazy correctness reclamation, hourly canonical reconciliation, immediate email redaction/claim release, and at most 30 additional days of non-PII terminal retention.
3. Unified login moves all IP, identifier, combined-failure, and global enforcement into the existing distributed operation controller; the process-local limiter is removed before public email login enablement.
4. Token derivation removes `issued_at` and freezes an exact binary context plus golden vectors, so reconstruction is independent of process, database, timezone, and timestamp precision.

The pre-implementation remediation also freezes four execution decisions: authenticated password change is part of Sprint 10.10 and invalidates every browser session; live verification resend is same-token redelivery; public unauthenticated capability serialization and lifecycle delivery-eligibility repositories are blocking foundations; and controlled/human acceptance evidence is distinct from automated test evidence.

## Decision 1: Identity Ownership and Module Boundary

**Decision**: Keep `models/sql/user.py`, the custom FastAPI Users password/JWT foundation, and the explicit `/api/v1/auth` router. Add `servers/fastapi/modules/identity` for lifecycle domain/application/persistence behavior. Auth routes remain transport adapters and call this module. FastAPI Users continues to supply the reviewed password helper, user-manager integration, and JWT strategy; its default verification/reset token routes and placeholder secrets remain unmounted.

**Rationale**: Bayanly already has one canonical user table and one browser-session authority. A domain module gives registration, challenge, reset, and account-state transactions an owning boundary without moving or duplicating established identity.

**Alternatives considered**:

- Mounting FastAPI Users' default registration/verification/reset routers: rejected because their identifiers, token secrets, errors, and transactions do not meet the approved contract.
- Building an independent auth service or session store: rejected as a direct architecture and constitution violation.
- Keeping all lifecycle logic in the router: rejected because transaction and security rules are reusable domain behavior, not transport behavior.

## Decision 2: Pending Registration, Account State, and Public Username Semantics

**Decision**: An unverified submission is a new `PendingRegistration` lifecycle record, not an authenticatable `User`. It contains a reserved normalized email, display email, locale, fixed `created_at`/`reclaim_after`, state, and claim generation, but no password/hash, session version, role, owner, workspace, or membership. A public `User` is inserted only by the valid verification transaction with its first adaptive password hash, verified email, active normal authority, and personal workspace.

Make the existing `username` column nullable for activated public users while preserving every existing value. Add explicit `account_origin` (`PUBLIC`, `ADMIN_PROVISIONED`, `GRANDFATHERED`), `account_state` (`ACTIVE`, `DISABLED`), `email_state` (`UNSET`, `VERIFIED`), `email_original`, `email_normalized`, `email_generation`, and `email_verified_at`. Keep `is_active` and `is_verified` as FastAPI Users compatibility fields synchronized by the identity application service; authorization never infers email ownership from `is_verified` alone.

Existing normal users backfill to `ADMIN_PROVISIONED`; the primary slot and anomalous historical superusers backfill to `GRANDFATHERED`. Activated public users have `username=NULL`. Backend serialization supplies a new `account_identifier` and retains `username` for legacy/admin accounts, preventing an invented internal username from leaking into the shell or workspace name.

**Rationale**: Separating a time-bounded pre-account record from `User` eliminates attacker-known credential pre-seeding and avoids making FastAPI Users tolerate an authenticatable row without an owned credential. Nullable username remains more honest and less error-prone than generating a hidden alias, while additive user state preserves current IDs, hashes, roles, and session versions.

**Alternatives considered**:

- Generate a hidden `public-<uuid>` username: rejected because current serializers and principal fields could expose it and make it an accidental login alias.
- Create a pending `User` with the registrant's password: rejected because an attacker can pre-seed a victim's email with a credential that survives later verification.
- Create a pending `User` with a random/sentinel or nullable hash: rejected because it needlessly puts unverified identities into the canonical authentication table and complicates the existing non-null password/FastAPI Users contract.
- Reuse `is_verified` as email state: rejected because all current rows default true without an email.
- Replace the current user model: rejected because it would create a second identity system and break ownership references.

## Decision 3: Global Login-Identifier Registry

**Decision**: Add `account_login_identifiers`, a unique registry whose row is owned by exactly one existing user or one live pending registration, with kind `EMAIL` or `USERNAME`. Backfill all existing usernames after Unicode NFC, trim, and case-fold normalization. Public registration atomically creates a pending registration and pending-owned email claim. Verified activation transfers that same locked claim to the newly created public user in the user/workspace transaction. Administrator creation and bootstrap rename atomically create/update user-owned username claims. The unified login resolver accepts only user-owned rows and treats pending-owned rows like absent identities after dummy password work. Activated public users receive only an email claim; nullable `username` creates no hidden alias.

**Rationale**: Separate unique indexes on user/pending email and `user.username` cannot prevent cross-column ambiguity under concurrent registration and administrator username creation. One reservable registry gives SQLite and PostgreSQL a portable, database-enforced global collision boundary. A pending owner is a temporary claim subject, not a second account or login identity.

**Alternatives considered**:

- Application-only checks across the two user columns: rejected because concurrent requests on different instances can race.
- PostgreSQL advisory locks: rejected as the sole guarantee because SQLite remains supported and every username mutation would have to share a lock protocol forever.
- PostgreSQL-only `citext`/exclusion logic: rejected because the migration must support SQLite and PostgreSQL.

## Decision 4: Email Validation and Normalization

**Decision**: Centralize normalization in `modules/identity/domain/email.py`: trim surrounding whitespace, reject controls, normalize Unicode to NFC, validate syntax with `email-validator` using `check_deliverability=False`, canonicalize the domain to lower-case IDNA ASCII, and case-fold the complete address for comparison. Store the trimmed/NFC display form separately from the normalized comparison form. Do not rewrite dots or plus tags. Promote `email-validator` from a transitive package to an explicit FastAPI dependency and lock it through `uv`.

**Rationale**: This implements the specification exactly, avoids network lookups during registration, and makes both application and migration normalization deterministic.

**Alternatives considered**:

- Lower-case only the domain: rejected because the approved contract requires full-address case folding.
- Provider-specific Gmail-style normalization: rejected because it changes user intent and creates false collisions.
- A hand-written email grammar: rejected because IDNA and internationalized mailbox validation are security-sensitive and an existing locked package already supplies the primitive.

## Decision 5: Registration and Activation Transactions

**Decision**: Registration and activation are separate transactions with a safe pre-account state. Registration accepts email and locale only; the verification consume request carries the first password and confirmation.

Registration owns one database transaction that:

1. applies canonical distributed IP and privacy-safe identity controls before identity lookup;
2. normalizes the email and locks any registry/pending row in the fixed claim-first order;
3. lazily reclaims an eligible expired pending registration when necessary;
4. inserts one `PENDING` pending registration and pending-owned email claim when unused, or selects the existing live pending registration without creating a user;
5. creates a challenge only if no eligible current challenge exists; otherwise an allowed repeat registration/resend schedules a new delivery of the same challenge/token without rotating it or extending retention;
6. inserts the notification-delivery row; and
7. submits one system-scoped notification job/outbox record through the same `AsyncSession` before committing.

It accepts/persists no password and creates no `User`, workspace, membership, ownership, credential, administrator authority, or browser session. A job/outbox insertion failure rolls a new pending registration back; a later provider failure leaves a recoverable pending record within its fixed lease.

Verification owns a second transaction. It parses the bounded token, validates password confirmation/policy, derives the adaptive hash in process memory, then locks the identifier claim, pending registration, challenge, and relevant activation rows in the documented fixed order. It revalidates token/purpose/expiry/binding/state and atomically creates the normal public `User`, transfers the email claim from pending registration to that user, persists the hash/verified email/active state, calls the current deterministic `ensure_personal_workspace`, consumes the challenge, revokes siblings, redacts the completed pending record, and appends lifecycle/workspace audit effects before one commit. Any insertion, uniqueness, provisioning, or audit failure rolls back user, credential, claim transfer, workspace, membership, and consumption, leaving the valid challenge retryable. The first winner may receive the existing JWT cookie after commit; a replay never receives a session or alter the winning credential.

Race outcomes are explicit:

- attacker registration before victim registration creates no credential; the victim receives the same current challenge and chooses the only durable password with the token;
- victim re-registration and attacker re-registration after it can consume budgets but cannot rotate the unexpired token, change a password, or extend retention;
- concurrent registrations converge on one pending claim/current challenge through the unique registry and row/state locks;
- after challenge expiry, the next eligible request atomically revokes the expired generation and creates one new challenge; every old link stays invalid;
- concurrent verification requests with different passwords permit one user/hash/claim/workspace winner; the loser is an already-completed safe response; and
- anyone who possesses the valid email token can set the first password, which is the intended proof-of-email capability boundary.

Pending retention is fixed and reclaimable:

- `reclaim_after` is exactly `created_at + 72 hours`, is written once, and is never extended by registration, resend, retry, or provider state;
- every verification `expires_at` is the earlier of its 24-hour limit and `reclaim_after`;
- registration, resend, and verification perform lazy reconciliation under the same claim → pending registration → challenge lock/state order, so identifier reuse never depends on a scheduler;
- an hourly bounded `account.pending.reconcile.v1` operation uses the already planned `SYSTEM_ACCOUNT_LIFECYCLE` canonical job authority for addresses that never return;
- reclamation atomically changes `PENDING` to `ABANDONED`, deletes/releases the pending-owned identifier row, nulls display/normalized email, revokes challenges, and suppresses not-yet-effective deliveries/jobs;
- actual users of every origin/state are outside the query predicate and cannot be selected by this path;
- PostgreSQL uses row locks plus unique/check constraints; SQLite uses its serialized writer transaction plus the same compare-and-set state/generation and uniqueness checks; and
- redacted activated/abandoned pending tombstones and terminal child challenge/delivery rows are physically deleted after at most 30 additional days once no job is non-terminal. Reclamation writes aggregate metrics/non-PII categories only, not a durable email oracle.

**Rationale**: No credential exists until email possession is proven, eliminating credential pre-hijacking rather than trying to repair an attacker-supplied pending hash. An active account without its personal workspace remains forbidden. The existing provisioner already uses deterministic user IDs and flushes without committing, so it fits the activation transaction.

**Alternatives considered**:

- Create the workspace at registration: rejected because pending registrations must have no workspace authority and the approved contract provisions on verified activation.
- Persist the registration password and supersede it on later registration generations: rejected because race ordering and unauthenticated replacement remain complex, and accepting a durable credential before email proof is unnecessary.
- Accept a password at registration but discard it: rejected as misleading UX and needless secret handling.
- Activate first and compensate workspace creation later: rejected because it permits active orphan accounts.
- Send email synchronously inside the registration transaction: rejected because network latency/failure would hold locks and cannot give durable bounded retry.

## Decision 6: Verification and Reset Token Design

**Decision**: Use dedicated, versioned deployment key material separate from the JWT signing secret, invitation pepper, abuse-key ring, provider secrets, and FastAPI Users placeholders. Each key is at least 32 random bytes. The exact ASCII wire form is `ba1.<purpose>.<kid>.<locator>.<secret>`, where purpose is `ev` or `pr`, `kid` matches `[A-Za-z0-9_-]{1,16}`, locator is unpadded base64url of the 16 RFC UUID bytes (22 characters), and secret is unpadded base64url of 32 bytes (43 characters). Parsers require exactly five components and the exact lengths/alphabet before lookup.

The HMAC-SHA256 message is the following concatenation with no separators or implicit serialization beyond those shown:

```text
UTF8("bayanly.account-token") || 0x00
|| u8(0x01)                                      # context/wire format version
|| u8(purpose)                                   # 0x01 EMAIL_VERIFICATION; 0x02 PASSWORD_RESET
|| u8(len(kid_ascii)) || ASCII(kid)
|| uuid_bytes(challenge_id)                      # 16 RFC/network-order bytes
|| u8(subject_kind)                              # 0x01 PENDING_REGISTRATION; 0x02 USER
|| uuid_bytes(subject_id)                        # 16 RFC/network-order bytes
|| u64be(binding_generation)                     # unsigned, range 0..2^63-1 by persistence rule
```

`issued_at`, `expires_at`, issue generation, locale, email text, timezone, and every database/string datetime representation are intentionally absent. Challenge UUID supplies per-issue uniqueness; purpose/subject/binding/key/version provide separation. Secret is `HMAC-SHA256(key[kid], context)`. Persist `kid` and a lowercase-hex `SHA256(ASCII(complete_token))` verifier; raw tokens and encrypted raw-token blobs are never persisted. Verification compares decoded/fixed values and digests in constant time.

Verification uses `subject_kind=PENDING_REGISTRATION`, the pending registration UUID, and its email-claim generation. Reset uses `subject_kind=USER`, the user UUID, and issuance-time `auth_version`. Verification expires in at most 24 hours and never later than pending `reclaim_after`; reset expires in at most 30 minutes. One partial unique index permits at most one current challenge per subject/purpose. An unexpired verification challenge is re-delivered rather than replaced by an anonymous resend. Expiry/reclamation/authorized invalidation may create a new generation and revoke older challenges. Consumption locks the row; exactly one transaction marks it consumed. Five failed secret validations revoke the challenge. Retiring key versions remain configured for the longest outstanding TTL plus clock-skew allowance; removing one is an explicit security revocation.

Golden vectors use the non-secret test key `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`, `kid=k1`, challenge UUID `00112233-4455-6677-8899-aabbccddeeff`, subject UUID `ffeeddcc-bbaa-9988-7766-554433221100`, and binding generation 42:

| Purpose / subject | Context hex | Expected token | Expected token digest |
| --- | --- | --- | --- |
| `ev` / pending registration | `626179616e6c792e6163636f756e742d746f6b656e000101026b3100112233445566778899aabbccddeeff01ffeeddccbbaa99887766554433221100000000000000002a` | `ba1.ev.k1.ABEiM0RVZneImaq7zN3u_w.RaT0UNMT7e7M-9mPsp_L8xkAR3gi7kU50QcwYvkWk8M` | `735ad8c0e21828252b5ba7025895c9a953dde8c267d7502c04b1a6bca661d3de` |
| `pr` / user | `626179616e6c792e6163636f756e742d746f6b656e000102026b3100112233445566778899aabbccddeeff02ffeeddccbbaa99887766554433221100000000000000002a` | `ba1.pr.k1.ABEiM0RVZneImaq7zN3u_w.yx45J0z61RA5iUENpyxHpk94xE1hZGWaIQbZxn9McJI` | `e1dba8e77763de61396d9ae75c2cf15d2b37c96b4097757807485132afed23e2` |

**Rationale**: A non-recoverable database verifier prevents database-only compromise from yielding bearer links, while deterministic PRF derivation lets a durable worker reconstruct/redeliver without placing a raw token in SQL or job payloads. Removing timestamps eliminates SQLite/PostgreSQL precision, timezone, driver, and formatting ambiguity; the explicit byte contract makes cross-process golden testing possible.

**Alternatives considered**:

- Persist raw or reversibly encrypted tokens: rejected because the contract forbids raw-at-rest tokens and no repository evidence justifies recoverable bearer storage.
- Put the raw token in the durable job: rejected by the constitution, job payload rules, and specification.
- Use self-contained JWT verification/reset tokens: rejected because one-time consumption, concurrent invalidation, resend replacement, and operator observability require authoritative server state.
- Reuse invitation tokens: rejected because their entity, purpose, authority, pepper policy, and workspace semantics are different.

## Decision 7: Password Policy and Session Revocation

**Decision**: Continue using `PASSWORD_HELPER` and its adaptive Argon2-capable `pwdlib` stack, including legacy PBKDF2 verification/upgrade. Centralize first/reset/authenticated-change/administrator-created password validation at 12–128 Unicode code points, allow spaces and password-manager output, reject controls, and compare a local SHA-256 digest against a reviewed, versioned common/compromised-password digest file. No candidate password leaves the process. Registration never receives a password; verified activation hashes the token holder's first password in process and persists it only in the winning transaction. Administrator creation/reset and authenticated password change call the same policy; login still accepts historical six-character values.

A successful public reset or administrator reset changes the hash and increments `auth_version` in one transaction. Reset invalidates all other reset challenges and does not auto-login. Add the minimum authenticated password-change operation at `POST /api/v1/auth/password/change`: the active browser principal submits current password, distinct new password, and confirmation under the common same-origin policy. The application locks the `User`, rechecks the JWT `auth_version` against persisted state, verifies the current password through `PASSWORD_HELPER`, rejects a new value that verifies against the current hash, applies the same 12–128/common-password policy, derives the new adaptive hash, revokes outstanding reset challenges, appends a safe audit event, and increments `auth_version` once in one transaction. Success deletes the caller's cookie, issues no replacement credential, and requires sign-in again. Incorrect current password, unchanged password, policy/confirmation failure, disabled state, stale generation, rate denial, or a losing concurrent request changes nothing; concurrent requests permit at most one hash/version winner.

A new authenticated `POST /api/v1/auth/sessions/revoke-all` increments `auth_version`, deletes the current cookie, and signs the user out everywhere; no session inventory is introduced. Deactivation makes `is_active=false`, sets `account_state=DISABLED`, rotates `auth_version`, and revokes challenges whenever an authorized path performs it. Password change and other credential mutations use the existing canonical operation controller with safe authenticated-user/IP/global scopes; no password-specific limiter is added. Existing bearer/API credential behavior remains separately governed; public users cannot create current administrator tokens.

**Rationale**: The existing JWT strategy already checks `auth_version` and activity on every read, so version rotation invalidates browser sessions without a second session table.

**Alternatives considered**:

- Add a session database solely for reset: rejected as a second session authority.
- Preserve the caller session by issuing a replacement JWT: rejected because selective session preservation would add race and credential-tracking complexity; Sprint 10.10 deliberately invalidates all browser sessions.
- Query an online breached-password service: rejected because it would transmit password-derived data and add an external availability/privacy dependency.
- Enforce composition rules: rejected by the approved password contract.

## Decision 8: Canonical System-Scoped Notification Jobs

**Decision**: Extend `modules/jobs` rather than create another queue. Add `QueueClass.NOTIFICATION` and an explicit `authority_kind` with existing `WORKSPACE` as the default and a code-registered `SYSTEM_ACCOUNT_LIFECYCLE` mode. System jobs have nullable workspace across job/outbox/inbox/attempt/event/dead-letter rows, no user/service actor, no public submission/listing route, and a system-only idempotency constraint. `submit_system_job` accepts only operations whose registry definition declares that exact authority. Workers skip membership lookup only for such registered definitions and require each handler to revalidate current lifecycle state immediately before effect.

The notification job payload is exactly `{notificationId}`. Before any notification worker is integrated, the identity persistence foundation exposes one authoritative challenge/subject/lease eligibility read contract over the same pending/challenge repositories used by registration, resend, consume, and reclamation. Workers call that contract immediately before effect and never infer eligibility from the durable payload or duplicate lifecycle queries. A second registered operation, `account.pending.reconcile.v1`, performs an hourly singleton, bounded-batch sweep using no identity-bearing payload; it invokes the same identity-domain reclamation transition used lazily by registration/resend/consume. Correct identifier reuse never depends on this cadence. Existing workspace jobs and router predicates retain their current behavior and non-null/default migration semantics.

**Rationale**: Pre-verification accounts deliberately have no workspace. Routing mail through an administrator or synthetic tenant would create cross-tenant coupling; a second background system would violate the canonical durable-work rule.

**Alternatives considered**:

- Use another user's or the primary administrator's workspace: rejected as a tenant-boundary violation and lifecycle dependency on administrator activity.
- Create a hidden synthetic workspace: rejected because it misrepresents global lifecycle work as tenant work and leaks into workspace invariants.
- Add a notification-specific queue/outbox: rejected as a competing durable status and retry system.
- Use process-local background tasks: rejected for production delivery because they are not durable or multi-instance safe.

## Decision 9: Minimal Transactional Email Boundary

**Decision**: Add `modules/notifications` with a small `TransactionalEmailTransport` protocol, deterministic renderer, application service, persistence model, job handler, production SMTP adapter, and in-memory capture adapter for tests/non-production. This module does not use the AI provider executor and has no marketing, preference, campaign, or user-selectable provider concepts.

SMTP is the initial provider-neutral production adapter. It uses operator-only configuration, strict TLS in production, bounded DNS/connect/read timeouts, DNS/address validation and connection pinning equivalent to the outbound-request policy, a bounded message size, and no internal retry loop. Credentials and provider replies never enter logs or durable state. An HTTP transport added later must use `utils/outbound_http.py`. The in-memory adapter exposes captured messages only to an injected test harness and has no production route or console output.

English and Arabic email content is owned by backend notification catalogs with identical keys/variables. A fixed renderer escapes every substitution into safe HTML and creates plain text separately. Messages contain only the action, expiry, ignore guidance, and reviewed sender identity—no echoed address, role, workspace, presentation, password, tracking pixel, or marketing content.

**Rationale**: No repository email abstraction exists. SMTP provides a vendor-neutral operational seam without extending the AI provider domain or choosing a permanent vendor.

**Alternatives considered**:

- Add email to `modules/providers`: rejected because that module's canonical families are AI text/image/search and its user-facing configuration semantics are wrong for identity delivery.
- Select a vendor SDK: rejected because the sprint explicitly avoids permanent vendor choice.
- Log development links: rejected because logs may not contain email addresses or raw tokens.

## Decision 10: Delivery Idempotency and Failure Semantics

**Decision**: Persist one `NotificationDelivery` per accepted delivery generation, unique by `(challenge_id, delivery_generation)`, and submit a canonical job with the notification UUID as its idempotency key. Initial issuance uses delivery generation 1. The invariant is **same-token redelivery while live**: an allowed registration/resend while the challenge remains current creates the next delivery generation for the same challenge/token and never changes challenge identity, bearer value, binding, expiry, or pending lease. A **replacement challenge occurs only after expiry/invalidation**. The handler locks delivery state, calls the shared authoritative eligibility repository, suppresses stale/revoked/consumed/expired/reclaimed subjects, derives the token only in memory, renders, and sends with a deterministic RFC `Message-ID` per delivery row.

Canonical jobs own at most three attempts and bounded backoff for each delivery. Failures known to occur before provider acceptance (DNS/connect/TLS and retryable SMTP 4xx) may retry. Permanent configuration/auth/rejection errors are terminal. An ambiguous handoff or worker crash after dispatch starts is recorded as `UNKNOWN_TERMINAL` and is not automatically resent; after cooldown the user may request a new delivery of the same still-current challenge, or a new challenge only if the old one expired. This prevents unbounded challenge generations and unauthenticated link-invalidation denial of service. SMTP cannot guarantee physical exactly-once copies after an ambiguous network outcome; deterministic per-delivery Message-ID and one effective challenge make duplicate copies equivalent, and this limitation is a rollout risk rather than a false guarantee.

**Rationale**: At-least-once jobs plus an external SMTP server cannot atomically commit delivery. Explicit ambiguous-terminal handling makes the trade-off observable and safe.

**Alternatives considered**:

- Blindly retry every timeout: rejected because it can duplicate mail.
- Never retry: rejected because known pre-acceptance temporary failures are safely retryable and the specification requires bounded recovery.
- Maintain adapter retries in addition to job retries: rejected because nested retry systems multiply effects.

## Decision 11: Distributed Abuse Controls

**Decision**: Extend the existing operation controller to support multiple explicit windows, outcome-aware failure counters, and anonymous IP/identity/combined scopes. Route middleware applies per-IP/global policies; identity application services apply distinct operation names keyed by purpose-separated `HMAC(account-abuse-key, normalized_identifier)` and by an HMAC of the canonical IP/identifier pair; token services use an HMAC of the challenge locator. Raw username/email never enters Redis keys or logs. Production authentication/lifecycle readiness requires the Redis control backend; development can use the existing bounded in-memory backend.

Defaults are:

- registration and forgot-password: 5 per IP per 15 minutes and 3 per normalized identity per hour;
- unified login admission: preserve the current canonical 10 submissions per trusted client IP per minute with burst 5 plus the existing explicit global ceiling;
- unified login failures: no more than 5 per privacy-safe IP/identifier scope per 5 minutes and 10 per privacy-safe identifier per 15 minutes; successful credential verification clears only those matching failure scopes after success and never refunds IP/global admission;
- verification/reset validation: 10 per IP per 15 minutes;
- failed secret validation: 5 per challenge, backed by an atomic durable failure counter that revokes the challenge;
- resend: 1 accepted delivery per identity per 60 seconds and 5 per identity per rolling 24 hours, with additional IP/global protection;
- global rates and concurrency: explicit operator-tunable ceilings no more permissive than the approved defaults without review.

All identity budgets apply before eligibility lookup. Repeated live pending registration uses the resend budgets, re-delivers the same challenge, and never accepts a password. Login admission occurs before lookup; after admission, pending/absent/inactive paths perform dummy password work and real eligible users use the canonical helper. A denial returns the greatest applicable bounded `Retry-After` with one generic rate-limit code and never states the limiting scope or account state.

Cutover is explicit: first extend/test the canonical Redis/memory contract and wire username login to distributed identifier/combined failure recording while public email login flags remain off. During a rolling compatibility deployment, old nodes may still apply their current local limiter in addition to the already-existing canonical IP guard, but that is temporary defense-in-depth, not claimed uniform authority. After all nodes use the new controller, remove `api/v1/auth/rate_limit.py`, its handler calls, and local-state tests in the same Sprint 10.10 implementation. Production readiness and public email-login enablement fail unless the local path is absent and multi-instance Redis tests pass.

**Rationale**: This is the only current multi-instance, fail-closed abuse boundary. Moving the existing login failure semantics into it resolves the SR-008 inconsistency; multi-window/outcome support is a necessary extension, not a second limiter.

**Alternatives considered**:

- Frontend cooldowns: rejected because clients can bypass them.
- Per-process counters: rejected because they are ineffective across instances.
- Raw email Redis keys: rejected because key inspection and telemetry would expose identity.

## Decision 12: Enumeration Resistance

**Decision**: Registration, resend, and forgot-password return HTTP 202 with the same bounded body for unused, active, live/stale pending, disabled, deactivated, username-only, primary-admin, and alias-collision cases. Validation failures for malformed input and rate-limit responses remain stable but do not reveal account state. Registration accepts no password, so every state follows the same normalization, keyed identity admission, bounded claim/reconciliation transaction shape, and asynchronous delivery boundary without credential hashing. Controlled fake-delivery timing distributions remain an explicit acceptance test; any practical oracle is a release blocker.

Pending registrations are never login subjects. Their email claims, absent identities, wrong passwords, disabled users, and ineligible aliases all return `AUTH_INVALID_CREDENTIALS` after the applicable dummy/real password work. Token holders may see purpose-safe expired/used/already-completed states but never an address, role, or tenant.

**Rationale**: Public flows need identical observable account-existence behavior while still giving a credential- or token-holder useful recovery states.

**Alternatives considered**:

- Return “email already registered”: rejected because it is an account oracle.
- Send distinct messages for disabled/admin accounts: rejected for the same reason.
- Block duplicate registration with 409: rejected because status itself would enumerate.

## Decision 13: CSRF and Browser Mutation Policy

**Decision**: Add one backend auth-mutation dependency/middleware for login, logout, registration, resend, verification consumption, forgot/reset, locale preference mutation, and session revocation. These routes accept JSON only, require `X-Bayanly-CSRF: 1`, and in production require an exact `Origin` equal to validated `NEXT_PUBLIC_URL`; `Sec-Fetch-Site` must be `same-origin` or `none` as defense in depth. Exact credentialed CORS replaces wildcard behavior when lifecycle flags are enabled. The frontend sends the common header through its account-lifecycle API adapter.

No separate CSRF-token/session store is introduced for this bounded same-origin family. The policy complements, rather than replaces, the current host-only HttpOnly `SameSite=Lax` cookie. Production startup/readiness fails closed if the canonical origin is missing, non-HTTPS, ambiguous, or inconsistent with proxy/cookie configuration.

**Rationale**: Strict origin plus a non-simple JSON/header request prevents cross-site form submission and preflight bypass while keeping FastAPI authoritative. It directly closes the public-lifecycle gap documented in `SECURITY.md` without pretending all unrelated mutation routes are remediated.

**Alternatives considered**:

- Rely only on `SameSite=Lax`: rejected because login and sensitive public token consumption need explicit cross-origin rejection.
- Add frontend-only CSRF checks: rejected because the frontend is not a security authority.
- Introduce a second CSRF session/token store: rejected as unnecessary for an exact same-origin deployment and larger than this feature.

## Decision 14: Safe Return Destinations

**Decision**: Extend `safeReturnPath` as the frontend pre-filter and add one backend `resolve_account_return_path` policy used by login and verification responses. Candidates must be local absolute paths, not scheme-relative/backslash-encoded, and must exclude API, `_next`, asset, logout, lifecycle/token, and internal routes. Fragments are stripped. The backend re-authorizes administrator/workspace destinations from the authenticated principal and current capabilities; unsafe or unauthorized values return the localized Dashboard. Email links carry no arbitrary return target.

**Rationale**: Current client validation prevents obvious open redirects but cannot authorize destinations. Returning a backend-approved path avoids trusting navigation state.

**Alternatives considered**:

- Redirect directly from a client `next` query: rejected because client checks are not authorization.
- Put a signed return token in email: rejected as unnecessary token surface.

## Decision 15: Frontend Route and Token-Handoff Architecture

**Decision**: Keep `/` as the unified login and create a public App Router group outside `(presentation-generator)` for `/register`, `/check-email`, `/verification-required`, `/resend-verification`, `/verify`, `/forgot-password`, `/reset-password`, and `/recovery-complete`. Their verification/reset outcome pages render success, already-completed/used, expired, invalid, rate-limited, delivery-delayed, loading, and generic failures as states of `/verify` or `/reset-password`. Interactive code lives in `features/account-lifecycle`; route files compose it. `/account` becomes the identity/security surface; `/settings` remains presentation preferences.

Email links use `/{locale}/verify#token=...` or `/{locale}/reset-password#token=...`. The verification route scrubs the fragment, then presents first-password/confirmation fields; it submits the in-memory token and password together so durable credential creation cannot occur without proof. Token routes disable Mixpanel/page-view initialization, set `Cache-Control: no-store` and `Referrer-Policy: no-referrer`, read a bounded fragment into memory, immediately call `history.replaceState`, delete the handoff value after the POST, and never use search parameters, storage, DOM/accessibility labels, console output, or telemetry. The first successful verification/credential activation may receive the current session cookie; reset returns to sign-in.

**Rationale**: Locale proxying already supports flat localized GET routes, and fragments do not reach HTTP access logs. A feature boundary avoids another auth UI while keeping token handling isolated from the protected shell and analytics.

**Alternatives considered**:

- Query-string tokens: rejected because they enter access logs, history, referrers, and analytics.
- Store tokens in session/local storage: rejected because it creates long-lived client bearer state.
- Put public pages under the protected presentation layout: rejected because unauthenticated users would be redirected before completing them.

## Decision 16: Bilingual Catalog and Accessibility Ownership

**Decision**: Every frontend user-story task that creates or changes a lifecycle surface also creates the required identical `accountLifecycle.*` English/Arabic keys and variables in `servers/nextjs/messages/en.json` and `ar.json`; a later convergence task only checks parity, unused keys, terminology, and RTL regressions and is never the first owner of story copy. The notification foundation is the single owner of the separate backend EN/AR email catalog for subjects and body fragments; later localization work validates or extends that catalog without recreating it. Extend the canonical localization check to validate both. All product routes inherit the existing locale proxy and root `lang`/`dir`. Addresses use bidi isolation and LTR value direction; layouts use logical CSS. No presentation renderer/canvas files are in scope.

Forms use semantic labels/instructions, correct autocomplete, `aria-invalid`/`aria-describedby`, a focused error summary, live status, visible focus, disabled/duplicate-submit controls, reduced motion, and deterministic timeout/recovery. Route-owned localized `loading.tsx` and `error.tsx` boundaries provide generic safe loading/failure/retry states without authorizing lifecycle access. Validation covers keyboard-only use, 320 CSS pixels, 200% text zoom, EN LTR, and AR RTL. Add `axe-core` as one explicit locked Next.js development dependency for automated WCAG A/AA checks. Automated checks do not satisfy the human gate: a recorded English reviewer, fluent Arabic reviewer, and accessibility reviewer must cover wording/meaning parity, bidi and reading order, keyboard/focus, semantics, and assistive-technology-relevant behavior in both locales.

**Rationale**: Existing localization and Cypress foundations cover routing/direction but do not provide account copy or a direct automated accessibility scanner.

**Alternatives considered**:

- Duplicate translated strings in components/templates: rejected because catalogs are canonical and parity must be checked.
- Reuse frontend catalog files directly from FastAPI at runtime: rejected because it couples backend deployment to frontend source layout.
- Treat RTL screenshots as sufficient: rejected because keyboard, semantics, zoom, and announcements are observable requirements.

## Decision 17: Invitation and Cross-Tenant Semantics

**Decision**: Extend the existing invitation record with normalized identity and identity kind. Existing invitations backfill as legacy `USERNAME`; new valid email invitations use `EMAIL`. Acceptance of an email invitation requires an authenticated account whose current `email_state=VERIFIED` and normalized email matches, plus the separate valid invitation token and existing workspace authorization. Legacy username matching remains only for grandfathered/admin-provisioned users. Registration/verification never auto-accepts an invitation or grants a non-personal membership.

**Rationale**: Identity is global while membership is tenant-scoped. Explicitly separating the two preserves cross-tenant isolation and the existing invitation authority.

**Alternatives considered**:

- Auto-accept an invitation after verification: rejected because possession of an email verification token is not possession of the invitation token.
- Continue matching all invitations to `user.username`: rejected because public users have no username and email ownership must be proven.

## Decision 18: Lifecycle Audit and Telemetry

**Decision**: Add a purpose-limited append-only lifecycle audit model under `modules/identity`, because existing workspace audit requires a workspace and pending registrations intentionally have none. It records safe account/actor UUIDs when available plus finite purpose, transition, outcome, rate/delivery category, and duration bucket. It never records a pending-registration UUID for anonymous cleanup, raw/normalized email, token/challenge secret/link, password/hash, cookie, rendered message, provider response, URL, path, presentation content, or arbitrary metadata. Rejected anonymous requests and abandoned-registration reclamation produce aggregate metrics/non-PII categories only, not durable identity records. Workspace creation continues to use the current workspace audit in the same activation transaction.

Add an allowlisted observability helper, lifecycle request-body/header/query filtering for Sentry, and frontend telemetry restrictions. Token pages remain analytics-dark until after scrub and never emit token-bearing properties.

**Rationale**: Extending workspace audit with null tenant rows would weaken its current workspace ownership semantics. A narrowly scoped global identity ledger is the minimum truthful boundary for pre-workspace transitions.

**Alternatives considered**:

- Put lifecycle audit into a synthetic workspace: rejected as false tenant attribution.
- Log raw identifiers for support: rejected by the constitution and privacy requirements.
- Persist every anonymous rejection: rejected because it creates a durable identity oracle and unnecessary personal data.

## Decision 19: Migration, Compatibility, and Rollback

**Decision**: Use two consecutive revisions on the single Alembic graph after current head `d4f6a8c0e2b3`:

1. **Expand/backfill revision**: add nullable user lifecycle/email fields; pending-registration, reservable-identifier, challenge, notification, and lifecycle-audit tables; job system-scope/nullable-workspace support; invitation identity fields; backfill existing accounts and user-owned username claims; add supporting non-destructive indexes. Abort with privacy-safe counts and affected user UUIDs if case-folded username claims collide.
2. **Constraint revision**: after the shadow collision checker passes, make user origin/state fields required, make username nullable, add user and pending-registration state/retention check constraints, normalized-email and login-identifier ownership/uniqueness, current-challenge subject partial uniqueness, per-delivery-generation notification idempotency, job authority/scope constraints, and invitation identity constraints.

Both revisions support SQLite and PostgreSQL and leave one head. Existing login/admin/bootstrap code is dual-read compatible between the revisions; all public flags remain off until the constraint revision and readiness checks pass. A preflight script reports collision categories/counts and safe UUIDs only and never merges, renames, emails, disables, or rewrites accounts.

Operational rollback disables new registration/resend/forgot issuance while preserving existing login/admin provisioning and allowing uncompromised accepted verification/reset tokens and notification jobs to finish or expire. Lazy/hourly pending reclamation remains enabled because it releases claims and removes PII rather than issuing access. `notification_delivery` stays enabled until accepted work drains. An emergency challenge-consumption kill switch is separate and used only for a security incident. Destructive schema downgrade is supported only before lifecycle/system-job rows exist; downgrade refuses otherwise. No rollback restores `/auth/setup` or reinterprets historical `is_verified`.

**Rationale**: Expand/backfill/enforce permits collision evidence and mixed-version deployment while retaining all existing data and safe rollback.

**Alternatives considered**:

- One destructive migration that rewrites usernames or merges identities: rejected because ambiguity must stop rollout, not alter accounts.
- Rely on startup `create_all`: rejected because Alembic is authoritative.
- Drop lifecycle tables during production rollback: rejected because accepted accounts/challenges/audit evidence would be lost.

## Decision 20: Feature Flags and Production Readiness

**Decision**: Add backend flags corresponding to `public_signup`, `email_verification`, `password_recovery`, and `notification_delivery`, all false by default. The shared foundation owns configuration parsing, dependency-health primitives, and a public unauthenticated `/auth/status` capability projection containing only these product-availability booleans—no dependency reason, deployment topology, account lookup result, or secret configuration. That public projection is complete before registration/verification/resend/recovery UI is built. Authenticated account-specific identity, role, recovery, workspace, and lifecycle fields remain owned by later account/session integration. Application services check flags in addition to route visibility. Issuance flags stop new work; valid accepted-token consumption remains available during ordinary rollback. A separate emergency disable can revoke/stop consumption.

The final integrated readiness evaluator—implemented only after all foundations and stories—combines those primitives and rejects contradictory production enablement unless the Alembic revisions are current, exact HTTPS `NEXT_PUBLIC_URL` and trusted proxy settings are valid, wildcard credentialed CORS is absent, Redis operation controls authoritatively cover login and lifecycle scopes, the process-local login path is absent, pending reclamation/backlog health is acceptable, durable jobs/notification queue are healthy, the token and abuse key rings are valid, token golden vectors pass, SMTP/sender/domain configuration passes health policy, and EN/AR templates pass parity. Foundation tasks do not claim integrated production readiness. Rollout order is schema with flags off, shadow evidence, distributed-login cutover, reclamation/golden-vector evidence, fake/staging delivery, staff accounts, controlled production observation, then anonymous signup.

**Rationale**: Safe defaults and dependency checks keep direct service calls and partial configuration from bypassing rollout gates.

**Alternatives considered**:

- Frontend environment flags: rejected because the browser cannot authorize or safely enable backend behavior.
- Disable all verification/reset consumption during normal rollback: rejected because it strands accepted users.

## Decision 21: API Compatibility and Generated Contracts

**Decision**: Preserve existing `/auth/status`, `/auth/verify` (session verification), `/auth/login`, and `/auth/logout`. Email verification uses the non-conflicting `/auth/email-verification/*` family. Login's preferred request field becomes `identifier`, while the existing `username` field is accepted as a compatibility alias when `identifier` is absent. Existing response fields and cookie behavior remain; new account/capability fields are additive. Routes use bounded Pydantic schemas and `StableAPIError`. After implementation, regenerate `servers/fastapi/openai_spec.json` only through `scripts/generate_openapi_spec.py` and update typed frontend adapters from the approved contract.

**Rationale**: `/auth/verify` already validates a browser session, and current clients depend on the login/status shapes.

**Alternatives considered**:

- Repurpose `/auth/verify` for email tokens: rejected because it would break session verification.
- Remove `username` immediately: rejected because current UI and compatible clients send it.

## Decision 22: Validation Strategy and Dependency Scope

**Decision**: Use unit tests for normalization, reservable-identifier collisions, password policy, exact token golden vectors/parsing, pending/user state machines, reclamation/redaction, templates, CSRF/origin, and redirects; SQLite integration for endpoint/transaction/reclamation behavior; disposable PostgreSQL for unique/concurrent attacker/victim registration, verification-with-different-passwords, cleanup, reset, authenticated password-change generation races, and migration behavior; cross-process plus SQLite/PostgreSQL token reconstruction tests; Redis integration for multi-instance login/lifecycle/password-change windows, outcome clearing, safe `Retry-After`, and notification/reconciliation jobs; injected fake/capture email only in CI; and Next unit/Cypress EN/AR, accessibility, keyboard, responsive, privacy, and safe-return tests. Run the full gates in `TESTING.md`, including OpenAPI generation check and migration graph, without real provider credentials.

Automated test output and human/controlled acceptance evidence have separate owners. After the converged implementation and automated validation, controlled runs create privacy-safe artifacts under `artifacts/account-lifecycle/acceptance/`: SC-001 records at least 20 independent participant results per locale and calculates the 95% thresholds separately; SC-006 records at least 100 accepted fake/staging deliveries and the two-minute/99% result without recipients or tokens; SC-010 records at least 20 cold-start production-build samples per required public route/state family and locale against the two-second threshold; and BA-004 records named reviewer roles and per-locale wording, parity, bidi, reading-order, keyboard, focus, semantics, and assistive-technology findings. A final evidence-recording task runs only after every producer and never fabricates a pass.

Only two direct dependency changes are planned and must be locked/audited: `email-validator` in the FastAPI manifest because application code imports it directly, and `axe-core` in Next.js development dependencies because SC-009 requires automated accessibility evidence. SMTP uses the Python standard library through an async-safe adapter.

**Rationale**: This maps each risk to deterministic evidence and follows the repository's owning test/tool chains.

**Alternatives considered**:

- Mock-only persistence/concurrency tests: rejected because SQLite cannot prove PostgreSQL locking and partial-unique behavior.
- Real transactional email in CI: rejected because quality gates must not invoke external paid/production services.

## Resolved Unknowns

All planning unknowns identified from the specification and repository inspection are resolved in the decisions above. The remaining items are implementation risks and rollout approvals, not missing product decisions:

- the canonical job/audit system-scope migration requires focused security review;
- SMTP has an unavoidable ambiguous-handoff/duplicate-copy risk, explicitly bounded above;
- the common-password digest list requires provenance/security approval before merge;
- production sender/domain, public origin, DNS/TLS, privacy/legal copy, and key-management inputs remain operator release prerequisites;
- exact timing-oracle and delivery SLO evidence must be measured in the controlled staging environment before public enablement.

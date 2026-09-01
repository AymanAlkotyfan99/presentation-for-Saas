# Feature Specification: Public Accounts, Verification, Recovery, and Unified Access

**Feature Identifier**: `001-public-account-lifecycle`

**Feature Branch**: None created; repository remains on `dev`

**Created**: 2026-09-01

**Status**: Approved — Ready for Implementation

**Input**: Sprint 10.10 specification for Bayanly's complete public account lifecycle, with no implementation work in this phase.

## Product Goal and Scope

Sprint 10.10 enables a visitor to create a normal Bayanly account, prove control of an email address, sign in through the same account entry point used by existing users, recover a forgotten password, and arrive in a correctly provisioned personal workspace. It preserves administrator-provisioned users, deployment bootstrap, backend authorization, owner isolation, and staged workspace/RBAC behavior.

Unless a statement is explicitly labeled otherwise, every user story, acceptance scenario, requirement, entity, and success criterion below describes the **ROADMAP-ONLY** Sprint 10.10 target. Repository claims use exactly these classifications: **CURRENT IMPLEMENTATION**, **FEATURE-FLAGGED FOUNDATION**, **LEGACY COMPATIBILITY**, and **ROADMAP-ONLY**.

### Repository Evidence and State Classification

| Classification | Repository evidence | Specification consequence |
| --- | --- | --- |
| **CURRENT IMPLEMENTATION** | `api/v1/auth/router.py` exposes one username/password login, status, session verification, logout, and locale-preference flow. A successful login issues the `presenton_session` cookie JWT; `auth_version` and `is_active` are checked on every JWT read. | Extend this identity and session foundation; do not create a second account or browser-session system. |
| **CURRENT IMPLEMENTATION** | Login normalizes username lookup, returns a generic invalid-credential error, performs a dummy hash for absent/inactive accounts, upgrades legacy password hashes, and is covered by bounded login controls. | Preserve or strengthen enumeration resistance, password-hash upgrades, and abuse protection for all new public flows. |
| **CURRENT IMPLEMENTATION** | `models/sql/user.py` is username-only and already contains `is_active`, `is_superuser`, `is_verified`, `auth_version`, and English/Arabic locale state. `is_verified` defaults to true. | Add email-ownership and public-account lifecycle state without misrepresenting the current `is_verified` value as proof of email ownership. |
| **CURRENT IMPLEMENTATION** | FastAPI Users is used through a custom user database, password helper, manager, JWT strategy, and authentication backend. The manager explicitly exposes no reset or verification routes and its placeholder reset/verification secret is not suitable for public exposure. | Reuse reviewed primitives where they meet this specification, but do not expose framework defaults or placeholder secrets as the product contract. |
| **CURRENT IMPLEMENTATION** | The public `/api/v1/auth/setup` route is absent and an integration test requires it to return 404. The first administrator is provisioned from deployment credentials under a database lock. | Do not restore or repurpose the removed setup claim flow. Public registration is a separate normal-user-only lifecycle. |
| **CURRENT IMPLEMENTATION** | The admin user route creates active, verified, non-superuser username/password users, provisions their personal workspace in the same transaction, and increments `auth_version` on administrator password reset. | Preserve administrator-created user support and its privilege boundary while defining explicit email/recovery semantics. |
| **FEATURE-FLAGGED FOUNDATION** | Workspace, membership, invitation, service-account, and RBAC modules exist, create deterministic personal workspaces, and enforce backend permissions when enabled; rollout flags default off and the legacy owner bridge defaults on. | Public activation must provision one personal workspace idempotently without treating staged workspace/RBAC rollout as already authoritative. |
| **LEGACY COMPATIBILITY** | Existing users sign in by username, legacy six-character passwords remain accepted at login, PBKDF2 hashes are upgraded after successful verification, and legacy administrator bearer keys still resolve through the common principal boundary. | Existing accounts, sessions, and operator recovery must continue to work during rollout; new passwords follow the stronger Sprint 10.10 policy. |
| **CURRENT IMPLEMENTATION** | The localized root route and `AuthGate` provide one English/Arabic login surface. Protected layouts, `SessionMonitor`, safe return paths, account/settings pages, role-aware shell links, and server-side admin guards already exist. | Add public lifecycle routes to the same localized shell and session contract; frontend guards remain navigation aids only. |
| **CURRENT IMPLEMENTATION** | English and Arabic catalogs have matching structures; locale-prefixed routing, `lang`/`dir`, logical-direction styles, account locale persistence, Arabic font support, and locale E2E foundations exist. | Every new state requires equivalent catalog, routing, accessibility, keyboard, responsive, LTR, and RTL evidence. |
| **CURRENT IMPLEMENTATION** | Central operation controls already route login through a distributed-capable per-IP policy in production, while the login handler separately retains a process-local five-failure compatibility limiter keyed by raw client/username input. | Sprint 10.10 must move login attempt/failure admission completely into the canonical distributed boundary, use privacy-safe identifier keys, and remove the process-local handler path before unified public email login is enabled. |
| **CURRENT IMPLEMENTATION** | One linear Alembic graph is authoritative; the current user migration deliberately removed an earlier email column, and no current user email, purpose-token, notification-delivery, verification, or self-service recovery persistence exists. | Sprint 10.10 requires additive migration and backfill work; roadmap wording is not evidence that any public lifecycle schema already exists. |
| **ROADMAP-ONLY** | Public self-registration, verified email ownership, verification resend, password recovery/reset, purpose-bound challenges, notification/email delivery, lifecycle feature flags, and public account pages do not exist in the current routes or migrations. | All of these capabilities are implementation scope for Sprint 10.10 and must default off until their rollout gates pass. |

### Architecture and Product Decisions

- **Backend authority**: FastAPI remains authoritative for identity, credential validation, email-ownership state, account status, password changes, session revocation, administrator authority, ownership, membership, RBAC, and workspace provisioning. Client state and route visibility never authorize an operation.
- **Public identifier and credential ownership**: Public registration collects email and locale only; it does not accept or persist a user-selected password. The bearer of a valid verification token supplies and confirms the first password during the winning activation transaction. Verified normalized email is the sign-in identifier for the resulting public account. The existing username remains a distinct legacy/admin-provisioned sign-in alias and display fallback.
- **Single login**: One localized sign-in page accepts an email for public accounts or the existing username for legacy/admin-provisioned accounts. There is no public administrator login and no client-selected role.
- **Account state**: Email ownership and account activation are separate concepts. An unverified submission is a non-authenticatable pending registration, not a `User`, and has no password hash, session, owner, workspace, or membership. A public `User` is created only after email proof and credential setup succeed atomically. Existing and administrator-created username-only accounts remain active under explicit `grandfathered` or `admin_provisioned` semantics; that status does not claim a verified email.
- **Administrator-created users**: The existing authorized administrator flow remains supported. Username-only users continue to use administrator-managed password recovery and are not eligible for public email recovery until a separately verified email-enrollment capability is approved. The primary administrator continues to use deployment-managed recovery.
- **Workspace provisioning**: The verified activation transaction creates the public `User`, transfers the reserved email identifier, persists the submitted password hash, creates exactly one deterministic personal workspace and owner membership, and consumes the challenge atomically. A failed transition remains retryable and cannot leave a user, credential, active account, or workspace orphan.
- **Notifications**: Transactional verification and recovery messages use a provider-independent delivery boundary, deterministic English/Arabic templates, bounded idempotent delivery, and a safe development/test sink. No permanent vendor choice or marketing-email capability is part of this sprint.
- **Pending-registration retention**: A pending registration has one fixed 72-hour lease from initial creation that registration and resend cannot extend. Verification challenges expire within both their normal 24-hour limit and that lease. Expired pending claims are reclaimed atomically and privacy-safe reconciliation removes their email data and releases the identifier without touching any active, verified, administrator-provisioned, or grandfathered user.
- **Anonymous conversion**: No anonymous work is claimed by signup in Sprint 10.10. Future claiming requires a separate possession-bound, verified, authorized, and auditable design.

## Clarifications

### Session 2026-09-01

- Q: How is pending-account credential pre-hijacking prevented? → A: Registration persists no user-selected credential and creates no authenticatable `User`; only the holder of a valid verification token can submit the first password, which is persisted atomically with user creation, identifier transfer, workspace provisioning, and activation.
- Q: How are abandoned pending registrations retained and reclaimed? → A: They have a non-extendable 72-hour live lease, are reclaimed lazily and by an hourly bounded canonical reconciliation job, release and redact their email claim atomically, and retain only non-PII terminal records for at most 30 additional days before physical cleanup.
- Q: What is the final production authority for unified-login abuse control? → A: The existing canonical operation-control boundary is the sole enforcing authority across instances; it owns IP, privacy-safe identifier, combined failure, and global budgets, while the old process-local limiter is removed from the request path before public email login can enable.
- Q: What canonical context is used to derive reconstructible verification/reset secrets? → A: A versioned binary contract uses fixed domain bytes, one-byte format/purpose/subject-kind codes, length-prefixed ASCII key ID, RFC UUID bytes, and unsigned 64-bit big-endian binding generation; `issued_at` and all database datetime serialization are excluded.
- Q: What authenticated password-change behavior completes the session-revocation contract? → A: A same-origin authenticated request verifies the current password, rejects reuse of that password, applies the canonical new-password policy, atomically replaces the hash and increments `auth_version`, revokes outstanding reset challenges, deletes the caller's cookie, and requires every browser session including the caller to sign in again.
- Q: What exactly may verification resend change while a challenge is live? → A: Resend performs same-token redelivery while live; `delivery_generation` may increase, but challenge identity, bearer token, expiry, binding, and the fixed pending lease do not change. A replacement challenge is allowed only after expiry or authorized invalidation.
- Q: What evidence is required for usability, delivery, timing, and bilingual acceptance? → A: Automated checks remain necessary but insufficient; controlled measurement artifacts and recorded human English/Arabic review must independently prove SC-001, SC-006, SC-010, and BA-004 before public enablement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register, Verify, Set a Credential, and Activate (Priority: P1)

A visitor submits an email, receives a localized verification message, proves control of the address, chooses the first password only on the verified token page, and reaches a localized Dashboard with a normal account and personal workspace.

**Why this priority**: Public account creation is the foundation for every other public Bayanly journey and must be safe from privilege escalation and duplicate provisioning.

**Independent Test**: With public signup and notification delivery enabled against a fake email provider, register a new address without creating a `User` or credential, consume the delivered verification link with a compliant password, and verify that exactly one normal active email-verified account is created, signed in through the common contract, and owns exactly one personal workspace.

**Acceptance Scenarios**:

1. **Given** an unused valid email, **When** a visitor submits registration in English, **Then** the visitor receives the generic check-email acknowledgement and one English verification message is scheduled without creating a `User`, accepting a password, or issuing a session.
2. **Given** an unused valid email, **When** a visitor submits registration in Arabic, **Then** the same outcome appears in Arabic RTL and the verification message and locale-preserving link are Arabic.
3. **Given** a live pending registration, **When** the email holder presents its valid unexpired verification token with a compliant confirmed password, **Then** exactly one normal `User`, adaptive password hash, verified email claim, active account, personal workspace, owner membership, and consumed challenge commit atomically.
4. **Given** a successful verification, **When** the user continues, **Then** the user enters the localized Dashboard through the single session contract and has no administrator capability.
5. **Given** an email already attached to an active account, **When** any visitor submits it again, **Then** the response has the same status, shape, wording class, and timing envelope as a new registration and no duplicate account is created.
6. **Given** an email reserved by a live pending registration, **When** registration or resend is repeated within policy, **Then** the response remains generic and a bounded delivery may resend the same current challenge without rotating the unexpired token, extending retention, or accepting a credential.
7. **Given** a valid verification token and compliant password, **When** user or personal-workspace creation fails before commit, **Then** no user, credential, identifier transfer, activation, membership, or token consumption commits and the same token can be retried safely.
8. **Given** two concurrent valid verification submissions carrying different compliant passwords, **When** both race, **Then** exactly one transition and its submitted password win, exactly one user/workspace/membership exists, and the other request returns an already-completed safe state without changing the credential.
9. **Given** an attacker registered a victim's email before or after the victim's own registration, **When** the victim obtains the current verification token and chooses a password, **Then** no attacker-selected password exists to survive activation and unauthenticated re-registration cannot replace the token or credential.
10. **Given** a pending registration reaches its fixed 72-hour reclaim deadline, **When** the same email is registered again, **Then** the stale claim is atomically abandoned, its email data is redacted and identifier released, every challenge/delivery is made ineligible, and a fresh pending registration may claim the address without revealing the cleanup.
11. **Given** verification and reclamation race at the lease boundary, **When** both transactions execute, **Then** row/state locking and uniqueness permit either a fully committed pre-deadline activation or a fully reclaimed registration, never both, and never delete an active or verified user.

---

### User Story 2 - Sign In Through One Account Entry Point (Priority: P1)

A verified public user or an existing administrator-provisioned user signs in through one localized page, and backend-returned authority determines the shell and protected capabilities.

**Why this priority**: A unified entry point prevents split identity products and preserves the backend as the only authorization authority.

**Independent Test**: Sign in a verified public user by email, a normal administrator-created user by username, and the bootstrap administrator by username; verify common session behavior and direct backend denial of administrator routes to the normal accounts.

**Acceptance Scenarios**:

1. **Given** a verified active public account, **When** the correct email and password are submitted, **Then** the common cookie session is issued and the localized Dashboard opens.
2. **Given** an existing active username-only user, **When** the correct username and password are submitted, **Then** login continues to succeed without requiring an email migration first.
3. **Given** the bootstrap administrator, **When** valid deployment-managed credentials are submitted, **Then** the same login surface is used and administrator capabilities are returned only by the backend.
4. **Given** an email reserved only by a pending registration, **When** any password is submitted at sign-in, **Then** the backend performs dummy password work, issues no session, and returns the same generic invalid-credential response used for an absent account; verification guidance remains available through the generic registration/check-email/resend journey rather than account lookup disclosure.
5. **Given** an absent account, wrong password, disabled account, or deactivated account, **When** sign-in is attempted, **Then** each case produces the same generic invalid-credential public response.
6. **Given** a normal authenticated account, **When** it directly requests an administrator route, **Then** the backend denies access even if the client route or UI is manipulated.
7. **Given** a safe requested destination, **When** sign-in succeeds, **Then** the destination is used only if it is local and authorized; otherwise the user reaches the localized Dashboard.
8. **Given** failed username or email logins alternate across two API instances, **When** the shared IP, identifier, or combined failure budget is reached, **Then** both instances return the same generic rate-limit class with a bounded safe `Retry-After`, no raw identifier appears in Redis/telemetry, and no process-local counter is the production authority.

---

### User Story 3 - Recover a Forgotten Password (Priority: P1)

A user with a verified recoverable email requests password recovery without revealing whether the account exists, uses one expiring reset link, chooses a compliant password, and invalidates earlier browser sessions.

**Why this priority**: Safe self-service recovery is essential for public accounts and is a high-risk account-takeover boundary.

**Independent Test**: Request recovery for existing and absent addresses, compare the public responses, consume a fake-provider reset link once, and prove that the new password works while every pre-reset browser JWT fails on its next protected request.

**Acceptance Scenarios**:

1. **Given** an active public account with a verified email, **When** forgot-password is submitted, **Then** the generic acknowledgement appears and one eligible localized reset delivery is scheduled.
2. **Given** an absent, pending, disabled, deactivated, username-only, or primary-administrator account, **When** forgot-password is submitted, **Then** the same public acknowledgement appears and no account state is disclosed.
3. **Given** a valid unexpired reset token and a compliant matching password, **When** reset is submitted, **Then** the password and challenge are changed atomically, all other outstanding reset challenges are invalidated, and the account's session version rotates.
4. **Given** a completed reset, **When** an old browser session makes its next protected request, **Then** it is rejected and the localized sign-in recovery state appears.
5. **Given** a completed reset, **When** the old password is used, **Then** sign-in fails; **When** the new password is used, **Then** sign-in succeeds.
6. **Given** an expired, malformed, wrong-purpose, or already-consumed reset token, **When** reset is attempted, **Then** no password or session state changes and a localized safe invalid/expired state offers a new recovery request.
7. **Given** concurrent reset requests for one account, **When** they race, **Then** at most one current reset challenge remains eligible and email effects stay within the delivery and throttle limits.
8. **Given** two concurrent submissions of the same valid reset token, **When** both race, **Then** exactly one password change succeeds and the other receives the safe used/invalid state.

---

### User Story 4 - Resend Verification and Recover from Delivery Problems (Priority: P2)

A visitor with a live pending registration can request another message after the cooldown, recover from an expired link or a temporary delivery failure, and never cause unbounded or duplicate delivery.

**Why this priority**: Email is an external dependency; the account lifecycle must remain usable and bounded when delivery is delayed or unavailable.

**Independent Test**: Use a fake provider that fails, retries, and recovers; confirm generic public responses, finite retry, idempotent delivery, resend throttling, same-token redelivery while live, replacement challenge only after expiry/invalidation, and successful verification after recovery.

**Acceptance Scenarios**:

1. **Given** a live pending registration and an expired verification link, **When** the link is opened, **Then** the localized expired state offers resend without creating or activating a user.
2. **Given** a live pending registration outside its cooldown with an unexpired current challenge, **When** resend is submitted, **Then** the public acknowledgement is generic, the same current token is scheduled for one bounded redelivery, and unauthenticated resend does not invalidate an earlier valid link.
3. **Given** an absent, active, disabled, or deactivated account, **When** resend is submitted, **Then** the same public acknowledgement appears and account state is not exposed.
4. **Given** repeated rapid resend requests, **When** the cooldown or daily budget is exceeded, **Then** delivery is suppressed, a safe localized rate-limited state appears, and no extra challenge is created.
5. **Given** a temporary provider failure, **When** an accepted delivery is retried, **Then** attempts are finite and idempotent and the user can request resend after the documented cooldown.
6. **Given** a consumed verification token, **When** it is reused, **Then** no second transition or workspace is created and the token holder sees the safe already-verified state.
7. **Given** a pending registration near its reclaim deadline, **When** resend is allowed, **Then** delivery never extends the deadline or produces a token valid beyond it; after reclamation, every earlier link is safely invalid.

---

### User Story 5 - Preserve Administrator-Provisioned Accounts (Priority: P1)

Administrators continue to create and manage normal username/password users, and existing users continue to sign in while public signup remains incapable of creating or elevating an administrator.

**Why this priority**: Public access must not break deployment bootstrap, existing tenants, operator recovery, or the administrator privilege boundary.

**Independent Test**: Upgrade a fixture with current administrator and normal users, use the existing authorized create/reset flows, and prove unchanged account IDs, roles, username login, workspace ownership, and session invalidation.

**Acceptance Scenarios**:

1. **Given** an existing current-schema user database, **When** the Sprint 10.10 migration is applied with public flags off, **Then** all account IDs, usernames, password hashes, roles, activity state, locale, session versions, ownership, and memberships are preserved.
2. **Given** an authorized administrator, **When** a username-only normal user is created, **Then** the account is active under `admin_provisioned` semantics, is not a superuser, and receives one personal workspace atomically.
3. **Given** a username-only administrator-provisioned user, **When** forgot-password is requested, **Then** the generic public acknowledgement appears and recovery remains administrator-managed.
4. **Given** an administrator password reset for a normal user, **When** it succeeds, **Then** the new-password policy applies and the user's prior browser sessions are invalidated.
5. **Given** the primary administrator, **When** public recovery or public registration is attempted with a matching identifier, **Then** no public path changes the primary administrator or reveals its existence.
6. **Given** any public registration payload containing password, role, superuser, workspace role, owner, or capability fields, **When** it is submitted, **Then** those fields are rejected and the backend can create only a non-authenticatable pending registration for a future normal account.

---

### User Story 6 - Maintain Unified Account, Session, and Workspace Behavior (Priority: P2)

A signed-in user sees account identity, email-verification state where applicable, locale, current session actions, authenticated password change, and server-issued role/workspace context consistently across Bayanly.

**Why this priority**: Registration and recovery are incomplete if the resulting identity diverges across the account page, application shell, sessions, or tenant context.

**Independent Test**: Complete verification, navigate through account and protected product routes in both workspace rollout modes, change the password using the current password, and verify that the hash and `auth_version` change atomically, all prior cookies including the caller fail, sign-in is required again, and identity, locale, owner, and workspace behavior remain consistent.

**Acceptance Scenarios**:

1. **Given** a newly verified account, **When** the Dashboard and account page load, **Then** both use the same backend identity and locale and show verified public-account status without exposing internal fields.
2. **Given** workspace rollout disabled, **When** the account uses existing owner-scoped product APIs, **Then** legacy owner isolation continues to apply and the personal workspace remains ready for later rollout.
3. **Given** workspace/RBAC rollout enabled, **When** the account selects or accesses a workspace, **Then** active membership and server-issued permissions are enforced for every protected operation.
4. **Given** a user invited by verified normalized email, **When** the user has not yet verified that address, **Then** no membership is granted; **When** verification succeeds and the invitation token is explicitly accepted, **Then** the invitation policy applies without replacing the personal workspace.
5. **Given** a legacy username-addressed invitation, **When** a grandfathered/admin-provisioned user accepts it, **Then** existing username matching remains available only through the documented compatibility path.
6. **Given** a user who signs out, **When** the current browser returns to a protected route, **Then** it is sent to the localized login recovery path; sign-out does not claim to revoke unrelated sessions.
7. **Given** a password reset or account deactivation, **When** any prior browser session is reused, **Then** backend session-version/activity validation rejects it regardless of frontend state.
8. **Given** an active authenticated account and the correct current password, **When** a distinct compliant new password and matching confirmation are submitted from the same origin, **Then** the canonical hash changes, outstanding reset challenges are revoked, `auth_version` increments exactly once, the current cookie is deleted, every prior browser session is rejected, and the user is directed to sign in again without a replacement session being issued.
9. **Given** an incorrect current password, a reused current password, a new-password policy failure, a mismatched confirmation, a disabled account, or a stale session generation, **When** password change is attempted, **Then** no password, challenge, session-version, or account state changes and only a stable bounded error is returned.
10. **Given** two concurrent password-change requests authenticated with the same session generation, **When** both pass initial transport validation, **Then** row locking and a persisted `auth_version` recheck permit at most one hash/version transition and the losing request cannot overwrite the winning password.

---

### User Story 7 - Complete Every Flow in English and Arabic (Priority: P1)

English LTR and Arabic RTL users can complete the same public-account journey with equivalent content, states, accessibility, keyboard behavior, and responsive layouts.

**Why this priority**: Bilingual parity is a product invariant, not a post-release translation task.

**Independent Test**: Run the full visitor-to-Dashboard and recovery journeys at narrow and desktop viewports in `/en` and `/ar`, using keyboard-only navigation and automated accessibility checks, and compare states and outcomes.

**Acceptance Scenarios**:

1. **Given** any public-account route or email, **When** it is opened in English or Arabic, **Then** the same actions, validation, status, and recovery choices are present in the selected language.
2. **Given** Arabic shell locale, **When** an auth page renders, **Then** application chrome is RTL, email addresses and tokens are bidi-isolated and readable, and presentation canvas geometry is unchanged.
3. **Given** keyboard-only use, **When** a user completes registration, verification, login, resend, forgot, or reset, **Then** focus order is logical, focus is visible, controls have accessible names, and no keyboard trap exists.
4. **Given** validation, rate limiting, success, or failure, **When** state changes, **Then** assistive technology receives an appropriate non-secret announcement and focus moves only when necessary.
5. **Given** a slow or failed request, **When** a public flow waits, **Then** a localized bounded loading state becomes a localized retry, resend, sign-in, or safe-exit state rather than an indefinite loader.
6. **Given** a narrow viewport or text zoom, **When** any account state renders, **Then** content remains readable and operable without horizontal loss of controls in both directions.

### Edge Cases

- An already registered normalized email receives the same public registration acknowledgement as an unused email; no duplicate account or pending registration is created.
- A pending registration has no password and cannot authenticate; every login attempt for it performs dummy password work and remains indistinguishable from an absent account.
- An attacker who submits a victim's email before or after the victim cannot persist or replace a password, rotate an unexpired verification link, or win activation without access to the victim's verification token.
- Concurrent registrations for one normalized email create at most one live pending registration and one current challenge; concurrent verification submissions persist only the winning token holder's password.
- A pending registration becomes reclaimable exactly 72 hours after initial creation; re-registration, resend, delivery retry, and provider delay do not extend that deadline.
- Lazy reclamation during registration/resend/consume and the hourly bounded canonical reconciliation job use the same state transition; a race with verification yields either activation or reclamation, never partial state.
- Reclamation immediately releases the identifier, redacts stored email values, revokes challenges, suppresses undelivered notifications, and leaves only non-PII terminal records eligible for physical deletion after 30 days.
- Active, verified, disabled actual users, administrator-provisioned users, and grandfathered users are never candidates for pending-registration reclamation.
- An expired verification token cannot activate the account and offers resend.
- A consumed verification token cannot replay activation or workspace provisioning; it resolves to a safe already-verified state.
- Repeated verification requests inside the cooldown or daily budget do not create additional challenges or delivery effects; an allowed resend of a live challenge re-delivers the same token rather than rotating it.
- An expired reset token cannot change password or session state and offers a new recovery request.
- A reused reset token cannot change the password a second time.
- Password reset rotates the account session version so all earlier browser JWTs fail on their next protected request.
- Existing and newly administrator-created username-only accounts remain active under explicit non-email-verification semantics and retain administrator-managed recovery.
- Public registration can never set `is_superuser`, administrator role, workspace role, owner ID, or capability state from client input.
- If user creation, credential persistence, identifier transfer, activation, and personal-workspace provisioning cannot all commit, none commits and the verification token remains safely retryable.
- Email delivery failure leaves the account pending, performs bounded idempotent retries, and preserves a later resend path.
- Multiple rapid signup, resend, recovery, login, and token-validation requests consume the applicable per-IP and privacy-safe per-identity budgets.
- Successful login clears only the matching distributed failure scopes after credential verification; it does not refund the general IP/global admission budget or expose which scope was limited.
- Malformed, truncated, oversized, wrong-purpose, or incorrectly encoded tokens produce bounded safe errors without stack traces or database diagnostics.
- Token derivation produces identical bytes and bearer values across processes, SQLite, and PostgreSQL; timestamps control eligibility in database state but never participate in cryptographic derivation.
- Disabled or deactivated accounts cannot log in, verify, resend, or recover; outstanding challenges are ineligible and prior sessions are rejected.
- Concurrent reset requests leave at most one current reset challenge; concurrent consumption permits only one password change.
- An authenticated password change requires the current password, rejects a new password equal to the current password, applies the same new-password policy, and never issues a replacement session cookie.
- Incorrect-current-password, policy, confirmation, disabled-account, rate-limit, and stale-session failures leave the hash, reset challenges, and `auth_version` unchanged and expose no password or internal state.
- Concurrent authenticated password changes lock and recheck the user/session generation so exactly one request can replace the hash and increment `auth_version`; every cookie from the prior generation, including the winner's caller cookie, becomes invalid.
- Case, Unicode, whitespace, and internationalized-domain variants of the same normalized email cannot create ambiguous or duplicate accounts.
- A public email that collides with an existing case-insensitive username login alias is treated as unavailable without disclosing the collision and requires administrator remediation.
- An invitation cannot substitute for email verification, and verification cannot auto-accept a membership without the separate valid invitation token and backend policy.
- Rollback disables new submissions while allowing previously accepted, uncompromised challenges to complete or expire safely.

## Requirements *(mandatory)*

### Functional Requirements

#### Identity and Account Lifecycle

- **FR-001**: The system MUST provide public registration that accepts a valid email and supported locale only; it MUST create a non-authenticatable pending registration rather than a `User`, MUST NOT accept or persist a user-selected password, and MUST NOT issue a session, workspace, membership, ownership, or product authority before verified activation.
- **FR-002**: The system MUST normalize email by trimming surrounding whitespace, applying Unicode normalization, case-folding the complete address for comparison, and canonicalizing the domain representation; it MUST reject invalid/control-character addresses and MUST NOT apply provider-specific dot or plus-tag rewriting.
- **FR-003**: The system MUST enforce one global account per normalized email and MUST prevent ambiguity between a normalized email and any existing case-insensitive username login alias, including under concurrent submissions.
- **FR-004**: Public registration MUST return the same accepted response class, schema, and non-identifying message for unused, active, pending, disabled, deactivated, and login-alias-colliding identifiers.
- **FR-005**: A repeated eligible registration or resend for a live pending email MAY schedule a bounded redelivery of the same unexpired current challenge but MUST NOT accept or persist a password, rotate the valid challenge, extend the fixed pending-retention deadline, create a `User`, or reveal pending state; only expiry, reclamation, binding change, authorized security action, or successful consumption may supersede that challenge.
- **FR-006**: Pending registration, verified public-user creation, email ownership, administrator provisioning, activity/deactivation, and superuser authority MUST be represented as distinct states or invariants so an unverified submission is never an authenticatable account and `is_verified` alone is never treated as proof of email ownership.
- **FR-007**: Public accounts MUST use verified normalized email as their sign-in identifier; the existing username MUST remain a legacy/admin-provisioned sign-in alias and display fallback, not a second public registration identity.
- **FR-008**: Pending registrations MUST have no `User`, password hash, session, authenticated product access, workspace role, administrator capability, API credential, ownership authority, or invitation acceptance and MUST be ineligible for login resolution. Each MUST have a fixed `reclaim_after` exactly 72 hours after initial creation that no anonymous request or delivery attempt can extend.
- **FR-009**: Valid verification MUST require a compliant confirmed password and atomically consume the challenge, create exactly one normal public `User`, persist its adaptive password hash, transfer the reserved email identifier, record email ownership, activate the account, create or reconcile exactly one personal workspace, and create or reconcile exactly one active owner membership.
- **FR-010**: If any part of verified user creation, credential persistence, identifier transfer, activation, audit, or personal-workspace provisioning fails, the system MUST roll back the complete transition, preserve a retryable valid challenge when safe, and avoid duplicate users, credentials, identifiers, workspaces, memberships, or audit effects.

#### Verification and Notification Delivery

- **FR-011**: Verification challenges MUST be purpose-bound to email verification and one live pending-registration/email-claim generation; reset challenges MUST bind to one active user and credential generation. Both MUST carry issued/expiry/consumed/revoked state, use at least 256 bits of unpredictable secret material or an equivalent reviewed security level, and derive reconstructible secrets from one frozen database-independent binary context. That context MUST exclude `issued_at`, `expires_at`, locale, email text, default datetime serialization, timezone formatting, and database timestamp precision.
- **FR-012**: Only a non-recoverable verifier or equivalent protected form MAY be persisted for a challenge; raw verification/reset tokens MUST NOT be stored in account rows, challenge rows, job payloads, audit records, logs, analytics, traces, or public errors.
- **FR-013**: A verification challenge MUST expire no later than 24 hours after issuance; operators MAY shorten but MUST NOT extend that limit without security review.
- **FR-014**: At most one verification challenge per live pending-registration/email-claim generation MAY be current. Registration/resend MUST re-deliver the same current token while it remains unexpired and eligible; only after expiry or another authorized invalidating transition may a new challenge replace it, and successful consumption MUST invalidate every remaining challenge for that pending registration.
- **FR-015**: Verification resend MUST use the same generic public acknowledgement for all account states, enforce a minimum 60-second cooldown and no more than five accepted resends per normalized identity in 24 hours, never extend pending retention, never issue a token beyond `reclaim_after`, and never disclose whether delivery occurred.
- **FR-016**: Transactional email delivery MUST be provider-independent, idempotent by notification purpose/generation, finite in attempts and backoff, and compatible with the canonical durable-work boundary; a queued delivery reference MUST contain stable IDs rather than raw email, raw token, provider credential, or rendered message content.
- **FR-017**: An accepted pending registration or challenge MUST remain in a safe non-authenticatable state through temporary provider failure; retries and redeliveries MUST not create duplicate effective challenges, and terminal delivery failure MUST be observable to operators without exposing recipient or content.
- **FR-018**: Verification and recovery emails MUST provide deterministic English and Arabic plain-text and safe-HTML content, use the reviewed Bayanly sender/domain, include only the action and expiry guidance needed, and contain no password, role, workspace, billing, presentation, tracking pixel, or marketing content.
- **FR-019**: Token-bearing links MUST prevent raw tokens from entering server/proxy access URLs, referrers, browser history after handoff, analytics initialization, or long-lived client storage; token submission MUST occur only to the authoritative same-origin backend.
- **FR-020**: Verification pages MUST provide localized success, already-verified, expired, invalid/malformed, rate-limited, loading, delivery-delayed, and generic-failure states without returning stored account identifiers.

#### Login, Passwords, Recovery, and Sessions

- **FR-021**: Bayanly MUST expose one localized login experience and one backend authentication contract that resolves only active user-owned identifier claims, accepting verified email for public users and the existing username alias for legacy/admin-provisioned users.
- **FR-022**: Pending-registration identifier claims MUST NOT be resolved as login accounts. Any login attempt for a pending, absent, wrong-password, disabled/deactivated, or ineligible identifier MUST perform the applicable dummy/real password work and return one generic invalid-credential response without disclosing verification state.
- **FR-023**: Successful browser login MUST preserve the current server-issued HttpOnly cookie-session contract, same-origin credential behavior, `SameSite=Lax`, path `/`, bounded lifetime, production `Secure` behavior, and backend activity/session-version validation.
- **FR-024**: The first public password MUST be accepted only with a valid verification token and persisted only in the atomic verified-activation transaction; first, reset, authenticated-change, and administrator-created passwords MUST use the existing reviewed adaptive one-way password helper. Current legacy hashes MAY be accepted only for compatibility and MUST be upgraded after successful credential verification without logging either password or hash.
- **FR-025**: Every first, reset, authenticated-change, or administrator-created password MUST be 12–128 Unicode characters, permit password-manager output and spaces, avoid arbitrary composition rules, and reject the approved local common/compromised-password blocklist without transmitting candidate passwords to a third party.
- **FR-026**: Forgot-password MUST accept an email and return the same accepted response class, schema, and message for recoverable, absent, pending, username-only, disabled, deactivated, and primary-administrator accounts.
- **FR-027**: Reset challenges MUST be purpose-bound to password reset, bound to one active recoverable account and credential generation, meet the token protections in FR-011/FR-012, and expire no later than 30 minutes after issuance.
- **FR-028**: A valid reset MUST atomically validate the policy, replace the password hash, consume the reset challenge, invalidate all other reset challenges, and rotate the account session version so every earlier browser session is rejected.
- **FR-029**: Expired, malformed, wrong-purpose, revoked, or consumed reset challenges MUST NOT change the password, session version, account status, or audit outcome beyond a safe failed-attempt event.
- **FR-030**: Concurrent recovery requests MUST leave at most one current reset generation and bounded email effects; concurrent consumption of one reset challenge MUST permit exactly one successful password change.
- **FR-031**: Normal sign-out MUST end the current browser session and route to the localized login state without claiming to revoke other sessions; password reset, administrator reset, authenticated password change, and deactivation MUST invalidate all existing browser sessions for that user, including the caller's current browser session when applicable.
- **FR-032**: Disabling or deactivating an account MUST make all sessions and outstanding verification/reset challenges ineligible on their next authoritative check without exposing the account state publicly.
- **FR-033**: The primary administrator MUST remain deployment-provisioned and deployment-recoverable; public signup, verification, resend, and forgot/reset flows MUST NOT create, elevate, reset, rename, or reveal it.

#### Abuse, Public Errors, Privacy, and Tenant Safety

- **FR-034**: Login, signup, verification, resend, forgot/reset, authenticated password change, and token-validation operations MUST use the existing canonical distributed-capable abuse-control boundary with separate per-IP, privacy-safe normalized-identity or safe authenticated-user, combined scopes where applicable, per-challenge where applicable, and global budgets. The process-local login limiter MUST be removed from the enforcing request path before public email login is enabled and MUST NOT remain a second or final production authority.
- **FR-035**: Default anonymous budgets MUST be no more permissive than five signup/recovery submissions per IP per 15 minutes, three per normalized identity per hour, ten token validations per IP per 15 minutes, five failed validations per challenge, and the resend limits in FR-015. Login MUST retain the current canonical ceiling of ten submissions per trusted client IP per minute with burst five, add no more than five failed attempts per privacy-safe IP/identifier scope per five minutes and ten failed attempts per privacy-safe identifier per 15 minutes, and retain an explicit global ceiling. Authenticated password change MUST allow no more than five failed current-password attempts per safe user/IP pair per 15 minutes plus explicit IP/global ceilings. Operators MAY tighten these values; loosening requires review.
- **FR-036**: Every cookie-authenticated account mutation and every token-consumption submission MUST enforce the reviewed same-origin/CSRF policy and MUST reject cross-origin mutation attempts even when client UI controls are bypassed.
- **FR-037**: Return destinations MUST be local, non-scheme-relative, non-API, non-internal paths and MUST be re-authorized after login/verification; untrusted or unauthorized destinations MUST fall back to the localized Dashboard.
- **FR-038**: New lifecycle APIs MUST use stable non-secret error codes and bounded response schemas that allow localized frontend messages without exposing SQL errors, exception text, token state beyond the safe UX state, provider details, internal paths, account role, workspace, or another tenant.
- **FR-039**: Logs, analytics, traces, durable payloads, and public errors MUST exclude raw/normalized email, passwords and hashes, cookies, bearer credentials, verification/reset tokens or links, rendered email bodies, provider credentials/responses, signed URLs, presentation content, and local paths.
- **FR-040**: Lifecycle audit events MUST record safe actor/account IDs when available, purpose, transition category, outcome, bounded timing, and non-secret rate/delivery categories; anonymous rejected requests and abandoned pending-registration cleanup MUST not create a durable identity oracle or retain email values. Reclamation may emit aggregate metrics and a non-PII terminal category only.
- **FR-041**: Account identity, pending email reservation, and normalized email uniqueness MUST be global rather than workspace-scoped; verified public activation MUST create only the personal workspace and MUST NOT infer or grant membership in any other tenant.
- **FR-042**: Email-addressed invitation acceptance MUST require an authenticated account with the matching verified normalized email plus the separate valid invitation token; legacy username invitation matching MAY remain only for grandfathered/admin-provisioned compatibility.
- **FR-043**: The backend MUST ignore or reject client-supplied activity, verification, owner, role, superuser, workspace, membership, and capability fields and MUST enforce every protected read/write with the applicable owner/workspace predicate.

#### Bilingual Product Experience

- **FR-044**: Locale-preserving public routes/pages MUST exist for registration, check-email, verification-required, verification success, verification expired/invalid, resend, login, forgot password, reset password, reset expired/invalid/used, recovery complete, duplicate-submission acknowledgement, rate limited, generic failure, loading, and success states.
- **FR-045**: All new user-facing UI and email copy MUST use canonical English/Arabic catalogs with identical keys and interpolation variables, plain-text-safe values, and no concatenated translated sentences.
- **FR-046**: Every public account page MUST use the selected `lang` and `dir`, logical-direction layout, and Arabic RTL styling while keeping presentation canvas geometry, element order, and coordinates unchanged.
- **FR-047**: Every asynchronous account state MUST have a bounded localized loading state, timeout, recoverable failure action, disabled-submit state, and duplicate-submit prevention at desktop and narrow viewports.
- **FR-048**: Forms and status pages MUST support keyboard-only completion, visible focus, correctly associated labels/instructions/errors, appropriate autocomplete, focus restoration, live status announcements, reduced motion, and no keyboard traps.
- **FR-049**: Email addresses, codes, and token-related guidance MUST be bidi-isolated and readable in Arabic without changing their underlying value; sensitive tokens MUST never be exposed to assistive labels, screenshots, or copied analytics data beyond the user's explicit action.

#### Migration, Rollout, Contracts, and Evidence

- **FR-050**: Persistent changes MUST use one additive Alembic migration path that introduces pending-registration/identifier-reservation state, fixed retention timestamps, nullable normalized/original email on terminal pending rows and verified users, explicit account/email state, and purpose-challenge/notification-delivery state, with reviewed upgrade/downgrade and reclamation behavior for SQLite and PostgreSQL.
- **FR-051**: Migration MUST backfill every existing account as active `grandfathered` or `admin_provisioned` according to repository evidence, preserve nullable email, retain current username login and administrator status, and avoid falsely asserting verified email ownership.
- **FR-052**: Before enforcing normalized-email uniqueness, migration/rollout MUST perform a shadow collision check across candidate emails and existing case-insensitive username aliases, produce privacy-safe operator evidence, and refuse destructive or ambiguous automatic merges.
- **FR-053**: `public_signup`, `email_verification`, `password_recovery`, and `notification_delivery` capabilities MUST default off, be exposed authoritatively to clients, fail closed in contradictory production combinations, and never be bypassed by direct calls. Disabling public issuance MUST NOT disable safe pending-registration reclamation or privacy cleanup.
- **FR-054**: Production enablement MUST require healthy authoritative database migration, shared Redis-backed login and lifecycle abuse controls, pending-registration reconciliation/backlog health, reviewed sender/domain and public origin, bounded notification delivery, secret configuration, English/Arabic templates, and staff/cohort evidence before anonymous traffic.
- **FR-055**: Operational rollback MUST disable new signup/resend/recovery submissions, keep login for existing active accounts, continue safe consumption or expiration of already accepted uncompromised challenges, continue pending-registration reclamation and redaction, retain required terminal/account/challenge/audit evidence, and avoid destructive schema reversal.
- **FR-056**: New public lifecycle contracts MUST be versioned, documented with stable request/response/error semantics, generated through the repository's owning API contract workflow, and preserve existing login/status/logout compatibility during rollout.
- **FR-057**: Validation MUST include focused and full backend auth/owner/workspace tests; attacker-before/after-victim credential-pre-hijack races; fixed-lease lazy/hourly reclamation races and identifier reuse; multi-instance Redis login admission/failure/clear/`Retry-After` tests; deterministic verification/reset golden vectors and cross-process/SQLite/PostgreSQL token reconstruction; migration graph and disposable PostgreSQL concurrency tests; equivalent SQLite state/uniqueness tests; API-contract checks; frontend unit/build/i18n tests; English/Arabic locale and product E2E; accessibility/keyboard/responsive checks; fake-email retry/idempotency tests; CSRF/safe-redirect tests; and secret/log redaction review without real provider credentials.
- **FR-058**: Privacy-safe observability MUST measure request outcome, response latency, rate-limit category, challenge transition, delivery attempt/outcome, pending-reclamation/backlog category, verification/recovery completion, workspace-provisioning outcome, and session-revocation outcome using bounded labels and safe IDs only.
- **FR-059**: The authenticated account/status contract MUST return backend-authoritative role, lifecycle state, and applicable workspace/capability context needed for navigation while treating that client-visible context as informational rather than authorization.
- **FR-060**: The localized account/settings experience MUST show the authenticated user's own account identifier, verified-email or administrator-managed status, locale, recovery eligibility, authenticated password-change action, current sign-out action, and global session-revocation action where required, without exposing internal token, hash, or tenant state.
- **FR-061**: Authenticated password change MUST require an active current browser session, the correct current password, a distinct compliant new password and matching confirmation, and the common same-origin mutation policy. It MUST lock and recheck the persisted user/session generation, atomically replace the canonical hash, revoke outstanding password-reset challenges, increment `auth_version` exactly once, append a privacy-safe audit event, delete the caller's cookie, issue no replacement session, and return a stable sign-in-required success result. Incorrect current password, unchanged password, policy/confirmation failure, disabled account, rate limit, stale generation, or a losing concurrent request MUST leave all credential and session state unchanged.

### Security Invariants

- **SR-001 — Authority**: FastAPI is the sole authority for identity, account/email state, credentials, sessions, roles, authorization, ownership, membership, RBAC, administrator status, and workspace provisioning.
- **SR-002 — Normal-only registration**: No public payload, route, migration default, retry, invitation, or provider response can create or elevate a superuser or platform administrator.
- **SR-003 — Enumeration resistance**: Signup, resend, forgot-password, and ineligible-account responses are constant-shape and non-identifying; delivery work is decoupled so provider/account lookup does not create an obvious timing oracle.
- **SR-004 — Token secrecy, purpose, and canonical derivation**: Verification/reset tokens are opaque, high entropy, purpose/subject/generation-bound, non-recoverable at rest, absent from durable payloads and observability, and submitted only to the authoritative same-origin backend. Deterministic reconstruction uses the frozen versioned byte contract and never a database-rendered timestamp or string representation.
- **SR-005 — Expiry and replay**: Verification expires within 24 hours, reset within 30 minutes, exactly one state transition can consume a token, and replacement/success invalidates superseded challenges.
- **SR-006 — Password protection and ownership**: No unauthenticated registration may persist a user-selected credential. The first public password is accepted only with valid email-verification proof and commits with account activation; all first/reset/authenticated-change values are accepted only over the protected deployment channel, bounded to 12–128 characters, blocked when known-common/compromised, adaptively hashed, never reversibly stored, and never logged or sent to third parties.
- **SR-007 — Session revocation**: Reset, administrator reset, authenticated password change, and deactivation rotate the authoritative session version; authenticated password change verifies the current password, rejects credential reuse, rechecks the locked generation, deletes the caller cookie, and issues no replacement credential, so every pre-transition JWT including the caller fails on its next backend check.
- **SR-008 — Distributed abuse controls**: Anonymous and credential operations, including unified username/email login, use the canonical distributed production controller with privacy-safe keyed identifier scopes, finite IP/identity/combined/global budgets, resend cooldown, attempt limits, bounded provider retries, safe `Retry-After`, and emergency disables. Raw username/email values never enter Redis keys, and no process-local limiter is a production authority.
- **SR-009 — Browser mutation safety**: Cookie-authenticated mutations and token consumption enforce same-origin/CSRF policy; redirects are allowlisted and re-authorized; token pages prevent referrer, URL-log, history, analytics, and storage leakage.
- **SR-010 — Tenant isolation**: Public identity is global, activation provisions only the personal workspace, invitations remain explicit and separately authorized, and every protected resource action retains owner/workspace predicates and enumeration-resistant cross-tenant failures.
- **SR-011 — Privacy**: Emails contain minimal transactional content; raw email, credentials, tokens, message bodies, provider data, presentation content, signed URLs, and local paths are excluded from logs, analytics, traces, jobs, audit metadata, and public errors as applicable.
- **SR-012 — Safe public errors**: Public errors use stable bounded codes/messages, never exception/provider/database text, and disclose detailed lifecycle state only when possession of valid credentials or token makes that state safe to show.
- **SR-013 — Reversible and minimized persistence**: Schema evolution is additive/backfilled, ambiguity refuses unsafe merge, and destructive rollback is forbidden after public data exists. A pending registration has a non-extendable 72-hour lease; reclamation atomically releases its identifier, removes email data, invalidates delivery/token effects, and cannot select any actual user. Non-PII pending tombstones are deleted after at most 30 additional days once dependent jobs are terminal, while operational rollback preserves required accepted state and continues cleanup.
- **SR-014 — Fail-safe rollout**: Public flags default off; production rejects invalid flag/dependency combinations; disabling submissions does not silently invalidate accepted safe challenges unless an explicit security incident requires revocation.

### Bilingual Acceptance Criteria

- **BA-001**: English and Arabic catalogs contain identical keys and variables for every lifecycle UI and email state.
- **BA-002**: `/en` LTR and `/ar` RTL registration, verification, resend, login, forgot, reset, completion, rate-limit, loading, and failure routes complete with equivalent outcomes.
- **BA-003**: Locale survives registration, email links, verification, sign-in, safe return navigation, account preference persistence, session expiry, and recovery.
- **BA-004**: Arabic pages and emails bidi-isolate addresses and token guidance; English/Arabic copy and interaction receive recorded human review rather than machine-only acceptance. The review MUST cover wording quality, meaning parity, bidi behavior, RTL/LTR reading order, keyboard flow, visible focus, accessibility semantics, and assistive-technology-relevant behavior for both locales.
- **BA-005**: Every form is keyboard-completable with visible focus, no traps, semantic labels, inline and announced validation, and deterministic focus after submit/error.
- **BA-006**: Every state is usable at 320 CSS pixels wide, at 200% text zoom, and with reduced motion in both directions without losing actions or obscuring errors.
- **BA-007**: Loading, disabled, duplicate-submit, success, expired, invalid, rate-limited, provider-delayed, network-failure, and generic-failure states are equivalent in both locales.
- **BA-008**: Application RTL changes do not mirror or mutate presentation canvas geometry, element order, or coordinates.

### Compatibility Requirements

- **CR-001**: Existing username login remains available for current and administrator-provisioned accounts throughout the compatibility window.
- **CR-002**: Existing six-character passwords remain login-compatible; only newly created/reset values must satisfy the new policy.
- **CR-003**: Successful login continues to upgrade recognized legacy password hashes through the current password-helper boundary.
- **CR-004**: The existing cookie name, JWT audience/strategy, `auth_version`, login/status/verify/logout behavior, locale preference, and same-origin clients remain compatible unless an explicitly versioned migration is approved.
- **CR-005**: Deployment bootstrap and `RESET_AUTH`/environment recovery remain the only primary-administrator provisioning/recovery path; `/api/v1/auth/setup` remains absent.
- **CR-006**: Existing administrator-created user IDs, usernames, roles, personal workspaces, ownership, memberships, access, and administrator password-reset behavior are preserved.
- **CR-007**: Workspace/RBAC flags remain default-off, the legacy owner bridge retains its safe default, and public identity work does not claim tenant cutover.
- **CR-008**: FastAPI Users may remain the internal account/password/session foundation, but no default route, secret, response, or token behavior is public contract unless it satisfies every requirement above.

### Explicit Exclusions

- Social login, OAuth login, SSO, passkeys, MFA, and a second administrator login product.
- Subscriptions, payments, credits, quotas, billing redesign, and commercial entitlement changes.
- Public administrator signup, self-service administrator recovery, client-assigned roles, and organization/workspace redesign.
- Email change after verified registration, username claiming for public accounts, full session inventory/device management, and general account deletion. The account page only integrates identity, verification/recovery status, authenticated password change, locale, and current/global revocation actions required by this sprint.
- Anonymous conversion claiming, conversion-specific accounts, conversion history/favorites implementation, and public API-key redesign.
- Marketing email, notification preferences beyond lifecycle delivery, or commitment to a permanent email vendor.
- Sprint 10.11 brand/repository cleanup, Sprint 11 generation-form work, Sprint 12 image-job work, unrelated dashboard/provider/editor changes, and any presentation canvas geometry change.

### Key Entities *(include if feature involves data)*

- **Pending Registration**: A temporary non-authenticatable email reservation with locale, fixed creation/reclaim times, claim generation, state, and no password, user authority, workspace, membership, or session; it either transfers its claim during verified activation or is redacted/reclaimed.
- **Account Identity**: One global Bayanly user created for a public identity only during verified activation, with immutable identity, public or admin-provisioned origin, activity state, normal/superuser authority, legacy username alias where present, locale, adaptive password hash, and session version.
- **Email Identity**: The submitted display address and canonical normalized value, first reserved by one live pending registration and then atomically transferred to one verified public user, with ownership/verification time and uniqueness/collision status; absent for grandfathered username-only accounts and redacted on pending terminal state.
- **Purpose Challenge**: One verification capability bound to a pending registration/email-claim generation or one reset capability bound to an active user/credential generation, with issued/expiry/consumed/revoked state, attempt/resend metadata, key/version fields, a database-independent canonical derivation subject, and a non-recoverable verifier. Eligibility timestamps are stored but excluded from derivation bytes.
- **Notification Delivery**: A provider-independent request/outcome reference for one localized transactional purpose and delivery generation, including bounded attempt, idempotency, terminal state, and safe timing/category data but no raw token or rendered content in durable payloads. Multiple allowed verification deliveries may carry the same still-current challenge.
- **Browser Session Version**: The authoritative account generation embedded in current cookie JWTs; changing it invalidates prior browser sessions without introducing a second session authority.
- **Personal Workspace and Membership**: The deterministic workspace and owner membership created or reconciled exactly once during activation or administrator provisioning.
- **Lifecycle Audit Event**: Append-only, privacy-safe evidence of authorized transition categories and outcomes using safe IDs and bounded metadata.

### Migration and Rollback Implications

- Migration is expand/backfill/enforce: add pending-registration, reservable identifier, lifecycle, retention, challenge, and delivery persistence; backfill existing accounts; shadow normalized-email/login-alias collisions; then enforce uniqueness only after reviewed evidence. No account is automatically merged, renamed, deactivated, reclaimed, or assigned an invented email.
- Existing `is_verified=true` rows are classified as `grandfathered`/`admin_provisioned` access, not silently converted into verified-email claims. Existing authentication remains available with all Sprint 10.10 flags off.
- SQLite and PostgreSQL upgrades, a single-head graph, downgrade behavior on disposable databases, concurrent uniqueness, idempotent re-run, and startup compatibility inference require tests. Production rollback is application/flag rollback, not destructive schema downgrade after lifecycle data exists.
- Rollback disables new public submissions first, keeps existing login/admin provisioning operational, allows already accepted uncompromised verification/reset challenges to finish or expire, retains required user/accepted-challenge/audit data, continues pending claim release/redaction/terminal purge, and restores no removed `/auth/setup` route.
- Pending cleanup is correctness-safe without a scheduler because registration, resend, and verification lazily reconcile expired claims under the same transaction protocol. An hourly bounded `SYSTEM_ACCOUNT_LIFECYCLE` reconciliation job supplies privacy cleanup for addresses that never return; it uses the canonical job/outbox boundary and cannot select actual users.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of usability-test participants can submit registration in under two minutes and complete verification-to-Dashboard in under five minutes after a message is available, measured separately in English and Arabic with at least 20 independent participants per locale and a recorded privacy-safe participant/result matrix.
- **SC-002**: 100% of tested public activations create a normal account only; zero can create or gain administrator authority, and zero attacker-known credential submitted before email proof survives victim re-registration, resend, token replacement, race, retry, or activation.
- **SC-003**: For every account-existence matrix, signup/resend/forgot responses have identical status and schema and no identifying copy; login pending/absent/disabled/wrong-password responses remain generic with dummy/real password work; reviewed timing distributions show no practical oracle; and two-instance Redis tests enforce identical login budgets and bounded `Retry-After` without raw identifiers.
- **SC-004**: 100% of attacker-before-victim, attacker-after-victim, repeated-registration, resend, expiry/replacement, malformed-token, wrong-purpose, replay, and concurrent-consumption tests result in no more than one verified user/credential activation or password change, and the winning first credential is supplied with the consumed verification token.
- **SC-005**: 100% of pre-reset, pre-administrator-reset, pre-password-change, and pre-deactivation browser sessions are rejected on their next protected backend request.
- **SC-006**: Under healthy controlled delivery conditions, at least 99% of a recorded run of at least 100 accepted fake/staging transactional messages reach a terminal delivered state within two minutes; retries and redeliveries produce zero duplicate effective challenge generations, and the evidence contains no recipient, token, link, or rendered body.
- **SC-007**: 100% of verified public accounts have exactly one user, adaptive credential, personal workspace, and active owner membership; injected creation/provisioning failures leave zero user, credential, identifier-transfer, or active-workspace orphan state.
- **SC-008**: Migration fixtures preserve 100% of existing account IDs, usernames, hashes, roles, locale, session versions, owner/workspace bindings, and login compatibility, with zero automatic identity merges or existing-user reclamation; stale-pending fixtures release their identifier and redact email atomically in both SQLite and PostgreSQL.
- **SC-009**: Every English/Arabic lifecycle route and email state passes catalog parity, locale routing, keyboard, responsive, and automated accessibility gates, with zero missing keys, keyboard traps, or presentation-geometry changes.
- **SC-010**: Public acknowledgement and token-state pages present a usable state within two seconds at the agreed service target and never wait indefinitely; dependency failures reach a recovery action within the configured timeout. A controlled production-build run MUST record at least 20 cold-start samples for each required public route/state family in each locale, and every recorded sample MUST meet the two-second usable-state threshold.
- **SC-011**: Security review finds zero raw email addresses, passwords/hashes, session cookies, verification/reset tokens or links, rendered email bodies, provider secrets/responses, signed URLs, presentation content, or local paths in sampled logs, analytics, traces, durable job payloads, audit metadata, and public errors.

### Acceptance Evidence Contract

- **AUTOMATED EVIDENCE**: Unit, integration, migration, Redis multi-instance, generated-contract, Node, Cypress, accessibility-scan, build, localization, privacy, and repository gates provide deterministic evidence for the implementation requirements. Automated evidence may prepare fixtures and measurements but MUST NOT be described as human usability, language-quality, reading-order, keyboard, or assistive-technology acceptance.
- **HUMAN / CONTROLLED ACCEPTANCE EVIDENCE**: Public enablement requires four separately recorded, privacy-safe artifacts: `artifacts/account-lifecycle/acceptance/sc-001-usability-matrix.csv` plus `sc-001-usability-summary.json`; `sc-006-delivery-run.json`; `sc-010-ui-timing.json`; and `ba-004-human-bilingual-review.md`. They MUST identify the build/configuration, date, evidence owner/reviewer role, pass/fail result, sample counts, and applicable threshold without including real email addresses, passwords, cookies, bearer tokens/links, rendered message bodies, or participant personal data. Planning defines these artifacts; it does not claim that any result has already been measured.

## Assumptions

- Public signup first collects email and locale and does not ask the visitor to claim a username or password. The first password is chosen on the verification-token page and persists only with successful activation. Existing username remains only the compatibility login/display alias for current and administrator-created accounts.
- Verification links expire after 24 hours; reset links expire after 30 minutes; resend has a 60-second cooldown and five-per-day ceiling. These are secure defaults derived from the requested product behavior and may be tightened by operators.
- A pending registration's 72-hour reclaim deadline is fixed at initial creation and cannot be extended by repeat registration, resend, delivery retry, or provider delay. Challenge expiry is capped by that deadline; terminal non-PII pending records are retained no longer than 30 additional days once dependent work is terminal.
- Verification/reset secret reconstruction uses the versioned canonical byte contract documented by the feature design; `issued_at` remains authoritative eligibility/audit data but is intentionally absent from the HMAC context.
- Existing username-only accounts intentionally remain usable without a verified email. They continue to use administrator-managed recovery until a future, separately approved verified-email enrollment flow.
- The public web origin, sender identity/domain, privacy/legal copy, and transactional email provider are operator-owned deployment inputs. CI and local validation use only fake or safe development delivery adapters.
- Current personal-workspace persistence exists even while workspace/RBAC enforcement is feature-flagged off, allowing provisioning now without claiming workspace cutover.
- Full session inventory, verified-email change, MFA/passkeys, and anonymous-work claiming are separate product decisions and are not prerequisites for this sprint's specified lifecycle.
- The existing normal-user owner isolation, bootstrap administrator, auth-version session contract, localized shell, and canonical job/operation-control foundations remain available and are extended rather than replaced.
- The authenticated password-change policy disallows choosing the current password, invalidates every browser session including the caller, and requires sign-in again; selective current-session preservation is out of scope.
- All product decisions required for this approved specification are resolved; there are no open clarification markers.

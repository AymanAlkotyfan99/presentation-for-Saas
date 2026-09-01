# Data Model: Public Account Lifecycle

- **Feature**: `001-public-account-lifecycle`
- **Authority**: FastAPI and the single Bayanly SQL/Alembic graph
- **Supported migration paths**: SQLite and PostgreSQL

This design extends the existing `user`, workspace, invitation, job/outbox, and audit foundations. It does not introduce a second user, session, tenant, queue, or provider authority.

## Entity Relationship Summary

```text
User (existing identity authority)
 |-- 0..2 AccountLoginIdentifier (legacy/admin username; verified public email)
 |-- 0..* AccountPurposeChallenge (password reset only)
 |-- 0..* AccountLifecycleAuditEvent
 `-- 0..1 Personal Workspace (existing; created at activation/admin provisioning)
        `-- exactly 1 active OWNER Membership (existing)

PendingRegistration (temporary, non-authenticatable pre-account state)
 |-- exactly 1 pending-owned AccountLoginIdentifier while live
 |-- 0..* AccountPurposeChallenge (email verification only)
 |      `-- 1..* NotificationDelivery (initial plus bounded same-token redeliveries)
 `-- 0..1 activated User after atomic claim transfer

NotificationDelivery
 `-- exactly 1 canonical SYSTEM_ACCOUNT_LIFECYCLE Job/Outbox execution

Invitation (existing workspace entity)
 `-- matches either verified normalized email or a legacy/admin username claim;
     token possession remains independently required
```

## 1. User (Existing Table, Extended)

**Table**: `user`
**Owner**: `models/sql/user.py`, with lifecycle transitions owned by `modules/identity`

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `id` | existing UUID, non-null | Immutable global account ID; preserved by migration. |
| `username` | existing string(128), becomes nullable | Preserved for all existing/admin-provisioned accounts; null for public accounts. A non-null value is a compatibility login alias only when claimed in `account_login_identifiers`. |
| `admin_slot` | existing string(32), nullable unique | Existing `primary` slot remains deployment-controlled. Public code cannot set it. |
| `hashed_password` | existing string(1024), non-null | Produced only by the existing adaptive password helper. Never exposed or logged. |
| `is_active` | existing bool, non-null | FastAPI Users compatibility projection: true only for an active account. |
| `is_superuser` | existing bool, non-null | Server-fixed false for public/admin-created normal users; only deployment/authorized admin policy may alter authority. |
| `is_verified` | existing bool, non-null | Compatibility projection. For public accounts it follows verified email state; historical true values do not prove email ownership. |
| `auth_version` | existing integer, non-null | Browser-session/credential generation; increments on reset, admin reset, global revocation, password change, and deactivation. |
| `preferred_locale` | existing `en` / `ar` / null | Registration persists the submitted supported locale; existing behavior remains. |
| `created_at` | existing timestamptz, nullable for legacy | Preserved. |
| `account_origin` | string enum, non-null after backfill | `PUBLIC`, `ADMIN_PROVISIONED`, or `GRANDFATHERED`. Primary/historical superusers are `GRANDFATHERED`; current normal users are `ADMIN_PROVISIONED`. |
| `account_state` | string enum, non-null after backfill | `ACTIVE` or `DISABLED`. Pending registration is not a user state. |
| `email_state` | string enum, non-null after backfill | `UNSET` or `VERIFIED`. Pending email is owned by `PendingRegistration`, not `User`. |
| `email_original` | string(320), nullable | Trimmed/NFC user-visible address. Stored only after verified public activation; not returned by anonymous endpoints. |
| `email_normalized` | string(320), nullable | NFC, complete-address case-folded, IDNA-domain comparison value. Globally unique when non-null. |
| `email_generation` | integer, non-null default 0 | Incremented by any future reviewed email replacement; verification challenges bind to the current value. Public creation starts at 1. |
| `email_verified_at` | timestamptz, nullable | Present only after successful public email verification; absent for username-only accounts even if historical `is_verified=true`. |

### User Constraints

- `PUBLIC` requires non-null verified email fields, `email_generation >= 1`, an adaptive password hash, and a user-owned email identifier.
- An active public user requires `email_state=VERIFIED`, non-null `email_verified_at`, `is_active=true`, and `is_verified=true`.
- `email_state=UNSET` requires null email fields and null `email_verified_at`.
- `is_superuser=true` is forbidden for `PUBLIC` and `ADMIN_PROVISIONED` creation paths.
- `email_normalized` has a partial unique index when non-null; the identifier registry supplies the stronger email-versus-username cross-kind invariant.
- State updates occur only through identity application operations that keep compatibility booleans synchronized.

### User State Transitions

```text
Public registration
  -> no User row (creates PendingRegistration only)

Valid verification + password + workspace transaction
  -> creates PUBLIC / ACTIVE / VERIFIED / active User exactly once

Authorized deactivation (management surface is not added by this sprint)
  -> any origin / DISABLED / prior email state / inactive
     + auth_version increment + challenge revocation

Admin creation
  -> ADMIN_PROVISIONED / ACTIVE / UNSET / active

Migration of current primary/historical superuser
  -> GRANDFATHERED / ACTIVE-or-DISABLED / UNSET / preserved activity
```

Reactivation, verified-email change, account deletion redesign, and public username enrollment are not introduced.

## 2. PendingRegistration (New)

**Table**: `account_pending_registrations`
**Owner**: `modules/identity/persistence`

This is a temporary lifecycle subject, not a user/account/session authority. No authentication resolver, owner predicate, workspace relation, invitation acceptance, API credential, or FastAPI Users adapter treats it as a `User`.

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `id` | random UUID, primary key | Stable verification subject and safe internal locator. |
| `state` | string enum, non-null | `PENDING`, `ACTIVATED`, or `ABANDONED`. Compare-and-set/row lock controls the single terminal transition. |
| `email_original` | string(320), nullable | Trimmed/NFC delivery address while `PENDING`; nulled in the terminal transaction. |
| `email_normalized` | string(320), nullable | Canonical comparison value while `PENDING`; nulled in the terminal transaction. Global reservation is enforced by `AccountLoginIdentifier`. |
| `preferred_locale` | `en` / `ar`, non-null | Initial and resend template locale; terminal rows may retain the non-identifying locale. |
| `claim_generation` | unsigned-compatible integer, non-null default 1 | Verification binding generation; immutable for this registration lease. |
| `created_at` | UTC timestamptz, non-null | Written once at initial creation. |
| `reclaim_after` | UTC timestamptz, non-null | Exactly `created_at + 72 hours`; never extended. |
| `terminal_at` | UTC timestamptz, nullable | Set on activation or abandonment. |
| `purge_after` | UTC timestamptz, nullable | Exactly `terminal_at + 30 days`; physical deletion waits for dependent jobs/deliveries to be terminal. |
| `activated_user_id` | UUID FK `user.id`, nullable unique | Set only for `ACTIVATED`; supports bounded already-completed replay without exposing the user. No cascade may delete the activated user. |

### Pending Registration Constraints and Transitions

- `PENDING` requires non-null email values, null terminal/purge/user values, exactly one pending-owned email identifier, and no `User`/password/workspace relation.
- `ACTIVATED` requires null email values, non-null terminal/purge/activated user, no pending-owned identifier, and the identifier transferred to that user in the same transaction.
- `ABANDONED` requires null email values, non-null terminal/purge, null activated user, no identifier, and every challenge/delivery ineligible.
- `reclaim_after = created_at + 72 hours` is enforced by application fixtures/checks across supported databases; no repeat registration, resend, retry, or provider event writes it.
- Every verification challenge for the subject has `expires_at <= reclaim_after`.
- Index `(state, reclaim_after, id)` supports bounded reclamation without scanning actual users.
- Lazy registration/resend/consume and the hourly reconciliation job acquire the identifier claim, pending row, and challenge in one documented order. PostgreSQL uses `FOR UPDATE`; SQLite uses its serialized writer transaction plus state/generation compare-and-set and uniqueness constraints.
- At reclamation, state transition, claim deletion, email nulling, challenge revocation, and delivery suppression commit atomically. At activation, user insertion, credential hash, claim transfer, email nulling, workspace/membership, audit, and challenge consumption commit atomically.
- Physical purge after 30 days removes only terminal pending/challenge/delivery rows whose canonical jobs are terminal. Actual users and user-owned identifier claims are never selected.

```text
PENDING
  -> ACTIVATED  (valid token + password; atomic User/claim/workspace creation)
  -> ABANDONED  (reclaim_after reached; atomic claim release/redaction)

ACTIVATED/ABANDONED
  -> PURGED     (after purge_after and terminal dependent work; no User deletion)
```

## 3. AccountLoginIdentifier (New)

**Table**: `account_login_identifiers`
**Owner**: `modules/identity/persistence`

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `normalized_value` | string(320), primary/unique | Global normalized login claim. Never logged or exposed anonymously. |
| `user_id` | UUID FK `user.id`, nullable | Set for actual username/email login claims. Existing deletion behavior remains; activated public email claims point here. |
| `pending_registration_id` | UUID FK pending registration, nullable unique | Set only while a pending email reservation is live; deleted/released on abandonment or replaced by `user_id` on activation. |
| `kind` | string enum, non-null | `USERNAME` or `EMAIL`. |
| `created_at` | timestamptz, non-null | Audit timing only. |

### Identifier Constraints

- Unique `normalized_value` prevents username/email ambiguity and cross-instance races.
- Check constraint requires exactly one of `user_id` or `pending_registration_id`.
- Unique `(user_id, kind)` for non-null users permits at most one current username claim and one current email claim.
- Existing/admin usernames normalize with trim + NFC + case fold.
- User-owned email identifiers must equal `user.email_normalized`; username identifiers must equal the normalized non-null `user.username`.
- A pending-owned email identifier must equal its pending row's non-null normalized email and is not a login subject.
- Activated public users have a user-owned `EMAIL` row only. Username-only users have a `USERNAME` row only until a separately approved email-enrollment flow exists.
- Login resolves only rows with non-null `user_id`, then rechecks user state/origin/kind eligibility before password verification and session issuance. A pending-owned match follows the absent-account dummy-password path.

## 4. AccountPurposeChallenge (New)

**Table**: `account_purpose_challenges`
**Owner**: `modules/identity/persistence`

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `id` | random UUID, primary key | Public token locator; not sufficient without the 256-bit secret. |
| `subject_kind` | string enum, non-null | `PENDING_REGISTRATION` for verification or `USER` for reset. Immutable and encoded as a fixed one-byte derivation code. |
| `pending_registration_id` | UUID FK pending registration, nullable | Required only for verification. |
| `user_id` | UUID FK `user.id`, nullable | Required only for password reset. |
| `purpose` | string enum, non-null | `EMAIL_VERIFICATION` or `PASSWORD_RESET`; immutable. |
| `issue_generation` | integer, non-null | Monotonic within the selected subject/purpose; persistence uniqueness only and excluded from token derivation. |
| `binding_generation` | integer, non-null | Verification: pending `claim_generation`; reset: issuance-time `auth_version`. Encoded as unsigned 64-bit big-endian bytes for derivation. |
| `key_version` | bounded string, non-null | Selects the operator key-ring version required to rederive/verify the secret. |
| `token_digest` | fixed char(64), non-null unique | SHA-256 verifier of the complete opaque token. Raw/encrypted raw token is not stored. |
| `issued_at` | timestamptz, non-null | Eligibility/audit timestamp only; explicitly excluded from token derivation. |
| `expires_at` | timestamptz, non-null | Verification <=24h; reset <=30m. |
| `is_current` | bool, non-null | Exactly one current row per user/purpose via partial unique index. |
| `failed_attempt_count` | integer, non-null default 0 | Atomic total; the fifth failed secret validation revokes eligibility. |
| `consumed_at` | timestamptz, nullable | Set once by the winning state transition. |
| `revoked_at` | timestamptz, nullable | Set by replacement, deactivation, generation change, emergency action, or failed-attempt ceiling. |
| `revocation_reason` | bounded enum/string, nullable | Finite safe category; never exception/provider text. |

### Challenge Constraints and Indexes

- Check constraints require verification → pending subject only and reset → user subject only.
- Partial unique indexes permit one current challenge per selected subject/purpose.
- Unique selected-subject/purpose/`issue_generation` and unique `token_digest`.
- `expires_at > issued_at`; verification TTL <=24 hours; reset TTL <=30 minutes.
- Verification additionally requires `expires_at <= pending_registration.reclaim_after`.
- `consumed_at` and `revoked_at` are mutually exclusive terminal outcomes; terminal rows have `is_current=false`.
- Token parsing is length/prefix/purpose bounded before lookup; digest comparison is constant-time.
- A current verification challenge is eligible only while the selected pending registration is live, its pending-owned email claim/generation matches, and its retention lease has not ended.
- A current reset challenge is eligible only while account is active/recoverable and `binding_generation == user.auth_version`.
- The identity persistence boundary exposes one shared authoritative eligibility read/lock contract over challenge, subject, binding, and lease state before notification workers are integrated. Registration, resend, consumption, reclamation, and delivery workers reuse that boundary; durable payload fields never substitute for re-reading these rows.

### Challenge State Transitions

```text
ISSUED/CURRENT
  -> CONSUMED       (one winning verification/reset transaction)
  -> REVOKED        (expiry replacement, reclamation, account disable, binding/key emergency)
  -> EXPIRED        (derived at read; reconciliation clears is_current)
  -> REVOKED        (five failed secret validations)

Registration/resend while an eligible verification row is current creates only a new delivery generation for the same row/token. After expiry or authorized invalidation, replacement creates a new challenge generation and revokes/clears the prior row atomically.
Replay of CONSUMED/REVOKED/EXPIRED never performs the protected transition.
```

### Canonical Token Derivation Bytes

Wire token: `ba1.<ev|pr>.<kid>.<base64url-uuid-no-padding>.<base64url-32-byte-secret-no-padding>`.

HMAC context, concatenated exactly:

```text
UTF8("bayanly.account-token") || 00
|| u8(format=1)
|| u8(purpose: ev=1, pr=2)
|| u8(kid_length) || ASCII(kid)
|| challenge_uuid.bytes[16]                 # RFC/network order
|| u8(subject_kind: pending=1, user=2)
|| subject_uuid.bytes[16]                   # RFC/network order
|| u64be(binding_generation)
```

No timestamp, issue generation, locale, email value, delimiter, JSON, ORM type, or default string conversion participates. The secret is the 32-byte HMAC-SHA256 result; `token_digest` is lowercase-hex SHA-256 of the exact ASCII wire token. [research.md](research.md) freezes one verification and one reset golden vector. Unit, independent-process, SQLite, and PostgreSQL reconstruction must produce those exact bytes.

## 5. NotificationDelivery (New)

**Table**: `account_notification_deliveries`
**Owner**: `modules/notifications/persistence`

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `id` | UUID, primary key | Only value carried by the canonical job payload. |
| `challenge_id` | UUID FK challenge, non-null | Initial issuance and allowed resends may reference the same current verification challenge. |
| `delivery_generation` | integer, non-null | Monotonic per challenge; unique with `challenge_id`. Initial delivery is 1. |
| `purpose` | string enum, non-null | Verification or reset; must match challenge. |
| `locale` | `en` / `ar`, non-null | Selected at issuance; controls deterministic template. |
| `status` | string enum, non-null | `PENDING`, `DISPATCHING`, `DELIVERED`, `RETRYABLE`, `FAILED_TERMINAL`, `UNKNOWN_TERMINAL`, `SUPPRESSED`. |
| `attempt_count` | integer, non-null default 0 | Mirrors business-effect attempts; canonical job maximum is 3. |
| `message_id` | bounded string, non-null unique | Deterministic RFC Message-ID derived from delivery UUID; not a provider response. |
| `dispatch_started_at` | timestamptz, nullable | Detects ambiguous crash/handoff; stale `DISPATCHING` becomes unknown terminal, not a blind resend. |
| `delivered_at` | timestamptz, nullable | Set only for accepted provider outcome. |
| `terminal_at` | timestamptz, nullable | Set for terminal failed/unknown/suppressed outcomes. |
| `safe_error_code` | bounded enum/string, nullable | Finite category only; no SMTP/provider body or recipient. |
| `created_at`, `updated_at` | timestamptz, non-null | Operational timing. |

The row contains no recipient address, token/link, rendered subject/body, provider credential, or provider response. The handler loads the pending registration or user through the challenge subject, revalidates authority/state/lease, derives the token in process memory from the canonical bytes, renders, sends, and discards sensitive values.

### Delivery State Transitions

```text
PENDING -> DISPATCHING -> DELIVERED
                    |-> RETRYABLE -> DISPATCHING (canonical job retry, max 3)
                    |-> FAILED_TERMINAL
                    `-> UNKNOWN_TERMINAL (ambiguous provider handoff; no blind retry)

PENDING/RETRYABLE -> SUPPRESSED when challenge/subject/lease is no longer eligible.
All terminal states are idempotent no-ops on redelivery.
```

An allowed resend of an unexpired verification challenge creates a new delivery generation and canonical job with a distinct deterministic Message-ID but the same effective token. It does not mutate challenge expiry/current state or pending `reclaim_after`. After challenge expiry, a newly issued challenge starts its own delivery generation at 1 and every old link is invalid.

## 6. AccountLifecycleAuditEvent (New)

**Table**: `account_lifecycle_audit_events`
**Owner**: `modules/identity/persistence`

| Field | Type / nullability | Rules |
| --- | --- | --- |
| `id` | UUID, primary key | Safe event ID. |
| `account_id` | UUID FK user, nullable/set-null | Present only after safely resolving an account; null deletion preserves evidence. |
| `actor_id` | UUID FK user, nullable/set-null | For authenticated/admin operations only. |
| `purpose` | finite enum, non-null | Registration, verification, reset, session, admin compatibility, or lifecycle. |
| `transition` | bounded enum/string, non-null | E.g. `challenge_issued`, `account_activated`, `password_reset`, `sessions_revoked`. |
| `outcome` | bounded enum/string, non-null | `accepted`, `completed`, `rejected`, `retryable`, `terminal`. |
| `rate_category` | bounded enum/string, nullable | No key or identity value. |
| `delivery_category` | bounded enum/string, nullable | No provider response. |
| `duration_bucket` | bounded enum/string, nullable | Bucket, never raw trace content. |
| `created_at` | timestamptz, non-null | Append-only event time. |

Database/ORM immutability protections mirror the current workspace audit. There is no arbitrary JSON metadata. Malformed/anonymous rejected requests and abandoned-pending reclamation are aggregate metrics/non-PII categories only; they do not persist email values or a pending-registration identifier as a durable identity record.

## 7. Existing Workspace and Membership (Reused)

**Tables**: `workspaces`, `memberships`

No second workspace or membership model is added. `ensure_personal_workspace(session, user)` remains the only personal provisioner and keeps:

- deterministic workspace ID equal to user ID;
- unique `personal_owner_id`;
- deterministic/unique owner membership;
- `OWNER` + `ACTIVE` membership reconciliation;
- no internal commit.

For public users, the persisted personal workspace name is a non-secret neutral value; the frontend localizes the “personal workspace” label. Existing workspace names are preserved. Activation adds no other membership and does not accept invitations.

## 8. Existing Invitation (Extended)

**Table**: `invitations`

| New/changed field | Type / nullability | Rules |
| --- | --- | --- |
| `invited_identity` | widen to string(320) | Preserve stored display/input value for compatibility; never public-log it. |
| `normalized_identity` | string(320), non-null after backfill | Deterministic email/username comparison form. |
| `identity_kind` | string enum, non-null after backfill | Existing rows become `USERNAME`; new email invitations use `EMAIL`. |

Acceptance rules:

- `EMAIL`: authenticated account has `email_state=VERIFIED` and matching `email_normalized`, and the separate invitation token/policy succeeds.
- `USERNAME`: only `GRANDFATHERED` or `ADMIN_PROVISIONED` accounts with the matching username claim are eligible.
- Public verification never auto-accepts; cross-workspace authorization and current token replay/expiry behavior remain.

## 9. Canonical Job/Outbox Models (Extended)

**Tables**: `jobs`, `outbox_messages`, `job_attempts`, `consumer_inbox`, `dead_letters`, `job_events`

| New/changed field | Type / nullability | Rules |
| --- | --- | --- |
| `authority_kind` on `jobs` | string enum, non-null default `WORKSPACE` | Existing rows backfill `WORKSPACE`; only registry-allowlisted notification operations may use `SYSTEM_ACCOUNT_LIFECYCLE`. |
| `workspace_id` across job tables | becomes nullable | Null only for system lifecycle jobs; existing workspace jobs remain non-null. |
| `system_idempotency_scope` / constraint behavior | existing columns reused with a system unique index | Workspace uniqueness remains `(workspace_id, scope, key)`; system uniqueness applies `(authority_kind, scope, key)` when workspace is null. |
| queue enum | add `notification` | Dedicated scheduling class inside the same canonical queue/worker system. |

System job constraints require null workspace and actor/service-account fields. Workspace jobs retain current authority/membership checks. System rows are excluded from public/user job list/get/cancel/event APIs. Notification handlers revalidate the referenced delivery/challenge/subject immediately before effect.

Registered system operations are limited to:

- `account.notification.deliver.v1` with exactly `{notificationId}`; and
- `account.pending.reconcile.v1` with a non-identifying singleton cadence/batch contract and no email, pending ID, token, or user-controlled selector in its payload.

The reconcile handler pages only `PendingRegistration(state=PENDING, reclaim_after<=now)` by safe primary key order, uses the same domain transition/lock order as lazy reclamation, and owns no independent retry or scheduling authority outside canonical jobs.

## 10. Browser Session Version (Existing Logical Entity)

No table is added. Existing JWT payload `{sub, av, aud}` remains authoritative.

| Event | `auth_version` effect | Browser result |
| --- | --- | --- |
| Normal login | unchanged | Existing cookie issued. |
| Normal logout | unchanged | Current cookie deleted only. |
| Verification/first credential success | new public user starts at the canonical initial value | First successful consume may issue the current cookie only after user/workspace commit. |
| Public reset | +1 atomically with hash/challenge | Every earlier cookie fails next backend read; no auto-login. |
| Admin reset | +1 atomically with hash/challenge invalidation | Same invalidation behavior. |
| Authenticated password change | +1 atomically with hash replacement and reset-challenge invalidation | The caller cookie is deleted, no replacement cookie is issued, and every cookie from the prior generation fails; sign-in is required. |
| Global revoke-all | +1 | Current and other cookies fail; response deletes current cookie. |
| Deactivation | +1 plus inactive state | Every session fails by both activity and version. |

Authenticated password change adds no table or session record. Its transaction locks the existing `User`, requires the request principal's `auth_version` to equal the persisted value, rechecks active state, verifies the current hash, rejects a new password that verifies against that hash, applies the canonical new-password policy, replaces `hashed_password`, increments `auth_version` exactly once, revokes every current password-reset challenge for that user, and appends the safe audit event. Two requests authenticated with the same generation can have at most one winner; the loser observes a stale generation or changed current credential and performs no write.

## 11. Migration Ordering and Data Preservation

### Revision A — Expand and Backfill

- Descend directly from current head `d4f6a8c0e2b3`.
- Add nullable user fields and all new pending-registration/reservable-identifier/challenge/delivery/audit tables/columns, including job system scope and invitation identity fields.
- Backfill user origin/state/email state without altering ID, username, hash, role, activity, locale, session version, workspace, membership, or ownership.
- Normalize/backfill username identifier claims in Python with the frozen application algorithm.
- Abort on case-fold collisions with privacy-safe category/count/user-ID evidence; never auto-merge.
- Backfill all job rows as workspace authority and all current invitations as username identity.

### Shadow Gate

- Run the repository collision checker against SQLite and a production snapshot/read replica as approved.
- Confirm no duplicate normalized username claims and no candidate email-versus-alias collisions.
- Deploy dual-read-compatible code with all public flags off; reconcile any safe anomalies explicitly.

### Revision B — Enforce

- Add required user/pending state, ownership, 72-hour retention/terminal-redaction checks and partial unique indexes.
- Make `username` nullable for public rows while preserving all existing values.
- Enforce identifier owner exclusivity/transfer, normalized-email, subject-bound current-challenge, per-delivery-generation idempotency, invitation identity, and job-authority constraints.
- Leave one Alembic head and update migration-head compatibility detection.

### Downgrade / Rollback

- Physical downgrade is permitted only when no public account, pending registration/reservation, lifecycle challenge/delivery/audit row, system lifecycle job, or email invitation created under the new schema exists.
- Downgrade performs a preflight and refuses destructive data loss.
- After lifecycle data exists, rollback is operational: disable new issuance, retain schema/data, preserve existing login/admin behavior, continue pending reclamation/redaction, drain accepted delivery, and allow valid accepted tokens to complete or expire.

## 12. Transaction Invariants

| Operation | Atomic writes | External/asynchronous work |
| --- | --- | --- |
| New registration | pending registration + pending-owned email identifier + challenge + delivery generation 1 + job/outbox; no User/password | SMTP occurs only after commit. |
| Live re-registration/resend | same-token redelivery while live: same challenge/token + next delivery generation + job/outbox; no identity/binding/expiry/lease change/User/password | SMTP after commit. Replacement challenge only after expiry/invalidation. |
| Expired-challenge registration/resend | revoke/clear expired current challenge + one new challenge bounded by `reclaim_after` + delivery generation 1 + job/outbox | SMTP after commit. |
| Stale re-registration/lazy reclaim | abandon/redact stale pending + release claim + revoke/suppress child state, then create fresh pending/claim/challenge/delivery/job as one transaction | Old jobs suppress; fresh SMTP only after commit. |
| Verification/first credential | lock claim/pending/challenge + create User/hash/verified email + transfer identifier + consume/sibling revoke + redact pending + workspace + owner membership + both audit records | Cookie is built/set only for the committed winner. |
| Hourly pending reconciliation | bounded claim/pending lock + abandon/redact + claim release + challenge revoke + delivery suppression; terminal purge after 30 days | Canonical system job only; no external provider effect. |
| Forgot-password issuance | revoke prior reset + new reset challenge + delivery + job/outbox | SMTP after commit; public response never waits. |
| Password reset | password hash + challenge consume + sibling revoke + `auth_version` increment + audit | No email or session required to commit; no auto-login. |
| Authenticated password change | lock/recheck active User and request `auth_version` + current-password verification + distinct policy-compliant hash replacement + reset-challenge revoke + one `auth_version` increment + audit | Success deletes the caller cookie after commit; no replacement session or external effect. |
| Admin create | user + username identifier + active state + personal workspace + owner membership + audit | No public email. |
| Admin reset | password hash + reset challenge invalidation + `auth_version` increment + audit | No public email. |
| Notification attempt | delivery transition is committed around one bounded provider attempt after current subject/lease revalidation; ambiguous dispatch becomes terminal unknown | Canonical job owns retry/backoff/dead letter. |

An application service owns each commit. FastAPI route handlers and the custom FastAPI Users database adapter must not commit partial lifecycle state.

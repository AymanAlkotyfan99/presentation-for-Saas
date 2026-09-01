# HTTP Contract: Account Lifecycle

- **Contract status**: Planning contract; implementation must generate and verify the repository OpenAPI artifact.
- **Base path**: `/api/v1/auth`
- **Authority**: FastAPI
- **Transport**: HTTPS in production; same-origin JSON for browser mutations

This contract is additive. Existing `/status`, `/verify` (session verification), `/login`, `/logout`, and locale-preference behavior remains compatible. It does not mount FastAPI Users' stock public routers.

## Common Browser Mutation Requirements

Every POST/PUT below requires:

- `Content-Type: application/json`;
- `X-Bayanly-CSRF: 1`;
- exact approved `Origin` in production and acceptable `Sec-Fetch-Site`;
- bounded body/field sizes before database or provider work;
- `credentials: include` where a session may be read or set.

Cross-origin or malformed mutation requests receive a stable, non-secret 403/415/422 error and never perform lifecycle work. Public account endpoints are explicitly allowlisted through `SessionAuthMiddleware`, but remain protected by operation controls and the same-origin mutation policy.

Stable errors retain the repository envelope:

```json
{
  "detail": {
    "code": "STABLE_CODE",
    "message": "Bounded English fallback; the frontend localizes by code",
    "params": {}
  }
}
```

No response contains an email address, password/hash, challenge/token/link, provider result, internal path, role/tenant state of an unauthenticated account, or exception text.

## Canonical Bearer Representation

Verification/reset requests accept exactly `ba1.<ev|pr>.<kid>.<locator>.<secret>`, where `kid` is 1–16 allowlisted ASCII characters, locator is 22 unpadded-base64url characters encoding 16 RFC UUID bytes, and secret is 43 unpadded-base64url characters encoding 32 bytes. Extra components, padding, alternate alphabets, Unicode, wrong purpose, and oversized values are rejected before database lookup.

Secret reconstruction follows the exact byte contract and golden vectors in [research.md](../research.md) and [data-model.md](../data-model.md). It uses fixed domain/version/purpose/key-ID/UUID/subject-kind/binding-generation bytes and excludes every timestamp/database serialization. `issued_at` and `expires_at` are authoritative eligibility fields only.

## 1. Public Auth Status (Existing, Additive)

### `GET /api/v1/auth/status`

#### Public / unauthenticated capabilities

Unauthenticated response remains 200 and adds authoritative lifecycle availability. This projection is a shared foundation required before registration, verification, resend, or recovery pages may depend on capability gating:

```json
{
  "configured": true,
  "authenticated": false,
  "username": null,
  "user_id": null,
  "role": null,
  "preferred_locale": null,
  "account_identifier": null,
  "account_origin": null,
  "account_state": null,
  "email_verification_state": null,
  "recovery_eligible": false,
  "capabilities": {
    "publicSignup": false,
    "emailVerification": false,
    "passwordRecovery": false,
    "notificationDelivery": false
  }
}
```

Only the four product-availability booleans are newly exposed to unauthenticated callers. The response never reports dependency failures, worker/Redis/SMTP topology, key/configuration state, rollout cohort, account lookup state, or a reason why a capability is unavailable. Existing compatibility fields remain null/false as shown.

#### Authenticated account state

Authenticated response returns only the current account's backend-authoritative state. Existing fields remain:

```json
{
  "configured": true,
  "authenticated": true,
  "username": null,
  "user_id": "00000000-0000-0000-0000-000000000000",
  "role": "user",
  "preferred_locale": "ar",
  "account_identifier": "user@example.test",
  "account_origin": "PUBLIC",
  "account_state": "ACTIVE",
  "email_verification_state": "VERIFIED",
  "recovery_eligible": true,
  "capabilities": {
    "publicSignup": true,
    "emailVerification": true,
    "passwordRecovery": true,
    "notificationDelivery": true
  }
}
```

For current/admin users, `username` keeps its current value and `account_identifier` uses that username. Client-visible role/capability/workspace context is informational; APIs re-authorize every operation.

The unauthenticated capability projection is owned by the shared configuration/capability foundation. The authenticated account-specific fields are additive account/session integration and may be implemented later without blocking public pages from safely determining whether a public lifecycle action is available.

## 2. Session Verification (Existing)

### `GET /api/v1/auth/verify`

This endpoint continues to verify the existing cookie/API principal. It is not repurposed for email verification. Its existing success and `AUTH_REQUIRED` behavior remain, with additive account fields matching `/status` where useful.

## 3. Registration

### `POST /api/v1/auth/register`

Request:

```json
{
  "email": "user@example.test",
  "locale": "en"
}
```

Password, role, authority, activity, verification, owner, workspace, membership, and capability fields are rejected as extra input. Registration accepts no credential and creates a temporary non-authenticatable pending registration, not a `User`.

For unused, active, pending, disabled/deactivated, primary-admin, and username-alias-colliding identifiers, the accepted response is exactly:

- HTTP 202
- no cookie

```json
{
  "status": "accepted",
  "code": "ACCOUNT_REQUEST_ACCEPTED"
}
```

Stable exceptional codes:

| HTTP | Code | Public meaning |
| --- | --- | --- |
| 404/503 | `PUBLIC_SIGNUP_DISABLED` | This deployment is not accepting new public registrations. |
| 422 | `ACCOUNT_EMAIL_INVALID` | Address syntax/size is invalid; no account lookup state. |
| 429 | `RATE_LIMITED` | Generic operation limit with bounded `Retry-After`. |
| 503 | `ACCOUNT_LIFECYCLE_UNAVAILABLE` | A required authoritative dependency failed closed. |

Duplicate-account state never receives a 409 or identifying message. An unused identifier creates one pending registration, pending-owned identifier claim, current challenge, delivery, and job atomically. A live pending identifier may schedule a throttled redelivery of its same current token. A stale pending identifier is reclaimed/redacted and freshly reserved in the same transaction. None of these branches accepts a password, extends the original 72-hour lease, or creates a user/session/workspace.

## 4. Verification Resend

### `POST /api/v1/auth/email-verification/resend`

Request:

```json
{
  "email": "user@example.test",
  "locale": "ar"
}
```

All account states receive the same 202 body as registration. A live pending registration outside cooldown with an unexpired current challenge receives one new delivery generation for the same token; the challenge and 72-hour retention deadline are unchanged. If the challenge expired but the pending lease remains live, one new challenge/delivery may replace it atomically. A stale pending registration is reclaimed before a fresh registration may be created. Ineligible/cooldown/daily-ceiling states do not create delivery work. A rate-limited response may be 429 with generic `RATE_LIMITED` and `Retry-After`, but cannot state whether the identity exists.

## 5. Email Verification Consumption

### `POST /api/v1/auth/email-verification/consume`

Request:

```json
{
  "token": "<opaque-token-from-fragment>",
  "password": "a password-manager value",
  "password_confirmation": "a password-manager value",
  "locale": "en",
  "return_path": "/dashboard"
}
```

Password fields are 12–128 Unicode characters, must match, and are accepted only in this token-bearing request. `return_path` is optional, contains no token fragment, and is backend-resolved after activation. The first successful consume atomically creates the normal public user, adaptive credential, verified identifier, personal workspace, owner membership, and consumed challenge; it returns 200, sets the existing `presenton_session` cookie after commit, and returns only the activated current account plus an approved redirect:

```json
{
  "state": "completed",
  "code": "EMAIL_VERIFICATION_COMPLETED",
  "authenticated": true,
  "redirect_path": "/en/dashboard"
}
```

Safe result matrix:

| HTTP | Code | State/action |
| --- | --- | --- |
| 200 | `EMAIL_VERIFICATION_COMPLETED` | One atomic activation; common cookie may be set. |
| 200 | `EMAIL_VERIFICATION_ALREADY_COMPLETED` | Replay/already verified; no new cookie or transition; offer sign-in. |
| 400 | `EMAIL_VERIFICATION_EXPIRED` | No state change; offer generic resend. |
| 400 | `EMAIL_VERIFICATION_INVALID` | Malformed, wrong-purpose, revoked, wrong-generation, or unknown; no account detail. |
| 422 | `ACCOUNT_PASSWORD_MISMATCH` | Confirmation mismatch; token remains unconsumed. |
| 422 | `ACCOUNT_PASSWORD_POLICY` | First password fails the local approved policy; token remains unconsumed. |
| 429 | `RATE_LIMITED` | IP/challenge budget reached. |
| 503 | `EMAIL_VERIFICATION_RETRYABLE` | Atomic user/credential/provisioning/dependency failure; token remains eligible when safe. |

Exactly one concurrent consumer can return `COMPLETED`. If two valid requests submit different passwords, only the committed winner's hash exists; the loser cannot replace it. The already-completed response contains no stored identifier and issues no cookie.

## 6. Unified Login (Existing, Compatible Extension)

### `POST /api/v1/auth/login`

Preferred request:

```json
{
  "identifier": "email-or-existing-username",
  "password": "existing-or-current-password",
  "return_path": "/dashboard"
}
```

Compatibility request remains accepted:

```json
{
  "username": "existing-username",
  "password": "legacy-six-character-or-longer-value"
}
```

If both `identifier` and `username` are present they must normalize identically or the request is 422. Login keeps the historical six-character minimum for existing passwords; it does not apply new-password policy until a password is created/reset.

Success remains 200 with the existing cookie and response fields, plus additive account context and backend-approved `redirect_path`.

| HTTP | Code | Behavior |
| --- | --- | --- |
| 200 | success | Existing cookie contract; legacy/adaptive hash upgrade preserved. |
| 401 | `AUTH_INVALID_CREDENTIALS` | Same result after applicable dummy/real password work for a pending-owned identifier claim, absent identity, wrong password, disabled/deactivated user, ineligible alias, and all other unauthenticated failure states. |
| 429 | `AUTH_RATE_LIMITED` / `RATE_LIMITED` | Stable generic limit; no account state. |
| 503 | `AUTHENTICATION_UNAVAILABLE` | Existing deployment availability behavior. |

The backend resolves `return_path` against current role/workspace/capabilities. Client code uses only returned `redirect_path` and otherwise falls back to the localized Dashboard.

The existing canonical operation-control boundary is the final login admission authority across instances. It enforces trusted-IP admission, privacy-safe identifier and IP/identifier failure scopes, and global limits; returns the greatest applicable bounded `Retry-After` without naming the scope; and clears matching failure scopes only after successful credential verification. Raw username/email values never enter Redis keys. The process-local login limiter is removed from the request path before public email login can enable.

## 7. Forgot Password

### `POST /api/v1/auth/password/forgot`

Request:

```json
{
  "email": "user@example.test",
  "locale": "ar"
}
```

Recoverable, absent, pending, username-only, disabled/deactivated, primary-admin, and alias-collision states all return:

- HTTP 202

```json
{
  "status": "accepted",
  "code": "RECOVERY_REQUEST_ACCEPTED"
}
```

Only malformed input, generic rate limiting, feature disable, or fail-closed dependency availability may differ; none discloses eligibility.

## 8. Password Reset

### `POST /api/v1/auth/password/reset`

Request:

```json
{
  "token": "<opaque-token-from-fragment>",
  "password": "a new password-manager value",
  "password_confirmation": "a new password-manager value"
}
```

Success returns 200, does not issue a cookie, and requires sign-in:

```json
{
  "state": "completed",
  "code": "PASSWORD_RESET_COMPLETED",
  "authenticated": false,
  "redirect_path": "/en/recovery-complete"
}
```

| HTTP | Code | State/action |
| --- | --- | --- |
| 200 | `PASSWORD_RESET_COMPLETED` | Hash/challenge/session-version transaction committed. |
| 400 | `PASSWORD_RESET_EXPIRED` | No mutation; offer a new forgot-password request. |
| 400 | `PASSWORD_RESET_USED` | No second mutation; offer sign-in/new request. |
| 400 | `PASSWORD_RESET_INVALID` | Malformed, wrong-purpose, revoked, wrong-generation, disabled/ineligible, or unknown; no account detail. |
| 422 | `ACCOUNT_PASSWORD_MISMATCH` | Confirmation mismatch. |
| 422 | `ACCOUNT_PASSWORD_POLICY` | Local password policy failure. |
| 429 | `RATE_LIMITED` | Generic IP/challenge limit. |
| 503 | `ACCOUNT_LIFECYCLE_UNAVAILABLE` | Safe fail-closed dependency error; no partial password change. |

Exactly one concurrent consumer can return `PASSWORD_RESET_COMPLETED`. Every prior browser JWT fails on its next authoritative read because `auth_version` increments atomically.

## 9. Authenticated Password Change

### `POST /api/v1/auth/password/change`

Requires a current active browser session plus the common same-origin mutation controls. Request:

```json
{
  "current_password": "the current password",
  "new_password": "a distinct password-manager value",
  "new_password_confirmation": "a distinct password-manager value"
}
```

The backend locks the canonical `User`, rechecks that the JWT `auth_version` equals the persisted generation and the account remains active, verifies `current_password` through the existing password helper, rejects a `new_password` that verifies against the current hash, applies the canonical 12–128/common-password policy and confirmation rule, replaces the adaptive hash, revokes all outstanding password-reset challenges, appends a safe audit event, and increments `auth_version` exactly once in one transaction.

Success returns 200, deletes `presenton_session`, issues no replacement cookie or session credential, and requires sign-in again:

```json
{
  "success": true,
  "code": "PASSWORD_CHANGED",
  "authenticated": false,
  "redirect_path": "/en/"
}
```

| HTTP | Code | State/action |
| --- | --- | --- |
| 200 | `PASSWORD_CHANGED` | Hash/version/challenge/audit transaction committed; caller cookie deleted; sign in again. |
| 400 | `ACCOUNT_PASSWORD_CURRENT_INVALID` | Current password was not accepted; no state changed. |
| 422 | `ACCOUNT_PASSWORD_UNCHANGED` | New password matches the current credential; no state changed. |
| 422 | `ACCOUNT_PASSWORD_MISMATCH` | New-password confirmation mismatch; no state changed. |
| 422 | `ACCOUNT_PASSWORD_POLICY` | New password fails the canonical local policy; no state changed. |
| 401 | `AUTH_REQUIRED` | Session is missing, stale, or no longer eligible, including a concurrent losing request; no state changed. |
| 429 | `RATE_LIMITED` | Canonical authenticated credential-mutation IP/safe-user/global budget reached. |
| 503 | `ACCOUNT_LIFECYCLE_UNAVAILABLE` | Safe fail-closed dependency error; no partial credential change. |

The canonical operation controller—not a password-specific limiter—enforces the mutation and failed-current-password budgets using trusted IP, safe user UUID, combined, and global scopes. A default maximum of five failed current-password attempts per user/IP pair in 15 minutes applies unless operators tighten it. Password values and hashes never enter control keys or telemetry.

Two requests authenticated with the same session generation can have at most one winner. The lock-time generation/hash recheck prevents a losing request from overwriting the winning hash. All pre-change cookies, including the winning caller's cookie, fail the next backend check.

## 10. Logout (Existing)

### `POST /api/v1/auth/logout`

Existing response remains `{"success": true}` and deletes the current cookie. The route adopts the common same-origin mutation requirements. It does not claim to revoke other browser sessions.

## 11. Global Browser Session Revocation

### `POST /api/v1/auth/sessions/revoke-all`

Requires the current browser session and common same-origin mutation controls. Atomically increments the current account's `auth_version`, appends a safe event, commits, and deletes the current cookie.

Success:

```json
{
  "success": true,
  "code": "SESSIONS_REVOKED"
}
```

It introduces no device/session inventory and does not alter separately governed administrator API credentials.

## 12. Locale Preference (Existing)

`GET /preferences/locale` remains unchanged. `PUT /preferences/locale` retains its request/response and adds the common same-origin mutation enforcement. Registration locale is stored directly on the pending registration and carried into email/template selection.

## 13. Feature-Flag Semantics

| Capability | Controls | Ordinary rollback behavior |
| --- | --- | --- |
| `publicSignup` | New registration and pending re-registration issuance | Stops new account/challenge issuance. |
| `emailVerification` | New verification challenge/resend issuance | Stops new/resend issuance; accepted valid consume remains available. |
| `passwordRecovery` | New forgot-password/reset challenge issuance | Stops new issuance; accepted valid reset consume remains available. |
| `notificationDelivery` | Notification scheduling/worker delivery readiness | Kept on until accepted work drains; cannot be enabled without canonical durable jobs. |

An emergency account-challenge consumption disable is operator-only and not advertised as routine rollback. Contradictory production combinations return fail-closed readiness/service errors and cannot be bypassed by calling application services directly.

Pending-registration lazy/hourly reclamation and terminal redaction are maintenance/security behavior, not public issuance capabilities. They continue when public flags are disabled. Production public-email login and lifecycle readiness also require canonical Redis login enforcement, successful token golden-vector checks, and an acceptable pending-reconciliation backlog; the legacy process-local login limiter cannot satisfy readiness.

## 14. Cookie Contract

No verification/reset cookie is added. Successful login and first successful verification use the current cookie:

- name `presenton_session` (legacy compatibility);
- JWT strategy/audience and `auth_version` unchanged;
- `HttpOnly`;
- `SameSite=Lax`;
- path `/`;
- bounded 30-day maximum age;
- `Secure` under validated production HTTPS/proxy configuration.

Reset, administrator reset, global revocation, authenticated password change, and deactivation invalidate earlier JWTs through `auth_version`/activity checks. Authenticated password change deletes the caller cookie after commit and deliberately issues no replacement credential.

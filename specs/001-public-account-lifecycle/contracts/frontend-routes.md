# Contract: Public Account Routes and States

- **Framework**: Next.js App Router
- **Locale behavior**: Flat routes are exposed as `/en/...` and `/ar/...` by the existing locale proxy
- **Authorization**: Navigation only; FastAPI remains authoritative

## Route Ownership

Public routes live in `app/(public-account)` outside the protected `(presentation-generator)` layout. Interactive behavior, API types, safe-state mapping, return-target logic, and token handoff live in `features/account-lifecycle`. The current root route remains the only login entry point.

| Route | Required states | Primary actions |
| --- | --- | --- |
| `/` | session checking, sign-in idle/submitting, generic invalid credentials, rate limited, unavailable, session expired, success redirect | Sign in with verified email or existing username; register; forgot password |
| `/register` | idle, email validation, submitting, generic accepted, rate limited, unavailable | Submit email/locale only; go to sign in |
| `/check-email` | generic accepted, delivery delayed guidance, rate limited, generic failure | Go to resend; go to sign in |
| `/verification-required` | generic check-email guidance reached from registration/verification UX, loading, failure | Enter email again for resend; go to sign in; never infer state from login |
| `/resend-verification` | idle, submitting, generic accepted, cooldown/rate limited, unavailable | Request resend without displaying stored account data |
| `/verify` | handoff/loading, first-password form, validation/submitting, completed, already completed, expired, invalid/malformed, rate limited, retryable user/workspace failure, generic failure | Set/confirm first password with the in-memory token; continue using backend-approved path; sign in; resend |
| `/forgot-password` | idle, validation, submitting, generic accepted, rate limited, unavailable | Submit email; return to sign in |
| `/reset-password` | handoff/loading, form, validation, submitting, completed, expired, used, invalid/malformed, rate limited, unavailable | Set/confirm password; request another reset |
| `/recovery-complete` | completed | Return to unified sign in |
| `/account` (existing protected route) | loading, authenticated identity, verified email or admin-managed recovery, locale, password-change idle/validation/submitting/success/current-invalid/unchanged/policy/rate/stale-session/failure, revoke-all confirmation/success/failure | Change password; change locale; current logout; revoke all browser sessions; sign in again after password-change success |

Verification/reset sub-states remain on their owning route; they are not encoded in query parameters. Duplicate/live/stale registration, resend, and forgot submissions use the same generic acknowledgement state. The frontend never collects a registration password and never treats an identifier as verification-pending based on a login response.

## Route Loading and Error Boundaries

`app/(public-account)/loading.tsx` and `app/(public-account)/error.tsx` are explicit shared route-boundary owners for all public account pages. They must use the story-owned English/Arabic catalog keys, render with inherited `lang`/`dir` and logical layout, expose a semantic status/heading, preserve keyboard focus and visible focus, and provide a bounded retry or safe navigation action. Error copy is generic and never renders exception text, account state, token data, provider detail, or deployment capability reasons. These boundaries are presentation/recovery surfaces only; they never authorize a route or infer lifecycle eligibility.

## Shared Form/State Contract

Every interactive route must provide:

- an explicit heading and instructions in the selected locale;
- associated labels and described validation/errors;
- correct autocomplete (`email`, `username`, `current-password`, `new-password`), with first-password fields present only after a verification token has been scrubbed into memory;
- visible keyboard focus, Enter submission, no focus trap, and deterministic error-summary focus;
- live status announcement that never contains a raw token or hidden account state;
- disabled submitting state and duplicate-submit prevention;
- bounded request timeout and a recoverable retry/navigation action;
- reduced-motion behavior;
- usable layout at 320 CSS pixels and 200% text zoom;
- logical-direction styles, `lang`, `dir`, and bidi-isolated LTR email values under Arabic RTL;
- no change to presentation canvas geometry or renderer state.

EN and AR catalogs must have identical `accountLifecycle.*` keys and variables for all states.
Each story that introduces UI owns its required EN/AR keys in the same change. Final localization convergence may normalize terminology and detect parity/unused/RTL regressions, but it is not the first owner of story strings.

## Token Handoff Contract

Token links use fragments:

```text
/{locale}/verify#token=<opaque>
/{locale}/reset-password#token=<opaque>
```

On either route, before application analytics or result rendering:

1. disable Mixpanel/page-view initialization for the route;
2. read and size/format-bound the fragment;
3. call `history.replaceState` to remove the fragment;
4. retain the value only in transient component/module memory;
5. POST it in the same-origin JSON body with the common CSRF header; verification submits the user's first password/confirmation in that same request, while reset submits the replacement password/confirmation;
6. erase the in-memory reference after terminal response/navigation.

The token must never enter query/search parameters, server/proxy URLs, referrers, `localStorage`, `sessionStorage`, cookies, IndexedDB, DOM text/attributes/accessibility names, clipboard helpers, console/errors, screenshots, analytics, or long-lived React/global state. Token pages set `no-store`, `no-referrer`, contain no third-party resources, and sanitize global error reporting.

## Safe Return Contract

The frontend extends the existing `safeReturnPath` only as a pre-filter. It rejects:

- absolute or scheme-relative URLs;
- backslash/encoded scheme-relative variants;
- `/api`, `/_next`, `/app_data`, static/internal endpoints;
- login/logout/register/verification/reset loops;
- any fragment, especially a token-bearing fragment.

The candidate is sent to FastAPI on login/verification consumption. Navigation uses only the backend-returned localized `redirect_path`; otherwise it uses the localized Dashboard. Server-layout and session-monitor redirects use the same helper and preserve only permitted path/query data.

## Public Capability Contract

Before rendering registration, verification, resend, or recovery actions, unauthenticated pages consume only the public `/api/v1/auth/status` product-availability booleans `publicSignup`, `emailVerification`, `passwordRecovery`, and `notificationDelivery`. This shared surface is implemented before the pages and never exposes dependency health reasons, environment values, keys, account existence, or an authenticated user's state. A false capability selects a localized unavailable/recovery state; it is not authorization, and direct backend calls still enforce the same server-owned gate.

## Frontend Account Contract

The UI treats these response fields as display/navigation context only:

- `account_identifier`;
- `username` for legacy compatibility;
- `role`;
- `account_origin`;
- `account_state`;
- `email_verification_state`;
- `recovery_eligible`;
- lifecycle/runtime capabilities;
- current workspace/capabilities returned by existing backend contracts.

The UI never derives verification, recovery eligibility, role, admin authority, workspace membership, or ownership from identifier syntax or local storage. Direct protected/admin route calls remain backend-enforced.

Authenticated password change posts current password, distinct new password, and confirmation through the shared same-origin API adapter. The form uses `current-password` and `new-password` autocomplete, maps only stable backend codes to localized states, and never retains/logs password values. On `PASSWORD_CHANGED`, it clears protected client state, treats the session as ended, and navigates to the localized sign-in path supplied by the backend; it never creates a replacement session or attempts selective caller-session preservation.

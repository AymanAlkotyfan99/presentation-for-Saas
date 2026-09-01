# Contract: Transactional Account Email

- **Status**: Internal design contract
- **Owner**: `servers/fastapi/modules/notifications`
- **Scope**: Verification and password-reset delivery only

## Boundary

The notification module accepts a stable `notification_id`, calls the shared identity lifecycle eligibility repository to load the authoritative pending-registration-or-user challenge subject, reconstructs the bearer token only in memory from the frozen binary contract, renders deterministic localized content, and invokes one configured transport. It is not an AI provider, marketing platform, user-selectable provider, or independent retry queue. The eligibility repository is a blocking identity foundation and must exist before worker integration; the worker may not duplicate lifecycle queries or trust stale payload state.

Conceptual protocol:

```text
TransactionalEmailTransport.send(message, idempotency_key) -> DeliveryOutcome
TransactionalEmailMessage:
  recipient       # process memory only
  sender
  reply_to?       # reviewed operator value only
  subject
  text_body
  html_body
  message_id      # deterministic from notification UUID

DeliveryOutcome:
  category        # DELIVERED | RETRYABLE_PRE_ACCEPTANCE | PERMANENT_REJECTION | AMBIGUOUS
  safe_code       # finite internal enum
```

ORM rows, request objects, SMTP response strings, provider SDK objects, and exceptions never cross this protocol.

## Configuration Contract

Production configuration is server-only and includes:

- provider selection fixed to `smtp` for this sprint;
- SMTP hostname/port;
- strict transport mode (`TLS` or reviewed `STARTTLS`), never plaintext in production;
- username/password or equivalent operator credential;
- reviewed sender address/display name and optional reply-to;
- exact HTTPS `NEXT_PUBLIC_URL` used to construct action links;
- connect/read timeout and message-size ceiling within reviewed maxima.

Secrets are not placed in `NEXT_PUBLIC_*`, database rows, jobs, templates, logs, traces, or responses. Readiness fails closed if production delivery is enabled with missing credentials, invalid sender/origin, plaintext transport, unhealthy DNS/address policy, or an unavailable notification worker.

## Job Contract

- Operation: `account.notification.deliver.v1`
- Queue: canonical `notification` queue
- Authority: registered `SYSTEM_ACCOUNT_LIFECYCLE` only
- Maximum attempts: 3

Payload:

```json
{
  "notificationId": "00000000-0000-0000-0000-000000000000"
}
```

The payload and job result contain no email, token/link, password/hash, cookie, template/body, provider credential/response, local path, presentation data, or arbitrary metadata. The canonical job submission secret-key validator must explicitly reject fields named or suffixed like `token`, `email`, `recipient`, `address`, `link`, `body`, `password`, `cookie`, and `secret` for this operation.

## Handler Preconditions

Immediately before provider effect, the handler must prove:

- job definition and authority kind match the registered lifecycle operation;
- notification exists and is eligible/non-terminal;
- referenced challenge exists, is current, unconsumed, unrevoked, and unexpired;
- purpose, notification delivery generation, and challenge binding match;
- verification subject is a live pending registration before `reclaim_after`, or reset subject is an eligible active user;
- verification pending-claim/reset `auth_version` binding generation still matches;
- notification delivery and required issuance capability were valid when accepted;
- current emergency policy does not prohibit effect;
- locale is `en` or `ar` and matching templates are present.

Failure of a current-authority check suppresses safely; it never sends stale mail.

## Idempotency and Retry

- One delivery row exists per accepted `(challenge_id, delivery_generation)`; initial issuance uses 1.
- Job idempotency uses the notification UUID and system scope.
- RFC `Message-ID` is deterministic from the notification UUID and approved sender domain.
- A delivered/failed/unknown/suppressed terminal row is an idempotent no-op.
- Known pre-acceptance DNS/connect/TLS/SMTP-4xx failures map to canonical retry classes.
- Configuration/authentication and permanent SMTP rejection are non-retryable.
- An ambiguous handoff or stale `DISPATCHING` state becomes `UNKNOWN_TERMINAL`; it is not automatically resent.
- The SMTP adapter performs no retry; canonical jobs alone own at most three attempts/backoff/dead letter.
- **Same-token redelivery while live**: an allowed registration/resend after cooldown creates a new delivery generation for the same still-current verification challenge/token and does not change challenge identity, bearer token, binding, expiry, or pending retention.
- **Replacement challenge only after expiry/invalidation**: only expiry, reclamation, or another authorized invalidating transition may replace the challenge; every old token then remains invalid.

Physical exactly-once SMTP copies are not promised after an ambiguous network handoff. The system guarantees bounded attempts, one effective current challenge across allowed redeliveries, deterministic per-delivery Message-ID, and no blind retry after ambiguity.

## Token Reconstruction Contract

Verification and reset delivery reconstruct only tokens matching `ba1.<ev|pr>.<kid>.<locator>.<secret>`. HMAC input is exactly the byte sequence frozen in [research.md](../research.md) and [data-model.md](../data-model.md): domain plus NUL, one-byte format/purpose, one-byte-length-prefixed ASCII key ID, RFC UUID bytes for challenge and subject, one-byte subject kind, and unsigned 64-bit big-endian binding generation. No `issued_at`, `expires_at`, locale, email, timezone, ORM, JSON, or database string representation participates.

The handler must reproduce both documented golden vectors before production readiness and cross-database tests must prove identical reconstruction after SQLite/PostgreSQL round trips. A derivation mismatch is terminal configuration failure; it never falls back to another serialization or sends a link.

## Template Contract

Backend catalogs contain the same keys and variables for `en` and `ar`:

```text
accountEmail.verification.subject
accountEmail.verification.heading
accountEmail.verification.body
accountEmail.verification.action
accountEmail.verification.expiry
accountEmail.verification.ignore
accountEmail.reset.subject
accountEmail.reset.heading
accountEmail.reset.body
accountEmail.reset.action
accountEmail.reset.expiry
accountEmail.reset.ignore
```

Creation and maintenance of this transactional email catalog is owned once by the notification-foundation implementation. Frontend story work never owns it; later localization convergence validates parity, interpolation, terminology, and bidi behavior and may add a newly approved key without recreating or splitting catalog authority.

Allowed variables are limited to product display name, action URL, and a localized expiry description. The renderer escapes variables, uses a fixed safe HTML shell plus a separately rendered plain-text body, sets `lang`/`dir`, and bidi-isolates unavoidable URLs. It does not echo the recipient address.

Messages contain no role, workspace, billing, subscription, presentation, prompt, upload, password, tracking pixel, remote analytics resource, or marketing copy. Verification copy may state that the recipient will choose a password after opening the secure Bayanly page, but never requests or embeds one in email. Verification states the earlier of its 24-hour maximum expiry and pending reclaim deadline; reset states 30-minute maximum expiry.

## SMTP Adapter Security

- Resolve and validate the operator-configured host using an explicitly reviewed DNS-pinning/address policy equivalent to `utils/outbound_http.py`; connect to the validated address while retaining TLS hostname verification.
- Bound DNS, connect, greeting, command, DATA, and overall operation time.
- Bound recipient count to one and total message bytes to the configured ceiling.
- Never follow redirects (not applicable to SMTP), use ambient proxy settings, downgrade TLS, or accept invalid certificates in production.
- Do not include secrets or full provider replies in exceptions. Map responses to finite safe codes.
- Log only safe notification/job IDs, attempt number, duration bucket, and outcome category.

## Test and Development Transport

`InMemoryTransactionalEmailTransport` retains captured messages only in process memory and is injectable by tests. It has no production registration, HTTP mailbox route, file output, or console logging. Manual local testing may point SMTP at an explicitly controlled local capture server; CI never calls a real external provider.

## Controlled Delivery Evidence

Automated transport/state-machine tests are necessary but do not alone satisfy SC-006. After the integrated worker path is ready, a controlled local/staging run using disposable PostgreSQL, shared Redis, canonical workers, and a local capture transport must record at least 100 accepted messages. `artifacts/account-lifecycle/acceptance/sc-006-delivery-run.json` records build/configuration identifiers, accepted and delivered-within-120-seconds counts, percentage, retry/redelivery counts, duplicate-effective-challenge count, and pass/fail result. It contains only safe notification/challenge IDs or aggregates—never recipients, bearer values/links, rendered content, provider replies, or credentials—and must prove at least 99% within two minutes with zero duplicate effective challenge generations before public enablement.

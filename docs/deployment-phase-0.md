# Phase 0 deployment runbook

Last reviewed: 2026-08-02

> **Release gate:** this repository is not ready for a paid, public launch. The
> procedures below define the safest Phase 0 deployment shape and the evidence a
> later release candidate must produce. They do not waive the open security,
> legal, reliability, or platform-qualification items in
> `docs/phase-0-baseline.md`.

## Intended topology

Use the server container only behind a TLS-terminating ingress or load balancer.
The minimum production-shaped environment has:

- an immutable Presenton image pinned by registry digest;
- an external PostgreSQL database on a private network;
- an external Redis deployment on a private network;
- a persistent encrypted volume or object/file storage arrangement for
  `/app_data`;
- a deployment secret manager that injects database, Redis, administrator, and
  provider credentials without committing or printing them;
- TLS at the ingress, with an explicitly audited proxy/header chain; and
- centralized logs, metrics, alerts, backups, and a tested restore destination.

The checked-in `docker-compose.yml` builds the application but does not create
PostgreSQL, Redis, TLS, backup jobs, monitoring, or highly available storage. It
is useful for development and a production-shaped smoke test, not a complete
production deployment definition.

Do not use SQLite, `DISABLE_AUTH=true`, an in-memory security-control backend, a
mutable image tag, or an Internet-exposed database/Redis service in production.

## Explicit commercial and architecture limitations

These limitations remain true after Phase 0 and must be carried into every
deployment/release decision:

- The product is not ready for a paid public launch.
- Local `/app_data` filesystem storage is not the final SaaS storage architecture.
  A single mounted volume is not a multi-region, tenant-isolated object-storage
  design and complicates replica scheduling, backups, and failover.
- Background/async presentation tasks are not the final durable job architecture.
  Database status rows do not by themselves provide a durable distributed queue,
  exactly-once processing, retry/dead-letter policy, worker isolation, or recovery
  after process loss.
- Billing, subscriptions, metering, credits, quota purchase, refunds, and related
  financial controls do not exist.
- Arabic and right-to-left authoring/rendering/export are incomplete and have not
  passed a commercial language-quality matrix.
- PPTX editability and fidelity are not commercially verified across supported
  Microsoft PowerPoint/LibreOffice versions, operating systems, fonts, templates,
  charts, and export paths.

Do not market around these limitations, emulate missing billing with ad hoc flags,
or treat Phase 0 controls as a replacement for the later SaaS architecture.

## Roles and approvals

Before a deployment, assign named owners for:

- application release and rollback;
- PostgreSQL migration, backup, and restore;
- Redis availability and namespace ownership;
- ingress/TLS/DNS;
- secret/provider credential rotation;
- security incident response; and
- asset/dependency license review.

One person may fill multiple roles in a small team, but the release record must
say who performed and who reviewed each irreversible step.

## Pre-deployment gate

Do not deploy until every applicable item is evidenced in the release record.

### Source and build

- [ ] The source revision is an immutable commit on the intended release branch.
- [ ] CI passed root tests, all FastAPI tests, Next.js tests/lint/build, Cypress,
      the redacting secret scan, export-integrity checks, and SBOM generation.
- [ ] `git diff --check` is clean and the release worktree contains no generated
      browser traces, screenshots with private data, credentials, or local `.env`.
- [ ] The image was built from the reviewed revision and both expected platform
      manifests were inspected.
- [ ] The deployment references `registry/name@sha256:<manifest-digest>`, not
      `latest`, `dev`, or another mutable tag.
- [ ] Vulnerability, SBOM, NOTICE, and asset-provenance reviews are recorded.
- [ ] Every enabled downloaded artifact has a recorded source, expected SHA-256,
      and completed legal/trust review.

### Data services

- [ ] PostgreSQL and Redis versions are pinned and have passed the chosen
      environment's compatibility test. Phase 0 does not yet publish a supported
      major-version matrix.
- [ ] PostgreSQL encryption in transit, authentication, least-privilege role,
      connection limit, point-in-time recovery, retention, and restore alerting
      are configured.
- [ ] Redis encryption/authentication, private network policy, eviction policy,
      memory alerting, and failover are configured. Security controls must not
      share a namespace with another environment.
- [ ] A pre-deployment PostgreSQL backup and matching `/app_data` snapshot exist,
      are encrypted, and have been restored successfully to an isolated target.
- [ ] Capacity exists for database connections. Application defaults are pool
      size 5, overflow 10, timeout 30 seconds, recycle 1800 seconds, and pre-ping
      enabled per process; multiply by the maximum replica count.

### Network and secrets

- [ ] The ingress is the only public path to the application. Ports 3000, 8000,
      8001, PostgreSQL, and Redis are private.
- [ ] TLS certificates, renewal, DNS, request-size limits, timeouts, and HSTS have
      been verified on the real hostname.
- [ ] The proxy preserves the original HTTPS scheme and an allowlisted client IP
      chain. `SECURITY_TRUSTED_PROXY_CIDRS` contains only actual trusted proxies.
- [ ] The deployment can prove the session cookie receives `Secure`, `HttpOnly`,
      `SameSite=Lax`, and `Path=/` through the production proxy path.
- [ ] Administrator and provider credentials come from the secret manager. Raw
      Docker Compose does not provide a first-class `_FILE` interface here; do
      not compensate with a committed or broadly readable environment file.
- [ ] `OUTBOUND_HTTP_ALLOWLIST` contains only required operator-controlled
      destinations and `OUTBOUND_HTTP_ALLOWED_PORTS` is minimal (normally 443).

### Required release flags

For the current Phase 0 production shape:

```text
PRESENTON_ENV=production
MIGRATE_DATABASE_ON_STARTUP=true          # bootstrap/migration instance only
SECURITY_CONTROL_BACKEND=redis
SECURITY_CONTROL_NAMESPACE=presenton:security:v1:<environment>
SECURITY_ADMIN_BYPASS_LIMITS=false
ENABLE_UNSAFE_CUSTOM_LAYOUTS=false
NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS=false
ENABLE_UNVERIFIED_PRESENTATION_EXPORT=false
ENABLE_ANONYMOUS_TRACKING=false
DISABLE_ANONYMOUS_TRACKING=true            # until notice/consent is approved
START_OLLAMA=false                          # unless a verified binary is built in
```

Also provide `DATABASE_URL`, `SECURITY_CONTROL_REDIS_URL` (or `REDIS_URL`), and
the initial administrator credentials through the secret manager. Never put a
real password into an example command.

## Secret generation and injection

- Generate the initial administrator password inside the approved password/secret
  manager with a cryptographically secure generator. The code minimum is eight
  characters, but deployment policy should require a unique random value of at
  least 20 characters and should not rely on human-composed examples.
- Let the database and Redis platforms generate independent least-privilege
  credentials. Do not reuse the administrator or a provider secret.
- Obtain provider credentials from the provider's authorized console with only
  the scopes/project/environment required.
- Presenton creates its own session-signing/recovery secret when provisioning the
  administrator and stores it in protected application configuration. Operators
  should not invent or commit a replacement value.
- Inject secrets directly from the deployment secret manager into the process.
  Ensure the platform masks them in configuration views, audit events, crash
  dumps, and logs. Restrict who can read values separately from who can trigger a
  deployment.
- Electron error reporting has no compiled destination and remains disabled when
  `SENTRY_ENABLED` is false/unset or `SENTRY_DSN` is absent. An approved opt-in
  must inject both settings explicitly; keep PII, tracing, logs, replay, and
  feedback flags false/unset unless each data flow has separate approval.
- Verify file/config backups use owner-only permissions and encrypted storage.
  Never copy a generated value through a ticket, chat, shell history, Compose
  file, Docker build argument, image layer, or CI output.

Record secret identifiers/versions and rotation dates in release evidence, never
the values.

## Database migration and initial bootstrap

Migrations run in FastAPI lifespan when `MIGRATE_DATABASE_ON_STARTUP` is exactly
`true` or `True`. The migration wrapper upgrades to Alembic head and contains
compatibility handling for recognized legacy schemas. Table creation, primary
administrator provisioning, ownership backfill, provider-setting migration, and
default-template import follow in startup order.

The administrator bootstrap uses a PostgreSQL transaction advisory lock plus a
unique primary-admin slot. That protects concurrent administrator creation. It
does **not** establish that every schema migration is safe to run concurrently.

Use this sequence:

1. Put the application into a maintenance window and stop all old replicas that
   can write.
2. Take a consistent PostgreSQL backup and matching `/app_data` snapshot.
3. Start exactly one new release instance with
   `MIGRATE_DATABASE_ON_STARTUP=true`, the production database/Redis settings,
   and first-boot administrator credentials from the secret manager.
4. Wait for startup to finish and verify `GET /api/v1/health/ready` returns HTTP
   200. Then verify `GET /api/v1/auth/status` returns HTTP 200 with
   `configured: true`. An unauthenticated auth-status response should report
   `authenticated: false`; that is expected.
5. Verify the Alembic revision from inside the running image:

   ```text
   cd /app/servers/fastapi
   alembic current
   alembic heads
   ```

   The current revision must equal the single repository head. Capture revision
   identifiers, not credentials, in the release record.
6. Log in through the real TLS hostname using a private operator session. Confirm
   the account is the primary administrator and existing owned data is present.
7. Remove `AUTH_PASSWORD` and the initial bootstrap value from the steady-state
   application environment. Ordinary later startups do not need them.
8. Start remaining replicas with `MIGRATE_DATABASE_ON_STARTUP=false`. Verify each
   replica and only then end maintenance.

For a brand-new database, the service fails closed if the secret manager did not
inject both a username of at least three characters and a password of at least
eight characters. There is no public HTTP setup endpoint. Detailed behavior and
recovery flags are in `docs/security/administrator-bootstrap.md`.

Do not run a generic `alembic stamp` against a populated database. The repository
migration wrapper has explicit legacy-schema inference; an incorrect manual stamp
can silently skip required data/schema work.

## Startup and health verification

The container exposes port 80. Nginx sends `/` to Next.js, `/api/v1` and
`/api/v2` to FastAPI, and `/mcp` to the MCP process.

FastAPI provides unauthenticated process and dependency probes. The image's
Docker `HEALTHCHECK` calls `GET /api/v1/health/ready` directly on FastAPI's
loopback port. Readiness returns 200 only when its SQL query and operation-control
backend health check pass; it returns 503 with per-check booleans otherwise.
Liveness proves only that the FastAPI process can respond. Neither endpoint
checks Nginx, Next.js, MCP, storage capacity, or external providers, so keep the
following layered probes and do not treat a single HTTP 200 as full readiness:

1. **Process/liveness:** `GET https://<host>/api/v1/health/live` returns HTTP 200
   and `{"status":"live"}` through the actual ingress and Nginx route.
2. **Database and operation controls:**
   `GET https://<host>/api/v1/health/ready` returns HTTP 200 and
   `{"status":"ready","checks":{"database":true,"operation_controls":true}}`.
   In production the latter check includes the configured Redis-backed controls.
3. **Administrator configuration:** `GET https://<host>/api/v1/auth/status`
   returns HTTP 200 and reports `configured: true` without disclosing secrets.
4. **Web UI:** `GET https://<host>/` returns the Next.js application and the
   browser can load static resources without mixed-content or CSP errors.
5. **Redis/security controls:** use the platform's authenticated Redis health
   probe, then perform a harmless controlled request that traverses an operation
   guard. Production operation requests must fail closed, not fall back to local
   memory, if Redis is unavailable.
6. **Authenticated ownership:** a non-admin test user sees only its own test data;
   the administrator can access the admin page; unauthenticated protected API
   calls return 401.
7. **Dependencies:** test only the provider(s), parsing path, and other features
   intentionally enabled for that environment. Avoid billable generation in a
   high-frequency health probe.

Alert separately on process death, HTTP latency/error rates, database pool
exhaustion, Redis unavailability, 429/503 rates, disk usage, backup failures,
provider errors, and repeated authentication failures. Logs must not contain
request bodies, provider keys, cookies, bearer tokens, uploaded document text, or
full outbound URLs with credentials/query secrets.

## TLS and response-header verification

TLS terminates outside the application. The external ingress must redirect HTTP
to HTTPS, use an approved TLS policy, renew certificates, and add HSTS only after
the domain is confirmed HTTPS-only. The application must receive the original
scheme as HTTPS so session cookies are secure.

From a clean client/network, inspect the final HTTPS response and confirm these
headers survive every proxy hop:

```text
Content-Security-Policy
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy
Cross-Origin-Opener-Policy
Strict-Transport-Security                 # ingress responsibility
```

Verify login response cookies separately. Also verify:

- the HTTP hostname redirects to the expected HTTPS hostname without reflecting
  an untrusted `Host` header;
- `/app_data` user content is inaccessible without authorization;
- `/docs` and `/openapi.json` exposure matches policy;
- `/mcp` rejects missing/invalid admin-generated bearer keys; and
- error responses do not disclose internal paths, stack traces, Redis/database
  URLs, or outbound-address validation details.

The current CSP retains `'unsafe-inline'` and broad HTTP(S) image/connect sources
for application compatibility. Do not describe it as a complete isolation
boundary; narrowing it is a later hardening gate.

## Rate and concurrency controls

Production must set `SECURITY_CONTROL_BACKEND=redis`. `auto` and `memory` are
development conveniences and are rejected when `PRESENTON_ENV=production`.
Missing/unhealthy Redis causes controlled operations to fail with 503.

Default policies are per minute unless noted:

| Operation | Subject rate / burst | Subject concurrency | Global concurrency | Lease seconds |
| --- | ---: | ---: | ---: | ---: |
| login | 10 / 5 | - | - | 120 |
| password | 5 / 3 | - | - | 120 |
| token_create | 10 / 4 | - | - | 120 |
| presentation_generation | 6 / 2 | 1 | 50 | 300 |
| outline_generation | 10 / 2 | 1 | 50 | 180 |
| slide_regeneration | 20 / 4 | 2 | 100 | 180 |
| ai_chat | 30 / 5 | 2 | 100 | 180 |
| image_generation | 20 / 4 | 2 | 50 | 300 |
| image_search | 30 / 6 | 3 | 100 | 120 |
| provider_discovery | 20 / 5 | 2 | 50 | 120 |
| web_search | 20 / 4 | 2 | 50 | 120 |
| file_upload | 30 / 6 | 2 | 100 | 120 |
| document_parsing | 10 / 2 | 1 | 30 | 600 |
| export | 10 / 2 | 1 | 20 | 600 |
| webhook_registration | 10 / 3 | - | - | 120 |
| webhook_delivery | 60 / 10 | 5 | 100 | 120 |
| admin | 60 / 10 | 5 | 50 | 120 |

Global rate defaults to 100 times the subject rate. Identities are scoped by
workspace/user when available, otherwise user, otherwise validated client IP.
Administrator bypass is off by default and does not bypass global protection.

Overrides follow:

```text
OPERATION_<UPPERCASE_NAME>_RATE_PER_MINUTE
OPERATION_<UPPERCASE_NAME>_BURST
OPERATION_<UPPERCASE_NAME>_GLOBAL_RATE_PER_MINUTE
OPERATION_<UPPERCASE_NAME>_CONCURRENCY
OPERATION_<UPPERCASE_NAME>_GLOBAL_CONCURRENCY
OPERATION_<UPPERCASE_NAME>_LEASE_SECONDS
```

Change limits only after load/abuse testing. Record old/new values and a rollback
threshold. Use a different Redis namespace for every environment and for test
runs. Do not flush a shared Redis database to reset Presenton counters.

## Emergency feature controls

`PRESENTON_DISABLED_OPERATIONS` accepts these operation identifiers:

```text
login,password,token_create,presentation_generation,outline_generation,
slide_regeneration,ai_chat,image_generation,image_search,provider_discovery,
web_search,file_upload,document_parsing,export,webhook_registration,
webhook_delivery,admin
```

Use the narrowest switch that contains an incident. Dedicated compatibility
flags also exist:

| Flag | Effect |
| --- | --- |
| `DISABLE_PRESENTATION_GENERATION=true` | Stops presentation and outline generation paths covered by the operation policies. |
| `DISABLE_AI_CHAT=true` | Stops AI chat. |
| `DISABLE_IMAGE_GENERATION=true` or `DISABLE_AI_IMAGE_GENERATION=true` | Stops AI image generation. |
| `DISABLE_PROVIDER_DISCOVERY=true` | Stops provider/model discovery. |
| `DISABLE_WEB_SEARCH=true` | Stops web search. |
| `DISABLE_FILE_PROCESSING=true` | Stops guarded document parsing. |
| `DISABLE_EXPORT=true` | Stops guarded exports. |
| `DISABLE_WEBHOOK_DELIVERY=true` | Stops guarded webhook delivery. |
| `ENABLE_UNVERIFIED_PRESENTATION_EXPORT=false` | Keeps the unreviewed bundled export runtime unavailable. |
| `ENABLE_UNSAFE_CUSTOM_LAYOUTS=false` | Keeps executable custom-layout compilation unavailable. |

Emergency procedure:

1. declare the incident and assign an incident commander;
2. capture redacted timestamps, versions, metrics, and request IDs;
3. apply the narrowest flag through normal audited deployment configuration;
4. verify both blocked and unaffected paths;
5. rotate affected credentials following `docs/security/secret-response.md`;
6. preserve sanitized evidence; and
7. remove the flag only after the fix, regression tests, and explicit approval.

Do not use `DISABLE_AUTH=true` as an emergency availability switch.

## Backups and restore

Treat PostgreSQL and `/app_data` as one consistency set. Redis contains ephemeral
rate/concurrency state and normally does not need application backup, although its
platform configuration must be recoverable.

### Backup

1. Record the application image digest, application version, Alembic revision,
   PostgreSQL version, and artifact-policy revision.
2. Quiesce writes by entering maintenance and stopping application replicas. The
   repository has no general read-only/maintenance mode; feature flags alone do
   not cover every write path.
3. Create a PostgreSQL custom-format dump or managed point-in-time snapshot using
   the database platform's secret injection. Do not put the connection URL on the
   command line or in logs.
4. Snapshot/copy the entire `/app_data` volume while writes remain stopped.
5. Encrypt both artifacts, store them under the same backup-set identifier, and
   record hashes, retention, and access policy.
6. Restart only after both sides complete or the maintenance decision is rolled
   back.

`userConfig.json` and its backup are sensitive even though passwords are hashed;
they can contain provider keys and session-signing material. Backup access must be
at least as restricted as the production secret store.

### Restore test

At a regular cadence and before a high-risk release:

1. provision an isolated network, new PostgreSQL database, new Redis namespace,
   and empty data volume;
2. restore the database and matching data snapshot;
3. deploy the exact recorded application digest with outbound provider access
   disabled or pointed at test accounts;
4. run migrations only if the restore test deliberately includes an upgrade;
5. verify login, ownership, representative presentations/assets, and export only
   if export is approved;
6. record duration, data loss window, warnings, and cleanup; and
7. securely destroy the restored secrets and data after review.

A backup is not accepted until this restore succeeds.

## Roll forward and rollback

Prefer a tested roll forward for an application-only defect when schema/data are
healthy. Use rollback when the new release cannot be safely repaired inside the
recovery objective.

### Application rollback without schema change

1. enable relevant kill switches and stop new release replicas;
2. redeploy the previous immutable image digest with its recorded configuration;
3. verify health, authentication, ownership, and core paths; and
4. retain the failed release's redacted diagnostics.

### Rollback after migration or data mutation

Do not point old code at a schema it was not tested against, and do not assume
Alembic downgrades are data-safe.

1. stop all writers;
2. preserve a forensic snapshot of the failed state;
3. restore the pre-deployment PostgreSQL backup and matching `/app_data` snapshot
   to a new target where possible;
4. deploy the previous image digest against the restored target and a fresh Redis
   namespace;
5. validate in isolation, switch traffic, then monitor; and
6. retain/expire the failed environment according to incident policy.

Blue/green deployment does not solve shared-database incompatibility. Each side
must use a schema and mutable-data set compatible with its image.

## Credential rotation

### Primary administrator

Use a one-time deployment with a new secret-manager value and either
`AUTH_OVERRIDE_FROM_ENV=true` or `RESET_AUTH=true`. Both require
`AUTH_PASSWORD`; an optional `AUTH_USERNAME` changes the existing primary
username. The operation preserves the user ID, increments the auth version,
rotates signing/recovery material, and revokes existing API tokens.

After successful login verification, remove the one-time flag and password from
the steady-state environment, deploy again, and verify old browser/API tokens no
longer work.

### Provider, database, Redis, TLS, and CI credentials

1. create a replacement with least privilege;
2. deploy it from the secret manager without logging either value;
3. verify through a safe identity/health operation;
4. revoke the old credential;
5. inspect provider/platform audit logs; and
6. update rotation metadata and alerting.

For database/Redis credentials, use the platform's overlap/dual-credential
mechanism or a controlled restart so active pools drain safely. For a suspected
repository exposure, follow `docs/security/secret-response.md`; deleting a file
does not revoke a credential or remove Git history.

## Updating external artifacts

Every export runtime, Chromium, ImageMagick, model, or other downloaded executable
update is a supply-chain change:

1. identify the immutable upstream release and all platform assets;
2. obtain hashes from an independently authenticated channel or independently
   download and hash the expected files;
3. verify signatures/provenance where the upstream supports them;
4. complete vulnerability and legal/license review;
5. update version metadata and `config/artifact-integrity.json` atomically;
6. run metadata tests, forced sync, check-only verification, clean rebuilds, SBOM
   generation, secret scan, and every native platform test;
7. inspect package contents and confirm the installed executable hash is recorded;
8. publish an immutable application artifact and record its digest; and
9. only then consider enabling the feature.

Never accept a new digest merely because a download failed the old digest. Do not
use `ALLOW_UNVERIFIED_ELECTRON_CHROMIUM_DOWNLOAD` or
`ENABLE_UNVERIFIED_PRESENTATION_EXPORT` in a release pipeline as a substitute for
review.

## Required release test matrix

Attach an evidence link and named reviewer for every row. "Not applicable" needs
a reason.

| Area | Minimum cases |
| --- | --- |
| Server architecture | Fresh install and upgrade on `linux/amd64` and `linux/arm64`. |
| Database | Qualified PostgreSQL version: fresh migration, legacy upgrade, concurrent bootstrap attempt, pool exhaustion, restart, backup, point-in-time restore. SQLite only for local regression. |
| Redis | Normal, unavailable at startup/request, failover, latency, lease renewal, rate exhaustion, concurrency exhaustion, namespace isolation. |
| Authentication | No-secret fail-closed boot, first bootstrap, login/logout, rotation/recovery, token revocation, admin/non-admin authorization, brute-force limits. |
| Proxy/TLS | HTTP redirect, TLS policy, original scheme/IP, Secure cookie, security headers, hostile Host/X-Forwarded headers, request-size limit. |
| Data isolation | Two users across presentations, slides, templates, images, uploads, exports, fonts, tasks, chat, webhooks, admin APIs. |
| Outbound security | Loopback/private/link-local/metadata/IPv6/DNS-rebinding/redirect blocks, allowlisted public target, timeout and size limits. |
| Generation | Each enabled LLM/image/web-search provider with test credentials; disabled providers fail safely. |
| Parsing | Approved file types, malformed/oversized files, LiteParse/OCR availability, resource limits, malicious filenames/content. |
| Export | Disabled-default behavior; if legally approved, every platform archive/integrity path and PPTX/PDF smoke tests. |
| Browser UI | Supported browser versions once defined; login, generation, editing, admin, headers/CSP, accessibility smoke, telemetry disabled. |
| Desktop | Each advertised native OS/architecture; sandbox/IPC, install/uninstall, code signing/notarization, update, local data migration, offline behavior. |
| Operations | Rolling restart, crash recovery, disk-full, database/Redis outage, alert delivery, log redaction, kill switches, rollback timing. |
| Supply chain/legal | Clean locked install, secret scan, SBOM validation, NOTICE reproduction, asset provenance, vulnerability/license policy. |

Until this matrix is complete and reviewed, a build remains a pre-release test
artifact.

## Known disabled or constrained features

- Bundled presentation export is disabled by default because the export runtime's
  license/trust review is unresolved.
- The unsafe export opt-in can preserve external HTTP(S) image/assets from imported
  converter HTML and therefore creates a headless-browser egress/SSRF boundary.
  Until Sprint 16 replaces that path, keep the flag off in production; any isolated
  evaluation must deny browser egress except explicitly approved origins.
- Electron export Chromium acquisition/packaging is blocked without a pinned
  platform archive hash.
- Executable custom layouts are disabled by default; their development opt-in is
  not supported for public deployments.
- Runtime source-code layout creation is removed.
- Runtime Ollama installation is removed. Use a verified built-in binary or an
  approved remote service.
- Authentication-disabled mode is limited to the local Electron/isolated
  development use case. MCP is disabled in Electron.
- MySQL, exact PostgreSQL/Redis majors, public browser versions, and all desktop
  targets lack a completed Phase 0 qualification matrix.
- Rootless application-container execution, readiness coverage beyond the SQL
  database and operation controls, and complete OS/model/native-artifact SBOM
  coverage remain open.
- Static asset provenance and several native/downloaded artifact legal reviews
  remain unresolved; see `docs/license-and-asset-provenance.md`.

## Deployment evidence record

For every environment change, retain at minimum:

- source revision, image digest, application/export versions, and artifact-policy
  revision;
- redacted configuration diff and enabled/disabled feature list;
- database/Redis versions, Alembic before/after revisions, and backup-set ID;
- CI, SBOM, secret, vulnerability, license, platform, and smoke-test results;
- migration/start/end times, health/metric screenshots without private content,
  and approvers;
- rollback digest, restore set, and decision thresholds; and
- incidents, exceptions, expiration dates, and owners.

Never include passwords, provider keys, session cookies, access tokens, private
presentation content, raw database URLs, or secret-bearing query strings in that
record.

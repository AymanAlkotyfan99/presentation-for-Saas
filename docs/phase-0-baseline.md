# Phase 0 engineering baseline

Last reviewed: 2026-08-02

This document records the repository as it exists at the end of the Phase 0
stabilization work. It is an engineering baseline, not a claim that the product
is ready for a paid, public, multi-tenant launch. When this document says that a
target is "buildable," that does not mean it has completed release qualification.

The sources of truth are the lockfiles and executable configuration in this
repository. If this document conflicts with a lockfile, container file, or tested
runtime guard, the executable source wins and this document must be corrected in
the same change.

## System shape

A server/container deployment is one image that supervises four local processes:

1. Nginx listens on container port 80 and routes browser/API traffic.
2. Next.js listens only on `127.0.0.1:3000`.
3. FastAPI listens only on `127.0.0.1:8000`.
4. The MCP HTTP server listens only on `127.0.0.1:8001` and is exposed through
   Nginx at `/mcp`.

`start.js` initializes `/app_data`, creates or updates `userConfig.json`, starts
the processes, and waits for Next.js startup output plus
`GET /api/v1/auth/status` from FastAPI. The data volume holds the default SQLite
database, provider configuration, generated presentations, uploaded files,
images, fonts, templates, exports, and Mem0 data.

The Electron application embeds the same Next.js and FastAPI applications on
random loopback ports. It defaults to `DISABLE_AUTH=true` because it is a
single-user local desktop process; it also disables the MCP server. That desktop
exception is not a supported server deployment configuration.

## Active implementation map

| Area | Active implementation at Phase 0 |
| --- | --- |
| FastAPI | `servers/fastapi/api/main.py` composes routers and middleware; `api/lifespan.py` performs migrations/bootstrap/imports; `server.py` runs loopback Uvicorn. SQLAlchemy/SQLModel services and Alembic live under `services/`, `models/sql/`, and `alembic/`. |
| Next.js | The App Router application is under `servers/nextjs/app/`, with server utilities in `lib/`, shared UI in `components/`, route mediation in `proxy.ts`, and a standalone production build configured by `next.config.mjs`. |
| Electron | `electron/app/main.ts` owns the desktop lifecycle, loopback child servers, BrowserWindow, security settings, and IPC registration. `electron/build.js` and scripts under `electron/scripts/` produce native resources/installers. |
| Authentication | `servers/fastapi/api/v1/auth/` implements users, JWT cookie sessions, admin-generated API keys, login/logout/status/verify, and deployment bootstrap. `SessionAuthMiddleware` protects server routes; Next.js proxy/server-role helpers gate UI paths. |
| First-run setup | `api/v1/auth/bootstrap.py` provisions the sole primary administrator from deployment secrets under a database lock/unique slot. Public `POST /api/v1/auth/setup` no longer exists. Electron is the explicit local auth-disabled exception. |
| Markdown | `servers/nextjs/lib/safe-markdown.ts` is the centralized renderer for block/inline Markdown. `MarkDownRender`, document preview, outline, and inline slide text import it. Raw HTML/event/style/script protocols are not accepted as Markdown output. |
| Custom layouts | Bundled declarative templates remain under `templates/`. Runtime source writing is removed. Legacy database/browser executable layout compilation is gated by `lib/unsafe-custom-layouts.ts` and separate server/browser opt-ins that must stay false in production. |
| Provider discovery | FastAPI OpenAI-compatible, Anthropic, Google, and Ollama endpoints call `utils/available_models.py`/`utils/ollama.py`. Discovery is guarded as the `provider_discovery` operation and outbound requests use centralized validation. |
| Webhooks | `/api/v1/webhook` subscription routes persist owner-scoped SQL records after outbound URL validation. `services/webhook_service.py` sends deliveries with an optional bearer secret through secure outbound HTTP and the `webhook_delivery` operation guard. |
| Export runtime | Next.js export routes use `lib/presentation-export-policy.ts` and `run-bundled-presentation-export.ts`; backend export helpers/tasks apply the same environment gate. Root/Electron sync scripts download and verify `presenton-export`; the feature defaults disabled pending review. |
| Docker | Digest-pinned multi-stage `Dockerfile` builds FastAPI, Next.js, locked Node assets, and the verified export archive; `Dockerfile.dev` is the bind-mounted development image. `start.js` supervises Nginx/Next/FastAPI/MCP. |
| CI and tests | `.github/workflows/test-all.yml` runs root, FastAPI, Next.js, Cypress, and Electron jobs. `secret-scan.yml` runs the redacting scanner. Tests live in root `scripts/*.test.mjs`, `servers/fastapi/tests/`, `servers/nextjs/tests/`/`cypress/`, and `electron/tests/`. |
| Package metadata | Public version/export relationships live in root and Electron package/lockfiles plus `config/artifact-integrity.json`; `scripts/package-metadata.test.mjs` enforces them. Each ecosystem has its own lockfile. |
| Python runtime | `servers/fastapi/pyproject.toml` and `uv.lock` define the Python 3.11 environment. `api/__init__.py` invokes `utils/runtime_version.py` before API startup. |
| License/notices | Root/backend `LICENSE` and `NOTICE` files declare the project and generated dependency notices. CycloneDX generation is in `scripts/generate-sbom.mjs`; limitations and asset status are documented in the two license/SBOM documents. |

## Pinned and supported toolchain

| Component | Phase 0 baseline | Evidence and scope |
| --- | --- | --- |
| Node.js (root, Next.js, server image) | `20.19.6` | `.node-version` and `.nvmrc`; CI reads `.nvmrc`. Server Docker stages use a digest-pinned Node 20 Bookworm image. |
| Node.js (Electron development tooling) | `22.17.1` | `electron/.node-version` and `electron/.nvmrc`; this satisfies Electron 42's declared `>=22.12.0` host-Node engine. Electron CI reads the nested pin. |
| Python | exactly `3.11.x` | `.python-version`, `requires-python = ">=3.11,<3.12"`, and the import-time guard in `servers/fastapi/api/__init__.py`. Python 3.10 and 3.12 are deliberately rejected. |
| npm | lockfile-based `npm ci` | `package-lock.json`, `servers/nextjs/package-lock.json`, and `electron/package-lock.json` are authoritative. The npm executable version is not separately pinned; this remains a reproducibility gap. |
| uv | `0.7.22` in Docker and CI | Docker copies uv from a digest-pinned `ghcr.io/astral-sh/uv:0.7.22` image and CI requests the same version. There is no repository-native developer version file, so install 0.7.22 when reproducing resolution locally. |
| Next.js / React | Next.js `16.2.12`; React and React DOM `19.2.6` | Exact direct versions in `servers/nextjs/package.json`; the lockfile pins the full graph. |
| Electron | Electron `42.2.0` | Exact development dependency in `electron/package.json`; the Electron lockfile pins the full graph. |
| Backend packaging | `uv.lock` under Python 3.11 | Run `uv sync --locked --dev`. The uv index policy is `first-index`, which prevents a package name from being selected from a later index once found on an earlier one. |

Do not replace `npm ci` with `npm install`, or `uv sync --locked` with an
unlocked install, in CI or release builds.

## Platform targets and qualification status

### Development environments

The repository does not yet contain a completed host-development qualification
matrix. The reproducible server baseline is the Linux container/Compose path.
Native FastAPI and Next.js work is expected to use the pinned Node/Python
toolchains above; `test-local.sh` requires a POSIX-compatible shell. Individual
`npm` and `uv` commands are portable to Windows, macOS, and Linux, but that alone
is not evidence that every native converter, browser, or packaging path works on
each host. Build and test Electron installers on their actual target operating
system with Node 22.17.1 and that platform's signing/packaging toolchain. Do not
claim another host as supported until its development, test, and packaging smoke
matrix is recorded.

### Server container

The Docker release workflow builds `linux/amd64` and `linux/arm64`. Base images
are pinned by digest. Chromium is installed from a dated Debian security snapshot.
These are the current build targets.

There is not yet a committed platform qualification report proving the full
generation, parsing, export, backup, restore, and rollback matrix on both
architectures. Treat both architectures as pre-release until that evidence is
attached to a release.

### Desktop

The documented packaging targets are:

- macOS on Apple Silicon and Intel (`.dmg`);
- Windows x64 (`.exe`); and
- Linux x64 (`.deb`).

The build scripts also contain Mac App Store and signed/notarized macOS paths.
Signing, notarization, store review, auto-update, and installer behavior require
native-platform qualification. The repository does not contain evidence that
all of those targets passed a Phase 0 release matrix.

### Databases and browsers

- SQLite is the default when `DATABASE_URL` is unset. It is supported for local,
  single-process development and desktop use, not a horizontally scaled public
  service.
- PostgreSQL is the required production database topology. The code supports
  `postgresql://` URLs using asyncpg at runtime and psycopg for migrations.
  No exact PostgreSQL major-version support matrix is committed yet. Qualify and
  pin the chosen managed/database version before release.
- MySQL URL conversion exists in `utils/db_utils.py`, but there is no Phase 0
  deployment qualification. It is not a recommended production target.
- Redis is required for production rate and concurrency controls. No exact Redis
  server version support matrix is committed yet. Qualify and pin it alongside
  the application release.
- No end-user browser support matrix is committed. Next.js production builds and
  Cypress component tests using Cypress's Electron browser are the current
  automated evidence only.

## External executables and downloaded artifacts

The container workflow requires Docker Engine with Compose v2; their exact
developer versions are not pinned and must be recorded in reproducibility
evidence. Native development requires the Node/npm, Python/uv, and shell
environment described above. Electron packaging additionally depends on the
target operating system's native signing/installer toolchain. The following
runtime/build artifacts are separate from package-manager dependencies:

| Artifact | Pinned baseline | Acquisition and status |
| --- | --- | --- |
| Presentation export runtime | `v0.4.2` | Platform archives from the `presenton/presenton-export` GitHub release are SHA-256 pinned in `config/artifact-integrity.json`. License/trust review is unresolved, so production use is disabled unless `ENABLE_UNVERIFIED_PRESENTATION_EXPORT=true`. |
| Docker Chromium | Debian package `149.0.7827.196-1~deb13u1`, snapshot `20260625T180000Z` | Installed during image build and held. It is used by Puppeteer/export paths. Debian OS-package license inventory is not yet generated by the repository SBOM command. |
| Electron export Chromium | Chrome build `149.0.7827.196`; macOS build IDs `1625085` and `1625072` | Upstream archive SHA-256 values are not yet in policy. Acquisition requires an explicit unverified-download override and is not release-approved. |
| ImageMagick for Electron | `7.1.2-18` | Known portable/AppImage archive hashes are in `config/artifact-integrity.json`; legal review remains open. The server image installs the Debian ImageMagick package instead. |
| spaCy English model | `en_core_web_sm 3.8.0` | Docker uses `ADD --checksum` with the recorded SHA-256. Legal review remains open. |
| Tesseract | Debian `tesseract-ocr` and English data | Optional at image build through `INSTALL_TESSERACT`; exact Debian package version is not separately recorded. |
| LiteParse | npm `@llamaindex/liteparse` dependency | Locked through npm. The runner is `electron/resources/document-extraction/liteparse_runner.mjs`; container and Electron reuse it. |
| FastEmbed model data | Not downloaded or shipped by default | Default icon search uses the bundled lexical catalog. Semantic icon search requires both `ENABLE_SEMANTIC_ICON_SEARCH=true` and `ALLOW_UNVERIFIED_FASTEMBED_MODELS=true`; Mem0 also defaults off. Exact model files/revisions remain unapproved and absent from the artifact BOM. |
| Ollama | Not downloaded at runtime | `START_OLLAMA=true` fails if an approved binary was not built into the image. Configure an approved remote `OLLAMA_URL` or build a verified artifact. |

The artifact integrity file records bytes and source locations. A matching hash
does not establish license permission, provenance, or security approval.

## Configuration baseline

There is intentionally no tracked `.env` file. Store secrets in the deployment
platform's secret manager and inject them at runtime. Do not place real values in
Compose files, images, shell history, CI logs, support tickets, or documentation.

### Required for an authenticated server deployment

- `PRESENTON_ENV=production`;
- `APP_DATA_DIRECTORY` (the image sets `/app_data`);
- a production `DATABASE_URL` using PostgreSQL;
- initial `AUTH_USERNAME` and `AUTH_PASSWORD` supplied through a secret store;
- `MIGRATE_DATABASE_ON_STARTUP=true` for the current single-step deployment
  process;
- `SECURITY_CONTROL_BACKEND=redis`;
- `SECURITY_CONTROL_REDIS_URL` (or `REDIS_URL`) pointing to the deployment's
  private Redis instance; and
- `SECURITY_CONTROL_NAMESPACE`, unique per environment.

The service fails closed when no administrator exists and valid bootstrap
credentials are absent. The retired public setup endpoint must not be restored.
See `docs/security/administrator-bootstrap.md`.

### Security and emergency controls

- `ENABLE_UNSAFE_CUSTOM_LAYOUTS=false` in production. The browser build must also
  leave `NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS` false/unset.
- `ENABLE_UNVERIFIED_PRESENTATION_EXPORT=false` until the export package's legal
  and trust reviews close.
- `OUTBOUND_HTTP_ALLOWLIST` and `OUTBOUND_HTTP_ALLOWED_PORTS` constrain operator-
  configured destinations. Public/private/link-local address checks and redirect
  validation still apply.
- `SECURITY_TRUSTED_PROXY_CIDRS` identifies only proxies the application actually
  trusts for client-IP attribution. An empty value is safest until the network
  path is known.
- `SECURITY_ADMIN_BYPASS_LIMITS` defaults false and should remain false.
- `PRESENTON_DISABLED_OPERATIONS` is a comma-separated emergency kill switch.
  Per-feature flags include `DISABLE_PRESENTATION_GENERATION`, `DISABLE_AI_CHAT`,
  `DISABLE_IMAGE_GENERATION`, `DISABLE_AI_IMAGE_GENERATION`,
  `DISABLE_PROVIDER_DISCOVERY`, `DISABLE_WEB_SEARCH`, `DISABLE_FILE_PROCESSING`,
  `DISABLE_EXPORT`, and `DISABLE_WEBHOOK_DELIVERY`.
- Per-operation limits use `OPERATION_<NAME>_RATE_PER_MINUTE`, `_BURST`,
  `_GLOBAL_RATE_PER_MINUTE`, `_CONCURRENCY`, `_GLOBAL_CONCURRENCY`, and
  `_LEASE_SECONDS`. Defaults live in `api/operation_security.py` and should be
  load-tested before override.

### Provider and optional-service configuration

Provider keys and model/base-URL settings are enumerated in `docker-compose.yml`
and `README.md`. They include OpenAI, Google, Vertex, Azure OpenAI, Bedrock,
Anthropic, OpenRouter, Fireworks, Together, Cerebras, LiteLLM, LM Studio, Ollama,
custom OpenAI-compatible services, image providers, and web-search providers.

Provider base URLs, webhook targets, Ollama, ComfyUI, Open WebUI, SearXNG, and
other operator URLs are outbound-network inputs. Production should allowlist
only required hostnames and ports. Never use broad private-network exemptions.

Set `CAN_CHANGE_KEYS=false` when provider configuration is controlled by the
deployment. Pseudonymous usage analytics are opt-in: they require
`ENABLE_ANONYMOUS_TRACKING=true` and no active disable setting; Compose defaults
enable to false and disable to true. Keep those safe defaults until telemetry
notice/consent review is complete. FastAPI Sentry is disabled without
`SENTRY_DSN` and defaults `send_default_pii` to false. Electron has no compiled
error-reporting destination: it requires both `SENTRY_ENABLED=true` and an
explicit environment-provided `SENTRY_DSN`; PII, tracing, logs, replay, and
feedback remain separately opt-in.

## Storage and data ownership

`APP_DATA_DIRECTORY` contains mutable application data. In the container that is
`/app_data`, normally backed by the host `./app_data` directory. Important paths
include:

- `fastapi.db` when SQLite fallback is used;
- `userConfig.json` and its backup, which can contain provider configuration and
  authentication recovery material;
- `exports/`, `images/`, `uploads/`, `fonts/`, `templates/`,
  `pptx-to-html/`, and `pptx-to-json/`;
- `mem0/` and related local model/vector data.

The application source tree is immutable at runtime. The former request handler
that wrote `.tsx` layouts has been removed. Mutable layouts/templates must use
data storage, not source files. See `docs/security/runtime-layout-source.md`.

PostgreSQL is authoritative for accounts, ownership, presentations, templates,
slides, tasks, access tokens, provider settings, and other SQL models. Files in
the data volume and rows in the database form one logical backup set; backing up
only one side can produce dangling references.

## Install, start, build, and test commands

### Repository and web development

```text
# repository tools
npm ci
npm test

# Next.js
cd servers/nextjs
npm ci
npm test
npm run lint
npm run build
npm run dev
```

### FastAPI development

Create isolated application/temp directories, then:

```text
cd servers/fastapi
uv sync --locked --dev
uv run --locked python server.py --port 8000 --reload true
```

The server will not start in authenticated mode on an empty database without
deployment bootstrap credentials. For isolated, loopback-only development,
`DISABLE_AUTH=true` is permitted. Never use that setting on a reachable server.

### Container development and production-shaped builds

```text
docker compose build development
docker compose up development

docker compose build production
docker compose up production
```

The production service requires externally supplied PostgreSQL, Redis, and
administrator secrets; the checked-in Compose file does not provision those
services. Follow `docs/deployment-phase-0.md` instead of treating the Compose
default as a complete production stack.

### Electron development and packaging

```text
cd electron
npm run setup:env
npm run dev
npm run typecheck
npm run build:all
```

Desktop builds that include export Chromium remain blocked until the platform
archives have pinned hashes and legal review is complete. Run Electron tooling
with a host Node version satisfying Electron's declared `>=22.12.0` engine; the
repository pins that host runtime to 22.17.1 under `electron/`.

### Local aggregate checks

On a Unix-like development environment:

```text
./test-local.sh
```

`test-local.sh` mirrors the commands below, including SBOM, Compose, Cypress,
Electron, and secret-scan checks. It does not reproduce GitHub-hosted runner
isolation or automatically switch between the repository's Node 20 pin and the
Electron Node 22 pin; the authoritative CI workflow runs each job with its
declared toolchain:

- root `npm ci`, repository tests, export download/integrity verification, and
  Node SBOM generation;
- `uv sync --locked --dev`, all FastAPI pytest tests, and Python SBOM generation;
- Next.js `npm ci`, Node tests, ESLint, production build, and Cypress component
  tests;
- Electron `npm ci`, security tests, TypeScript build/type validation, and main-
  process undefined-symbol validation under Node 22.17.1; and
- a separate redacting repository secret scan.

Useful focused checks are:

```text
python scripts/scan_secrets.py
npm run sbom
git diff --check
```

## Phase 0 security implementation baseline

- First-run administrator creation is deployment-time, transaction-protected,
  and race-safe. Public account claiming is removed.
- Browser/API sessions and data access are owner-scoped; admin operations require
  an administrator principal.
- Operation rate and concurrency controls have Redis and development-memory
  backends. Production rejects the memory backend and fails closed when Redis is
  unavailable.
- Outbound HTTP validation rejects unsupported schemes, embedded credentials,
  prohibited ports, private/loopback/link-local/reserved targets, unsafe DNS
  results, and unsafe redirects. An explicit hostname allowlist can narrow access.
- Markdown is rendered through the centralized safe renderer. Next.js emits CSP
  and baseline browser security headers.
- Unsafe executable custom layouts and the unreviewed export runtime are disabled
  by default.
- Artifact downloads use HTTPS and recorded SHA-256 values where policy exists.
  Runtime `curl | sh` installers were removed.
- Python is constrained to 3.11 and uv uses first-index resolution.
- Python advisory scanning is exact-pinned in the uv development lock and runs in
  CI against the synchronized environment.
- Secret scanning is redacting and enforced in CI. Incident handling is described
  in `docs/security/secret-response.md`.

## Known limitations and open release blockers

The following are factual limitations, not accepted production risk:

- This baseline is **not paid-launch ready**. PostgreSQL, Redis, browser, desktop,
  backup/restore, failover, load, abuse, and rollback matrices are not complete.
- The checked-in Compose topology has no PostgreSQL or Redis service and is not a
  highly available deployment definition.
- The application processes in the server image run as root; only Nginx workers
  drop to `www-data`. Container privilege reduction remains open.
- FastAPI exposes process-local `/api/v1/health/live` and dependency-aware
  `/api/v1/health/ready` endpoints. The Docker `HEALTHCHECK` calls readiness on
  loopback. Readiness currently verifies the SQL database and operation-control
  backend; it does not prove Nginx, Next.js, MCP, storage capacity, or external
  providers are healthy, so layered external probes remain required.
- Nginx/TLS proxy trust must be explicitly verified. The application does not
  terminate TLS and does not itself emit HSTS. Secure-cookie behavior must be
  tested through the real proxy chain.
- CSP still needs `'unsafe-inline'` for the current Next.js/template renderer and
  allows broad HTTP(S) image/connect destinations. It is a baseline mitigation,
  not a final tenant isolation boundary.
- Mixpanel has no compiled project token. Telemetry remains off unless both the
  explicit opt-in flag and `NEXT_PUBLIC_MIXPANEL_TOKEN` are configured;
  autocapture/session replay are disabled. Enabling it still requires a reviewed
  notice/consent, data-map, retention, and incident-response decision.
- The presentation export runtime has verified bytes but unresolved license and
  trust status. Electron export Chromium lacks archive hashes. Export remains
  disabled by default.
- If the explicit unsafe export flag is enabled for evaluation, imported converter
  HTML may retain external HTTP(S) asset URLs that Chromium can fetch. This is a
  documented browser-egress/SSRF boundary requiring network isolation until the
  Sprint 16 provider replacement enforces an origin allowlist.
- Static templates, fonts, icons, screenshots, videos, and example images lack a
  complete provenance record. See `docs/license-and-asset-provenance.md`.
- Package-manager and policy-derived external-artifact SBOM generation still
  does not fully cover Debian OS packages, extracted runtime contents, FastEmbed
  model files, Electron export Chromium, or packaged desktop/native artifacts.
  Docker release builds request an SBOM attestation, but its scanner/coverage and
  reconciliation to the final image still require release review.
- npm itself and developer-installed uv are not pinned by a package-manager
  version declaration; CI and Docker explicitly select uv 0.7.22.
- SQLite cannot provide a supported multi-replica production topology.
- Development URLs and wildcard standalone FastAPI CORS are convenience paths;
  production must use the same-origin Nginx/ingress path.

## Intentional Phase 0 breaking changes

- `POST /api/v1/auth/setup` is removed. New server instances require
  deployment-time administrator credentials.
- `POST /api/save-layout` is removed. Runtime requests cannot write executable
  source into the application tree.
- Legacy executable custom layouts are disabled unless both server and browser
  development-only flags are explicitly enabled.
- Presentation export is disabled unless
  `ENABLE_UNVERIFIED_PRESENTATION_EXPORT=true` is explicitly set.
- Production operation controls require Redis; an in-process limiter is no longer
  an accepted production fallback.
- Missing/unverified Ollama and export artifacts fail instead of being installed
  through unverified runtime shell pipelines.
- The FastAPI process now rejects every Python minor version except 3.11.
- uv resolves a package name from the first index on which it appears rather than
  choosing the best version across indexes.

## Version update policy

The public application version is `0.9.3-beta`. It must match in root
`package.json`, root `package-lock.json`, `electron/package.json`, and
`electron/package-lock.json`. The Next.js and FastAPI package versions (`0.1.0`)
are internal package metadata and do not replace the public application version.

The export runtime has an independent version, currently `v0.4.2`. It must match
root `presentationExportVersion`, Electron `exportVersion`, and
`config/artifact-integrity.json`.

Every version change must:

1. state whether it is an application release, export-runtime update, dependency
   update, or external-artifact update;
2. update every authoritative metadata/lockfile location atomically;
3. update artifact URLs, all platform hashes, build IDs, and manifests when bytes
   change;
4. regenerate lockfiles only with the supported toolchain and review the complete
   dependency diff;
5. regenerate SBOMs and dependency notices, then complete license and vulnerability
   review;
6. run the full CI, secret scan, integrity checks, platform test matrix, and
   `git diff --check`;
7. record breaking configuration, migration, rollback, and disabled-feature
   changes in release notes; and
8. publish immutable image/artifact digests. Deployments must pin those digests,
   not a mutable `latest` or `dev` tag.

`node --test scripts/package-metadata.test.mjs` enforces the metadata relationships
that can be checked automatically. A checksum update is a security-sensitive
review: derive it from an independently verified upstream artifact, never by
copying the digest printed after an unexpected download.

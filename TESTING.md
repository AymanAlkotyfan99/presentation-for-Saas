# Bayanly testing and quality checks

The commands below exist in the current repository and mirror `.github/workflows/test-all.yml`, `.github/workflows/secret-scan.yml`, and `.github/workflows/quality.yml`. Use Node 20.19.6 for root/Next.js work, Node 22.17.1 for Electron, Python 3.11, and uv 0.7.22. Run `npm ci`/`uv sync --locked --dev` after switching OS or toolchain; copied `node_modules` can contain incompatible native binaries.

On Windows PowerShell, use `npm.cmd` if the local execution policy blocks `npm.ps1`.

## Mandatory local checks

Every change runs these fast repository checks from the root:

```bash
npm run check:governance
npm run check:architecture
npm run localization:check
npm run canonical:check
npm run product:metadata:check
npm run brand:scan
python -m unittest scripts/tests/test_scan_secrets.py
python scripts/scan_secrets.py
docker compose config --quiet
git diff --check
```

`check:governance` validates required governance files, local Markdown links, declared paths, workflow action pinning, and the governance workflow contract. `check:architecture` validates route ownership, dependency directions, deprecated renderer ingress, runtime source generation, and generated-artifact hygiene.

For a documentation-only change outside governance, run relevant link/reference checks plus `git diff --check`. For governance, architecture, security, configuration, generated-contract, or workflow changes, the complete mandatory group above applies.

## FastAPI

Install and run the complete suite from `servers/fastapi`:

```bash
uv sync --locked --dev
APP_DATA_DIRECTORY=/tmp/bayanly-tests/app-data \
TEMP_DIRECTORY=/tmp/bayanly-tests/temp \
DATABASE_URL=sqlite+aiosqlite:////tmp/bayanly-tests/test.db \
DISABLE_ANONYMOUS_TRACKING=true \
DISABLE_IMAGE_GENERATION=true \
uv run --locked python -m pytest --verbose --tb=short
uv run --locked python -m compileall -q api models services utils
uv run --locked python scripts/generate_openapi_spec.py --check
uv run --locked python scripts/check_migrations.py
```

Run the narrowest relevant test first. Examples:

```bash
uv run --locked python -m pytest tests/integration/test_auth_endpoints.py
uv run --locked python -m pytest tests/unit/test_session_auth_middleware.py tests/unit/test_owner_isolation.py tests/unit/test_workspace_rbac.py
uv run --locked python -m pytest tests/unit/test_outbound_http_security.py tests/unit/test_operation_security.py
uv run --locked python -m pytest tests/unit/test_presentation_document.py tests/unit/test_revision_persistence.py tests/integration/test_presentation_document_api.py
uv run --locked python -m pytest modules/jobs/tests/test_durable_jobs.py
uv run --locked python -m pytest modules/assets/tests/test_assets.py
uv run --locked python -m pytest modules/providers/tests/test_providers.py modules/providers/tests/test_provider_business_cutover.py
```

Migration changes require the graph check and the PostgreSQL smoke path used by CI:

```bash
MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DISPOSABLE_DB \
uv run --locked python scripts/check_migrations.py
```

The script refuses a non-empty database. PostgreSQL/Redis/MinIO integration suites also fail closed unless their environment points at explicitly disposable local services; otherwise they skip. Do not aim them at shared or production resources.

## Next.js

From `servers/nextjs`:

```bash
npm ci
npm test
npm run check:i18n
npm run check:canonical
npm run lint
NEXT_PUBLIC_FAST_API=http://localhost:8000 \
NEXT_PUBLIC_URL=http://localhost:3000 \
npm run build
```

There is no separate type-check script; `next build` is the repository's TypeScript/build validation. Use focused Node tests during development, for example:

```bash
node --test tests/safe-markdown.test.mjs tests/security-headers.test.mjs
node --test tests/auth-bootstrap-policy.test.mjs tests/settings-access.test.mjs tests/workspace-rbac.test.mjs
node --test tests/i18n-coverage.test.mjs tests/i18n-routing.test.mjs tests/locale-format.test.mjs
node --test tests/presentation-document.test.mjs tests/renderer-boundaries.test.mjs tests/revision-persistence.test.mjs
```

Run browser coverage for affected interaction/routing surfaces:

```bash
npm run test:locale-e2e
npm run test:cypress
```

`test:product-e2e` is an available focused product-journey command, but is not currently a CI gate.

## Electron

Use the Electron-specific Node version from `electron/.nvmrc`, then from `electron` run:

```bash
npm ci
npm test
npm run lint:main
```

`npm test` builds TypeScript before running the Electron security tests. `lint:main` rebuilds and runs the main-process undefined-symbol check.

## Change matrix

| Change | Required validation |
| --- | --- |
| Small implementation change | Mandatory root checks, focused regression test, owning app lint/type/build check as applicable |
| FastAPI behavior | Focused pytest, full pytest, compileall; OpenAPI check when routes/schemas are touched |
| Next.js behavior | Focused Node test, `npm test`, ESLint, production build; locale/Cypress tests for affected UI |
| Electron behavior | `npm test` and `npm run lint:main` |
| Auth, admin, workspace, or RBAC | Auth middleware/endpoints plus owner/workspace/RBAC tests; frontend tests are supplemental only |
| Provider or outbound networking | Provider boundary tests, outbound HTTP security tests, operation controls, deterministic failure cases; no live paid provider |
| Durable job | Idempotency, authority revalidation, lease/restart, cancellation, finite retry/dead-letter tests |
| Asset/storage | Ownership, traversal/symlink, MIME/checksum, quarantine/scanner, capability expiry, cleanup tests |
| Presentation/editor/renderer | Canonical schema check, document/revision tests, command/renderer tests, Arabic/LTR parity where applicable |
| Localization/RTL | Root localization check, i18n Node tests, locale E2E, manual English/Arabic review |
| Migration | Unit migration tests, single-head graph, disposable PostgreSQL upgrade/idempotency smoke |
| Security-sensitive | All relevant backend and frontend security suites, secret scan, threat-boundary manual review |

## CI checks

- `quality.yml` runs dependency-free governance, architecture, generated-contract, localization, product identity, secret, and Compose gates on pushes to and pull requests targeting `dev`, `staging`, and `production`.
- `test-all.yml` runs on the same three push/pull-request targets and installs locked dependencies, audits high-severity dependency findings, runs root tests, all FastAPI pytest tests, compile/OpenAPI/migration checks, Next.js unit/lint/build/locale/Cypress checks, Electron tests/main validation, export integrity, Compose validation, and SBOM generation.
- `secret-scan.yml` independently scans tracked text files on the same three push/pull-request targets.
- Real AI credentials and production secrets are not CI inputs. Provider behavior is tested through fakes or controlled local HTTP servers. Unavailable providers must produce bounded normalized failures, not retries without limit or fallthrough around policy.

## Known baseline blockers

The governance-audit baseline blockers were remediated on 2026-08-30. Under the documented CI
configuration with `DISABLE_IMAGE_GENERATION=true`, the exact targeted FastAPI platform/security
baseline now completes with `150 passed, 1 skipped`. The remaining skip reports that symlink
creation is unavailable for the Windows test account. The three formerly failing tests remain
active and passing; they were not skipped, xfailed, weakened, suppressed, or allowed to continue
on error.

The checked-in `servers/fastapi/openai_spec.json` was synchronized through
`scripts/generate_openapi_spec.py`, and `uv run --locked python scripts/generate_openapi_spec.py
--check` passes. This evidence clears the named governance-audit blockers only; the broader suite
and all other mandatory gates must still be run and reported for each affected change.

## Manual acceptance and E2E

Before production merge, supplement CI with the relevant manual checks:

- sign in/out, session expiry, normal-user versus admin navigation, direct forbidden API calls, and resource enumeration attempts;
- switching workspaces and verifying that presentations, members, jobs, assets, and provider settings never cross tenant boundaries;
- English LTR and Arabic RTL shell, keyboard navigation, focus order, narrow viewport, and mixed-direction presentation content;
- generation cancellation/failure and provider-unavailable UX without real paid calls unless a separately approved staging exercise exists;
- presentation create/edit/reload/conflict/recovery and renderer parity for the rollout mode being changed;
- Docker same-origin startup/readiness and any explicitly enabled Redis, object-storage, or durable-worker dependency;
- migration backup, forward upgrade, rollback/compatibility plan, and operator runbook for production schema changes.

No check may be silently ignored. Record skipped suites, unavailable disposable services, and environment-specific failures in the handoff.

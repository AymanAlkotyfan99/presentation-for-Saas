# GitHub Actions workflows

## Test All Applications (`test-all.yml`)

The test workflow runs on pushes and pull requests to `main`, and can also be
started manually. It enforces the checks that exist in the current repository:

- repository tooling: template-converter tests and bundled export verification;
- FastAPI: every pytest test using the Python version and locked dependencies
  declared in `servers/fastapi`;
- Next.js: all Node.js unit tests, ESLint, a production build, and Cypress
  component tests;
- Electron: security tests plus TypeScript/main-process validation;
- repository policy: Docker Compose validation, checksum-mismatch regressions,
  and reproducible CycloneDX SBOMs retained as workflow artifacts.

No test step is allowed to fail silently.

## Run the CI checks locally

Install Node.js 20.19.6 for repository/Next.js work, Node.js 22.17.1 for
Electron, npm, Python 3.11, and uv 0.7.22. The checked-in `.nvmrc`,
`electron/.nvmrc`, and `.python-version` files are authoritative. Run each
group below; together they mirror the GitHub Actions workflow.

## Run one test group

### FastAPI

```bash
cd servers/fastapi
uv sync --locked --dev
mkdir -p /tmp/presenton-tests/app-data /tmp/presenton-tests/temp
APP_DATA_DIRECTORY=/tmp/presenton-tests/app-data \
TEMP_DIRECTORY=/tmp/presenton-tests/temp \
DATABASE_URL=sqlite+aiosqlite:////tmp/presenton-tests/test.db \
DISABLE_ANONYMOUS_TRACKING=true \
DISABLE_IMAGE_GENERATION=true \
uv run --locked python -m pytest --verbose --tb=short
```

### Next.js

```bash
cd servers/nextjs
npm ci
npm test
npm run lint
NEXT_PUBLIC_FAST_API=http://localhost:8000 \
NEXT_PUBLIC_URL=http://localhost:3000 \
npm run build
npm run test:cypress
```

### Repository tooling

```bash
npm ci
npm test
npm run sync:presentation-export
npm run check:presentation-export
npm run sbom:node
```

### Electron

```bash
cd electron
npm ci
npm test
npm run lint:main
```

### Complete SBOM set

```bash
npm run sbom
```

Outputs are written to the ignored `artifacts/sbom/` directory. Review the
policy and exception process in `docs/sbom-and-license-policy.md`.

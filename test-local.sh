#!/usr/bin/env bash

# Aggregate the checks enforced by the repository's GitHub Actions workflows.
# GitHub-hosted jobs remain authoritative for isolated Node 20/Node 22 runners.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED_CHECKS=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_check() {
    local name="$1"
    shift

    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}${name}${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if "$@"; then
        echo -e "${GREEN}✓ ${name} passed${NC}"
    else
        echo -e "${RED}✗ ${name} failed${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
    echo
}

test_repository_tools() {
    cd "$SCRIPT_DIR" &&
        npm ci &&
        npm audit --audit-level=high &&
        npm test &&
        npm run check:architecture &&
        npm run product:metadata:check &&
        npm run brand:scan &&
        npm run sync:presentation-export &&
        npm run check:presentation-export &&
        npm run sbom:node &&
        docker compose config --quiet
}

test_fastapi() (
    cd "$SCRIPT_DIR/servers/fastapi" || return 1
    local test_root="${TMPDIR:-/tmp}/presenton-tests"
    local app_data_path="$test_root/app-data"
    local temp_path="$test_root/temp"
    local database_path="$test_root/test.db"

    mkdir -p "$app_data_path" "$temp_path" || return 1
    if command -v cygpath >/dev/null 2>&1; then
        app_data_path="$(cygpath -m "$app_data_path")" || return 1
        temp_path="$(cygpath -m "$temp_path")" || return 1
        database_path="$(cygpath -m "$database_path")" || return 1
    fi

    export APP_DATA_DIRECTORY="$app_data_path"
    export TEMP_DIRECTORY="$temp_path"
    export DATABASE_URL="sqlite+aiosqlite:///$database_path"
    export DISABLE_ANONYMOUS_TRACKING=true
    export DISABLE_IMAGE_GENERATION=true

    uv sync --locked --dev || return 1
    uv run --locked pip-audit --progress-spinner off || return 1
    uv run --locked python -m pytest --verbose --tb=short &&
        uv run --locked python -m compileall -q api models services utils &&
        uv run --locked python scripts/generate_openapi_spec.py --check &&
        uv run --locked python scripts/check_migrations.py &&
        mkdir -p "$SCRIPT_DIR/artifacts/sbom" &&
        uv run --locked cyclonedx-py environment \
            --pyproject pyproject.toml \
            --output-reproducible \
            --output-format JSON \
            --output-file "$SCRIPT_DIR/artifacts/sbom/python.cdx.json"
)

test_nextjs() {
    cd "$SCRIPT_DIR/servers/nextjs" &&
        npm ci &&
        npm audit --audit-level=high &&
        npm test &&
        npm run lint &&
        NEXT_PUBLIC_FAST_API=http://localhost:8000 \
            NEXT_PUBLIC_URL=http://localhost:3000 \
            npm run build &&
        npm run test:cypress
}

test_electron() {
    cd "$SCRIPT_DIR/electron" &&
        npm ci &&
        npm audit --audit-level=high &&
        npm test &&
        npm run lint:main
}

test_secret_scan() {
    cd "$SCRIPT_DIR" && python scripts/scan_secrets.py
}

for command in docker npm node python uv; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo -e "${RED}Required command not found: ${command}${NC}"
        exit 1
    fi
done

echo "Running the GitHub Actions checks locally from $SCRIPT_DIR"
echo

run_check "Repository tooling tests" test_repository_tools
run_check "FastAPI tests, compile, and Python SBOM" test_fastapi
run_check "Next.js tests, lint, build, and component tests" test_nextjs
run_check "Electron tests, build, and main-process validation" test_electron
run_check "Redacting repository secret scan" test_secret_scan

if [[ "$FAILED_CHECKS" -eq 0 ]]; then
    echo -e "${GREEN}All GitHub Actions checks passed.${NC}"
    exit 0
fi

echo -e "${RED}${FAILED_CHECKS} GitHub Actions check(s) failed.${NC}"
exit 1

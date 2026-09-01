# Bayanly repository operating contract

## Precedence and scope

- User and system instructions take precedence over this file. The nearest nested `AGENTS.md` adds directory-specific rules; it MUST NOT weaken this contract.
- This contract applies to the whole repository. Read [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), [CODESTYLE.md](CODESTYLE.md), and [TESTING.md](TESTING.md) before changing implementation code.
- [Sprint_exeuteive.md](Sprint_exeuteive.md) is roadmap context, not evidence that planned functionality exists. Verify current behavior in code, tests, migrations, and configuration.

## Read before write

- Before editing, agents MUST inspect the branch, `git status`, relevant diffs, `.gitignore`, nearby code, applicable nested instructions, manifests, and the tests and configuration that govern the target.
- Agents MUST distinguish current implementation, feature-flagged rollout foundations, legacy compatibility behavior, and roadmap-only work.
- Existing user changes MUST be preserved. Unrelated changes MUST NOT be reformatted, reverted, deleted, or folded into the task.

## Architecture and scope

- Existing module, persistence, job, storage, provider, renderer, and API boundaries MUST be extended rather than duplicated.
- FastAPI routes are transport adapters. New domain behavior SHOULD live in the owning `servers/fastapi/modules/*` application/domain boundary where one exists.
- New or migrated AI execution MUST use `modules/providers` application services and the canonical provider execution boundary. Legacy direct SDK paths are migration debt, not precedent.
- User- or configuration-influenced outbound URLs MUST use `utils/outbound_http.py` or an explicitly reviewed adapter with equivalent DNS pinning, redirect, address, timeout, and size protections.
- New durable work MUST use the canonical job/outbox boundary when enabled. Code MUST NOT create unbounded retries, nested retry systems, or a competing queue.
- Canonical presentation behavior MUST use the versioned presentation document, command, renderer, and revision boundaries. Renderer state, resolved URLs, and executable code MUST NOT become document truth.
- New managed file behavior MUST use asset IDs and `modules/assets`; a second object-store abstraction or new durable path convention MUST NOT be introduced.
- Feature flags and compatibility facades MUST retain safe defaults and rollback semantics unless a separately approved rollout changes them.
- Public APIs, schemas, persistence formats, or major subsystem names MUST NOT change incidentally. Scope expansion requires explicit approval.

## Security

- The backend is authoritative for authentication, authorization, ownership, workspace membership, RBAC, service-account scopes, and admin access. Hidden UI or route guards are never authorization.
- Every database read, write, export, asset access, job, and provider action MUST preserve the applicable owner/workspace predicate. Cross-tenant lookup failures SHOULD remain enumeration-resistant.
- Admin-only capabilities MUST NOT be exposed to normal users or non-browser principals without an explicit reviewed policy.
- Secrets, cookies, bearer credentials, provider responses, prompts, presentation content, signed URLs, and local paths MUST NOT be logged or placed in job payloads, analytics, or public errors.
- Existing outbound-request, safe-rendering, path-containment, IPC-sender, rate/concurrency, and security-header protections MUST NOT be weakened.
- Frontend-only security, permissive production auth bypasses, executable content, arbitrary redirects, and uncontrolled external fetches MUST NOT be introduced.
- Security gaps and assumptions MUST be documented rather than described as implemented protection.

## Changes, defects, and migrations

- A bug fix MUST begin with a reproducible failing case or concrete root-cause evidence, change the narrowest responsible boundary, and add or update regression validation.
- Database changes MUST use Alembic, keep one reviewable migration graph, preserve existing data, and be tested against the supported database path. `create_all` is not a substitute for a migration.
- Dependencies MUST be added only at the owning manifest, pinned/locked through the existing toolchain, and justified against an existing capability. Governance checks SHOULD use standard-library code where practical.
- Generated contracts and product metadata MUST be changed through their generators and verified with their `--check` commands.
- Documentation MUST be updated in the same change when architecture, security posture, commands, flags, or operator assumptions change.

## Validation and Git safety

- Run the mandatory checks in [TESTING.md](TESTING.md) for the affected scope before declaring completion. A skipped or environment-blocked check MUST be reported with the exact reason.
- Agents MUST review `git diff --check`, the final diff, and final `git status --short`.
- Maintained branches are `dev`, `staging`, and `production`. Agents MUST NOT invent or use a `main` branch or create sprint/feature branches unless the user explicitly changes repository policy.
- Agents MUST NOT reset, restore, stash, clean, rebase, merge, create/switch branches, commit, push, force-push, or tag unless the user explicitly requests that exact Git action.
- Agents MUST NOT invoke real paid providers, production secrets, or destructive production resources for validation.

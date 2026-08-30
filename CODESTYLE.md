# Bayanly code style

This document records the repository's current intentional conventions. It is not a mandate to reformat legacy code. Nearby code and the owning configuration remain authoritative when this document does not specify a detail.

## General rules

- Keep changes narrow. Do not mix behavioral work with formatting, import sorting, renaming, or cleanup of unrelated code.
- Prefer an existing module, helper, schema, error type, client, or test fixture over a parallel abstraction.
- Name code after the repository domain (`presentation`, `workspace`, `asset`, `provider`, `job`, `revision`) rather than implementation trivia.
- Comments explain invariants, security decisions, compatibility constraints, and non-obvious tradeoffs. Do not narrate syntax or leave roadmap claims in implementation comments.
- Treat generated files as outputs. Change their source and run the checked-in generator; do not hand-edit generated presentation or product identity bindings.
- There is no repository-wide formatter. Preserve the dominant style of the file and avoid broad formatting sweeps.

## Python and FastAPI

- Target Python 3.11 as declared by `.python-version` and `servers/fastapi/pyproject.toml`.
- Use four-space indentation, `snake_case` functions/variables/modules, `PascalCase` classes/models, and upper-case constants. Existing code predominantly uses double-quoted user-facing strings but formatting is not mechanically standardized.
- Add type annotations to public application/domain functions and to data crossing module boundaries. Use modern unions and built-in generics (`X | None`, `list[X]`, `dict[K, V]`) where the surrounding module does.
- Keep async call chains async. Use `AsyncSession`, async provider/storage clients, and `asyncio.to_thread` for established blocking SDK boundaries. Do not perform blocking network or disk work directly on the event loop.
- FastAPI handlers declare request/response schemas and dependencies explicitly. Validate untrusted values before calling application services, and return repository-standard response aliases where the API contract requires them.
- Pydantic models represent validated external/domain data. SQLModel classes represent persistence. ORM rows, request objects, and provider SDK responses must not leak into canonical domain contracts.
- Use `StableAPIError(status, code, message, params=...)` for new stable application errors in modules/routes that use the stable envelope. Do not expose exception text, SQL errors, provider payloads, paths, or credentials.
- Use module-level `logging.getLogger(__name__)`. Log bounded categories and safe identifiers; never use `print` for new runtime diagnostics. Existing startup/migration scripts that intentionally print operator status are exceptions.
- Transaction ownership belongs to the application operation. Flush when an ID is needed inside a transaction; commit only at the boundary that owns the complete state transition.
- Import from the canonical package path (`modules.*`, `services.*`, `utils.*`, `api.*`). Domain modules must not import FastAPI transports or provider endpoint modules.
- Pyright is explicitly set to `typeCheckingMode = "off"`, and no Ruff/Black/isort configuration exists. Type checking, formatting, and Python lint rules are therefore advisory until tooling is adopted; `compileall`, pytest, and review are the current mechanical controls.

## TypeScript, React, and Next.js

- Next.js uses TypeScript strict mode, the App Router, React 19, and the `@/*` path alias. New code must type public props, API payloads, state, and helper returns.
- ESLint uses Next core-web-vitals and TypeScript presets. Several legacy rules, including explicit `any`, are intentionally disabled; this is compatibility, not a recommendation for new boundaries.
- Use `PascalCase` for components and component files, `camelCase` for functions/values, `use*` for hooks, and `UPPER_SNAKE_CASE` for fixed constants. Preserve route filenames required by Next.js.
- Prefer named domain types and discriminated unions to casts. Narrow `unknown` responses/errors before use. Keep unsafe casts at a validated adapter boundary.
- Server Components are the default. Add `"use client"` only when hooks, browser APIs, event handlers, or client state require it.
- Route/layout files compose. Put reusable product behavior in `features/`, shared primitives in `components/ui`, cross-feature policy in `lib`/`utils`, and renderer-specific behavior in `renderers/*`.
- Use the existing `getApiUrl`, timeout, stable-error, runtime-capability, and feature API helpers. Requests that rely on the session cookie include `credentials: "include"`.
- User-facing application text uses `t("catalog.key")`; English and Arabic catalogs keep identical keys and interpolation variables. Do not build translated sentences by concatenation.
- Use CSS logical properties (`start`/`end`, inline/block) for application chrome and the existing RTL stylesheet/guidelines. Presentation geometry remains physical and must not be mirrored with the UI.
- Use centralized safe Markdown rendering for HTML sinks. Ordinary React content stays as text nodes; never add `dangerouslySetInnerHTML` without an existing audited policy and regression test.
- The dominant code uses semicolons and double quotes, but legacy areas vary and no Prettier configuration exists. Match the edited file and let ESLint determine enforceable style.

## Electron TypeScript

- Electron's TypeScript project is strict and compiles `electron/app` into `app_dist`. Keep main-process code in `app`, preload exposure narrow, and renderer/product behavior in the web application.
- IPC channel names are stable contracts. Handlers validate `unknown` inputs with explicit assertions before side effects and return bounded safe results.
- Use existing lifecycle, memory, path, process, safe-console, Sentry, and IPC-security helpers. Spawn processes with an executable plus argument array, never a shell-built command.
- Filesystem operations use resolved platform directories and containment checks. Temporary output is cleaned in `finally` or an established lifecycle handler.

## Tests and fixtures

- Python tests use pytest with plain test functions, fixtures, `tmp_path`, and `monkeypatch`; async scenarios are commonly contained and run deterministically. External systems use disposable explicit endpoints or skip.
- Next.js and Electron unit/security tests use Node's built-in test runner. Cypress owns browser component and locale/product journeys.
- Test names state the observable invariant. A regression test should fail for the original cause, not just execute the changed line.
- Tests must not require real provider credentials, paid APIs, production databases, or production object storage. Use controlled local servers, fake adapters, temporary SQLite, or explicitly disposable integration services.

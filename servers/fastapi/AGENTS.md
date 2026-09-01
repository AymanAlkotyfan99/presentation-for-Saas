# FastAPI scope instructions

This file inherits the root `AGENTS.md` and applies to `servers/fastapi/**`.

- Keep `api/` handlers and middleware as transport/policy adapters. Put reusable business behavior in the owning `modules/*` application/domain layer or the established service when no module boundary exists.
- API changes MUST preserve authentication middleware, admin restrictions, owner/workspace context, stable error semantics, response models, and the checked-in OpenAPI contract.
- Pydantic/API schemas are trust boundaries. Validate untrusted size, shape, identity, URL, and state before persistence or external execution.
- SQL access MUST use the shared async session factories and applicable owner/workspace predicates. Related state transitions MUST commit atomically; partial commits require explicit recovery semantics.
- Schema changes MUST be expressed as a linear Alembic migration with upgrade/downgrade behavior and migration tests. Do not rely on startup `create_all` for evolution.
- Provider work MUST go through `modules/providers` application services; durable work through `modules/jobs`; managed bytes through `modules/assets`; user-controlled outbound HTTP through `utils/outbound_http.py`.
- Job handlers MUST be idempotent under at-least-once delivery, revalidate current authority/revision, keep payloads secret-free and bounded, and use finite classified retries.
- Use `StableAPIError` for new public application errors where the surrounding API supports it. Log safe identifiers and categories, never content or credentials.
- Preserve Python 3.11 compatibility and async I/O. Do not add blocking network or storage work to the event loop.
- Run focused pytest first, then the FastAPI checks in root `TESTING.md`; update `openai_spec.json` only through `scripts/generate_openapi_spec.py` when an intentional API change is approved.

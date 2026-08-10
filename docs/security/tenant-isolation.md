# Tenant isolation

The authoritative tenant key is the server-validated workspace context, not a client header, cookie, URL, or serialized job claim. Explicit unknown workspace selection returns a non-enumerating not-found response. Resource/workspace mismatch also returns not found where existence would disclose another tenant.

Presentation, canonical document, revision, revision patch, slide, image asset, owned template, async job, chat message, access-token metadata, webhook, layout-code, and template-create-info reads are scoped by the central database listener. Default Template V2 rows are the only explicitly shared commercial-like records. Bulk mutations add the central workspace predicate. Revision rows inherit the locked presentation workspace, restores create a new workspace-bound revision, and workers re-resolve job/resource revision bindings.

Private filesystem paths created under RBAC use a validated workspace namespace. A request cannot select a different workspace merely by changing `X-Workspace-ID`; browser users require active membership and service credentials are fixed to one workspace. Legacy user paths remain owner-only during migration, preventing a team membership from exposing unrelated personal files.

Security logging may include workspace, actor, role, permission name, denial category, invitation state, and credential operation category. It must never contain presentation content, prompts, private paths, raw invite tokens, credential secrets, or token digests.

The focused isolation matrix covers presentations, canonical revision writes, image assets, owned templates, and jobs in separate workspaces, plus credential workspace binding. PostgreSQL route/concurrency coverage is required before paid beta; if Docker/PostgreSQL is unavailable locally, the limitation must be explicit rather than inferred from SQLite.

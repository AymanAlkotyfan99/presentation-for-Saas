# Runtime layout source policy

The former `POST /api/save-layout` route has been removed. It accepted
user-controlled layout/component names and wrote generated `.tsx` files at
runtime. Removing it is an intentional breaking security change: neither an
administrator nor a normal user can create executable TypeScript, JavaScript,
JSX, or TSX through the running application.

Bundled templates and the declarative `layouts.json` catalog remain available;
they are application build inputs and are not modified by requests. The server
may continue writing non-executable configuration, export-task, upload, and
asset data to their dedicated data directories subject to their own validation
and authorization policies.

If runtime custom-layout authoring returns in a later sprint, it must store a
versioned declarative JSON schema in an isolated data/object-storage namespace.
The application must validate the schema and render it through an allowlisted
component system. User input must not select filesystem paths, modify source
directories, or be transpiled/executed in the primary application origin.

The legacy database-backed executable custom-layout compiler is disabled by
default as well. Server compilation requires
`ENABLE_UNSAFE_CUSTOM_LAYOUTS=true`; browser compilation separately requires
`NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS=true` at build time and relaxes the
CSP with `unsafe-eval`. Those opt-ins are for isolated, trusted development
only and must remain false in production. Disabled endpoints return the stable
code `UNSAFE_CUSTOM_LAYOUTS_DISABLED`.

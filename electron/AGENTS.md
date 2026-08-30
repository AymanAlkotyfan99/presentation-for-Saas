# Electron scope instructions

This file inherits the root `AGENTS.md` and applies to `electron/**`.

- Electron is an outer adapter around the Next.js/FastAPI applications. Product/domain behavior MUST NOT be reimplemented in the main process.
- Keep context isolation, renderer sandboxing, trusted-origin navigation, window-open policy, IPC sender validation, and narrow preload exposure intact.
- Every IPC handler MUST validate sender, argument types, sizes, identifiers, paths, and allowed operations before filesystem, process, shell, or network effects.
- Child processes MUST use explicit argument arrays, bounded output/time/lifecycle handling, controlled environments, and cleanup. Do not interpolate untrusted values into shell commands.
- Paths MUST be resolved through existing app-data/cache/temp/download/resource helpers and checked for containment before reads, writes, moves, or deletion.
- Logs, Sentry breadcrumbs, dialogs, and returned errors MUST use the safe console/error helpers and MUST NOT include credentials, cookies, document content, or raw child-process output.
- Export remains a separately versioned, integrity-pinned boundary and is disabled unless its explicit verification flag is enabled. Do not silently replace or inline it.
- Preserve strict TypeScript and the packaged/runtime resource distinction. Run Electron tests and `npm run lint:main` from root `TESTING.md`.

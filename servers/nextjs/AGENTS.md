# Next.js scope instructions

This file inherits the root `AGENTS.md` and applies to `servers/nextjs/**`.

- Preserve the Next.js App Router composition boundary: route/layout files compose screens, `features/` owns product behavior, and shared UI MUST NOT import route or feature code.
- Server layouts and `AuthGate` improve navigation only. All authorization, admin, owner, workspace, and RBAC decisions MUST remain enforced by FastAPI.
- Browser code MUST NOT import Electron main-process code or the separately versioned presentation-export runtime.
- Use existing API URL, timeout, error, workspace, and capability helpers. Authenticated requests MUST preserve credentials and must not invent a second client/session store.
- All user-facing shell copy MUST use the English/Arabic catalogs. Keep locale-prefixed routing, account locale persistence, `lang`/`dir`, logical CSS properties, and Arabic RTL behavior intact.
- Presentation content direction is canonical document state; Arabic application chrome MUST NOT mirror slide geometry, element order, or canvas coordinates.
- Raw HTML MUST NOT be introduced. Markdown sinks MUST use `lib/safe-markdown.ts`; canonical renderers MUST remain declarative and may not invoke the legacy executable-layout compiler.
- Use Server Components by default and add `"use client"` only for browser state, effects, or interaction. Keep strict TypeScript types at boundaries even though selected legacy lint exceptions remain enabled.
- Components use PascalCase, hooks use `use*`, and route-independent behavior belongs in a feature/lib/helper rather than a page god component.
- New screens MUST handle loading, empty, failure, disabled-capability, keyboard, and narrow viewport states in both LTR and RTL.
- Run focused Node tests, `check:i18n`, ESLint, and a production build as required by root `TESTING.md`; run locale/Cypress coverage for routing, renderer, workspace, or interaction changes.

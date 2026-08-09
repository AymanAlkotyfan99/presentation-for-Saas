# Bayanly localization translator guide

Status: the English catalog is the source copy. The Arabic catalog is
`TECHNICALLY_TRANSLATED` and remains `HUMAN_REVIEW_REQUIRED`. Authentication,
privacy, destructive-action, and security-warning namespaces additionally have
`SECURITY_COPY_REVIEW_REQUIRED` status. No Arabic wording is represented as
human-approved in Sprint 3.

## Catalog workflow

Catalogs live in `servers/nextjs/messages/en.json` and `ar.json`. Keys use
stable `namespace.camelCaseKey` identifiers. Add the English and Arabic value
in the same change, run `npm run localization:check`, and use `useTranslations`
inside client components. Product name, short name, support email, URLs, and
assets are identity tokens supplied by the Sprint 2 product registry; do not
copy those values into a catalog.

Catalog text is plain text. Do not add HTML, Markdown-as-HTML, `javascript:`
URLs, provider output, user input, or dynamically constructed keys. Variables
use controlled names such as `{count}`. React renders interpolated values as
text; never pass catalog output to `dangerouslySetInnerHTML`. Add controlled
singular/plural keys when grammar differs.

## Adding a locale

1. Add a constrained BCP-47 primary tag to `i18n/config.ts`.
2. Create a complete catalog with identical keys and placeholders.
3. Define direction and formatting behavior explicitly.
4. Add routing, bidi, font, accessibility, and E2E fixtures.
5. Obtain human review for product terminology and security/destructive copy.

Machine translation may seed a technical draft, but it is not approval.
Financial copy remains `FINANCE_COPY_REVIEW_REQUIRED` until the later payment
work exists. A future `workspace.default_locale` may participate after Sprint
7; Sprint 3 stores only the explicit user preference and cookie mirror.

## Verification

- `npm run localization:check`
- `cd servers/nextjs && npm test`
- `cd servers/nextjs && npm run test:locale-e2e`
- `cd servers/nextjs && npx tsc --noEmit && npm run lint`

Presentation content locale is a separate document property. Changing the UI
locale must never rewrite the language or direction of a presentation.


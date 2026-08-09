# RTL and bidirectional UI guidelines

Arabic application routes render `<html lang="ar" dir="rtl">`; English renders
`lang="en" dir="ltr"`. Route rewriting preserves the existing App Router tree,
query parameters, presentation IDs, and deep links. API, Next internals, static
assets, export-internal routes, and non-GET/HEAD requests bypass localization.

Use logical CSS (`margin-inline`, `padding-inline`, `inset-inline`, `text-align:
start/end`, or Tailwind `ms/me/ps/pe/start/end`) for application-shell meaning.
Keep physical `left/right`, X coordinates, crop coordinates, chart axes, slide
geometry, and fixed canvas calculations physical. Do not mirror logos, photos,
charts, canvases, or presentation slides solely because the shell is Arabic.

Use `dir="auto"` for short user-authored labels and `<bdi>` for usernames,
titles, filenames, and other embedded user content. URLs, email addresses,
hashes, API keys, code, paths, and identifiers use `.ltr-isolate`. Avoid bidi
control characters in catalogs. Test Arabic, English, Arabic with English and
numbers, URLs, email, filenames, parentheses, and punctuation.

Sprint 3 covers the application shell. Canonical slide direction begins in
Sprint 4; full canvas/editor and export RTL behavior remains Sprints 5 and 16.


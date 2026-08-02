# License and asset provenance register

Last reviewed: 2026-08-02

This register is evidence-based. It records what is present in the repository,
what source/version information can be proven from tracked files, and what remains
unknown. It does **not** grant permission, give legal advice, or claim approval.

No static-asset or downloaded-runtime category below has a recorded final legal
approval in this repository. Where a likely upstream family can be identified,
that is only a lead for review. Do not infer that a license used by a current
upstream project applies to these exact bytes.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `VERIFIED` | Exact source/version/license evidence, obligations, and commercial/distribution approval are recorded for the reviewed scope. No current row qualifies. |
| `REQUIRES_ATTRIBUTION` | Use or redistribution is supportable only when the recorded attribution/notice requirements are fulfilled. No asset row may receive this state without exact evidence. |
| `REQUIRES_LEGAL_REVIEW` | Source or license evidence exists, but commercial use, redistribution, notice, trademark, data/model, or other obligations still need an authorized decision. |
| `UNKNOWN` | The tracked evidence is insufficient to determine one or more material rights or obligations. |
| `DO_NOT_DISTRIBUTE` | Exclude the item from public artifacts until its blocking provenance/license decision is resolved. |
| `DECLARED_NOT_FINAL` | A tracked manifest declares a source/license, but final package/obligation review is not recorded. |
| `IDENTIFIED_UNREVIEWED` | The family/provider/source can be identified, but exact version, license evidence, obligations, or approval is incomplete. |
| `UNKNOWN_BLOCKED` | The tracked repository does not establish source/ownership/permission. Exclude from a public distributable until resolved. |
| `EXTERNAL_TERMS` | Content is fetched or supplied at runtime and is governed by provider/user terms not captured by the repository license. |
| `DISABLED_PENDING_REVIEW` | Bytes/source may be known, but a feature is deliberately disabled until trust/legal gates close. |
| `INVENTORY_GAP` | Existing SBOM/NOTICE tooling does not cover the item. |

Only an authorized reviewer can change a row to an approved organizational
state, and that decision must link exact bytes/version, license text, source,
obligations, approver, date, and scope/platform.

## Required asset/package decision matrix

This matrix supplies the common review fields for every in-scope asset group.
Narrative sections below give the supporting detail. `VERIFIED` is intentionally
not used: no row has complete commercial/distribution approval evidence in the
tracked repository.

| Asset or package | Source | Version or commit | License | Commercial-use status | Redistribution status | Attribution requirement | Modification status | Evidence or license file | Review status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Presenton-authored application source | Tracked repository contributions | Public app `0.9.3-beta`; exact release commit must be recorded at release | Apache-2.0 declared | License declares permission; contribution provenance review remains | Apache conditions apply; final shipped-byte review remains | LICENSE/NOTICE preservation | Modified throughout repository history | `LICENSE`, `servers/fastapi/LICENSE`, root/backend NOTICE | `REQUIRES_LEGAL_REVIEW` |
| Seven bundled template JSON/design groups | Original design/source presentations not recorded | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Converted/derived structure is visible; source and tool chain unknown | `templates/*/template.json`, no sidecars | `DO_NOT_DISTRIBUTE` |
| Template raster/vector media and thumbnails | Unknown | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Some SVGs appear exported/converted; exact changes unknown | 37 PNG, 3 JPEG, 47 SVG under `templates/` | `DO_NOT_DISTRIBUTE` |
| Bundled template fonts | Family names only; original download source absent | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Possible embedding/copying; no transformation record | 12 TTF files under `templates/`, no license files | `DO_NOT_DISTRIBUTE` |
| Inter and Electron Syne/Unbounded application fonts | Original download source absent | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Bundled as TTF; Next.js maps branded aliases to its local Inter file during Phase 0 | `servers/nextjs/app/fonts/`, `electron/resources/ui/assets/fonts/` | `DO_NOT_DISTRIBUTE` |
| Google Fonts loaded by templates/editor/backend | Live Google Fonts CSS/service; family names in code | Service-selected bytes; no pinned font revision | Exact per-family license not retained | `REQUIRES_LEGAL_REVIEW` | Embedding/export rights unknown | Exact per-family requirements unknown | Runtime loading and possible document embedding/subsetting | Template JSON and font/chat utilities | `REQUIRES_LEGAL_REVIEW` |
| Phosphor-labeled icon corpus and derived vectorstore | Family identified by `icons.json`; upstream URL absent | Unknown version/commit | Exact license text absent | `UNKNOWN` | `DO_NOT_DISTRIBUTE` pending exact evidence | Unknown; brand glyphs need separate trademark review | Renaming/weight organization/index derivation visible; acquisition transform unknown | `servers/fastapi/static/icons/`, `assets/icons*.json` | `REQUIRES_LEGAL_REVIEW` |
| Next.js UI images and illustrations | Mostly unknown; the identified Freepik-shaped 404 illustration was removed in Phase 0 | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown; third-party logos also need brand review | Unknown | `servers/nextjs/public/`; no sidecars | `DO_NOT_DISTRIBUTE` |
| README screenshots, GIFs, banners, template previews, video | Unknown/product creation records absent | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Screenshots/edits/compositing unknown | `readme_assets/`; no sidecars | `DO_NOT_DISTRIBUTE` |
| Backend placeholder images | Unknown | Unknown | Unknown | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Unknown | `servers/fastapi/static/images/` | `DO_NOT_DISTRIBUTE` |
| Example presentations/layouts and inline sample media | No tracked PPTX/PDF; template/inline examples have unknown inputs; an Unsplash URL remains in a prompt example | Unknown; one remote photo ID is identifiable | Provider/source terms not retained | `UNKNOWN` | `DO_NOT_DISTRIBUTE` as bundled defaults | Photographer/source attribution unknown | Inline HTML/layout conversion and remote linking | Templates, `prompts.py`, README previews | `DO_NOT_DISTRIBUTE` |
| Pexels and Pixabay stock integrations | Provider APIs at runtime | Live API/content terms | External provider terms, not committed | `REQUIRES_LEGAL_REVIEW` | Output/cache/export rights unknown | Creator/provider attribution currently not retained | URLs may be selected, downloaded, cropped, edited, and exported | `image_generation_service.py`, images API/UI | `REQUIRES_LEGAL_REVIEW` |
| Electron framework and bundled Chromium/Node | npm/GitHub Electron distribution | Electron `42.2.0`; internal component versions require final package inventory | Electron package declares MIT; bundled components are multi-license | `REQUIRES_LEGAL_REVIEW` | Notices/source/codec/store obligations require platform review | Required Electron/Chromium third-party notices | Packaged with Presenton and platform installer/signing | `electron/package.json`, lockfile, generated NOTICE inputs | `REQUIRES_LEGAL_REVIEW` |
| Server Chromium | Debian security snapshot | `149.0.7827.196-1~deb13u1`, snapshot `20260625T180000Z` | Multi-license Chromium/Debian package; final copyright inventory absent | `REQUIRES_LEGAL_REVIEW` | Source/notice obligations require review | Required Debian/Chromium notices | Installed/held/configured in container | `Dockerfile`; not covered by current package SBOM | `REQUIRES_LEGAL_REVIEW` |
| Separate Electron export Chromium | Archive resolved by Electron build tooling; exact platform URLs/hashes incomplete | Chrome `149.0.7827.196`; mac IDs `1625085`/`1625072` | Multi-license; evidence not assembled | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown until third-party notices are assembled | Downloaded/extracted and bundled when override is used | Electron package/config and `prepare-export-chromium.cjs` | `DO_NOT_DISTRIBUTE` |
| Presentation export runtime | `presenton/presenton-export` GitHub release | `v0.4.2`, five platform hashes recorded | `UNKNOWN` in integrity policy | `UNKNOWN` | `DO_NOT_DISTRIBUTE` | Unknown | Archives extracted; converters/runtime bundled | Integrity policy, sync scripts, generated external-artifact BOM | `DO_NOT_DISTRIBUTE` / disabled |
| ImageMagick portable/AppImage runtime | ImageMagick GitHub release | `7.1.2-18`, five hashes recorded | Exact reviewed license/notice bundle not recorded | `REQUIRES_LEGAL_REVIEW` | Delegate/library obligations unknown | Unknown pending exact package inspection | Downloaded/extracted/bundled for Electron | Integrity policy, prepare script, generated external-artifact BOM | `REQUIRES_LEGAL_REVIEW` |
| spaCy English model | explosion/spacy-models GitHub release | `en_core_web_sm 3.8.0`, SHA-256 recorded | Policy explicitly requires legal review | `REQUIRES_LEGAL_REVIEW` | Model/data redistribution decision absent | Unknown | Wheel installed into server image | Integrity policy, Dockerfiles, generated external-artifact BOM | `REQUIRES_LEGAL_REVIEW` |
| Sharp and bundled/prebuilt libvips/native add-ons | npm registry lockfiles and platform optional packages | Sharp `0.35.3`; exact libvips/native builds are platform-dependent | Sharp manifest says Apache-2.0; libvips/delegates need separate exact review | `REQUIRES_LEGAL_REVIEW` | Native library notices/source obligations require review | Exact native package notices required | Native binaries bundled into container/desktop | Three lockfiles, SBOMs, NOTICE inputs | `REQUIRES_LEGAL_REVIEW` |
| LiteParse and shared runner | npm `@llamaindex/liteparse`; runner tracked locally | LiteParse `2.10.1`; runner release origin not separately recorded | Package manifest says Apache-2.0; runner/final contents still need provenance review | `REQUIRES_LEGAL_REVIEW` | Final native/runtime contents require review | Package notices required | Integrated through local runner and bundled Node runtime | Root/Electron lockfiles, runner source | `REQUIRES_LEGAL_REVIEW` |
| FastEmbed/Hugging Face model/cache | No default acquisition; optional upstream model ecosystem | Exact model revision/files absent | Unknown model/data terms | `UNKNOWN` | `DO_NOT_DISTRIBUTE` until inventoried | Unknown | Build warm-up and cache shipping were removed; semantic execution requires two explicit risk flags | `icon_finder_service.py`, Docker/Compose flags | `DO_NOT_DISTRIBUTE` |
| Tesseract/OCR data, Noto fonts, Nginx, zstd, OS/native libraries | Debian packages/base image | Build-resolved versions; only Chromium is explicitly pinned by package version | Multiple licenses; final OS inventory absent | `REQUIRES_LEGAL_REVIEW` | Per-package obligations unknown | Per-package notices/source offers may apply | Installed/configured in container | Dockerfiles; OCI SBOM missing | `REQUIRES_LEGAL_REVIEW` |
| Preview Tailwind and Chart.js code | Tailwind is compiled from the lockfile; Chart.js is copied from locked npm `4.5.1` into local static assets | npm lockfile revisions | Package manifests/notices identify licenses; final redistribution review remains | `REQUIRES_LEGAL_REVIEW` | Locally redistributed as application assets | Preserve applicable package notices | Remote executable CDN injection removed in Phase 0 | `prepare-vendor-assets.mjs`, local `/vendor` paths, npm lockfile | `REQUIRES_LEGAL_REVIEW` |
| Copied, adapted, generated, and derived source not covered above | No comprehensive origin register | Unknown per file | Unknown per file | `UNKNOWN` | `DO_NOT_DISTRIBUTE` until classified | Unknown | Unknown or generator-specific | `openai_spec.json`, runner, conversion outputs, inline examples | `REQUIRES_LEGAL_REVIEW` |

## Repository-level code license

Root `LICENSE` declares Apache License 2.0 and names Presenton in the appendix.
`servers/fastapi/LICENSE` is also present. Root `NOTICE` and
`servers/fastapi/NOTICE` contain generated package notices.

Status: `DECLARED_NOT_FINAL`.

The declaration covers Presenton contributions only to the extent their authors
had the right to license them. It does not automatically cover separable fonts,
photos, illustrations, icons, models, copied source, provider trademarks,
downloaded binaries, or dependencies. The repository contains no contributor
provenance/DCO/CLA audit evidence as part of this Phase 0 snapshot.

## Built-in presentation templates

Tracked inventory under `templates/`:

- seven JSON template bundles: `dynamic`, `executive`, `general`, `modern`,
  `momentum`, `standard`, and `swift`;
- 37 PNG files, including thumbnails and embedded template images;
- three JPEG files;
- 47 SVG freeform/design files; and
- 12 TTF font files.

No template directory contains a LICENSE, NOTICE, source URL, author statement,
asset manifest, consent record, purchase record, or attribution sidecar. File
names and the converted/freeform structure suggest some assets may have been
derived from presentation source files, but the source presentations and rights
chain are not recorded.

Several template JSON files reference Google Fonts stylesheets:

- `general`: Poppins;
- `dynamic` and `modern`: Montserrat;
- `standard`: Playfair Display; and
- `swift`: Albert Sans.

Those URLs establish a service/family name, not the license/version of font bytes
loaded at a later date.

Status: `UNKNOWN_BLOCKED` for public distribution of the template designs and
their embedded raster/vector media. Google Font references are
`IDENTIFIED_UNREVIEWED` plus `EXTERNAL_TERMS`.

Required evidence per template:

1. designer/owner and original source file;
2. creation or acquisition date and rights grant covering commercial
   redistribution, modification, and presentation output;
3. per-asset source URL/order/license/version/hash;
4. required attribution and trademark/personality/model releases;
5. font embedding/subsetting and document-export permission; and
6. exact reviewed hashes for the JSON and every static file.

## Fonts

### Bundled template fonts

| Family/files | Tracked locations | Status |
| --- | --- | --- |
| Montserrat Medium/SemiBold | `templates/dynamic/static/` | `UNKNOWN_BLOCKED` |
| Anton Regular, DM Sans Bold, Montserrat Bold/Medium/Regular/SemiBold | `templates/executive/static/` | `UNKNOWN_BLOCKED` |
| Anton Regular, Lato Black/Bold/Regular | `templates/momentum/static/` | `UNKNOWN_BLOCKED` |

The repository has no adjacent font license text, exact upstream release, or
byte-level provenance. Family names are insufficient to conclude these files are
the Google Fonts versions or that a particular license applies.

### Application and Electron UI fonts

| Family/files | Tracked locations | Status |
| --- | --- | --- |
| Inter | `servers/nextjs/app/fonts/Inter.ttf` | `UNKNOWN_BLOCKED` |
| Syne Regular/Medium | `electron/resources/ui/assets/fonts/` | `UNKNOWN_BLOCKED` |
| Unbounded Medium/SemiBold | `electron/resources/ui/assets/fonts/` | `UNKNOWN_BLOCKED` |

### Runtime fonts

The server image installs Debian Noto, Liberation, and Noto Emoji/CJK/UI font
packages, then removes non-Noto font files. Next.js dependencies may also ship
fonts such as KaTeX fonts. Backend/editor code can load Google Fonts families,
including Playfair Display, Overpass, Prompt, Inter, Instrument Sans, Montserrat,
DM Sans, and arbitrary families inferred from uploaded presentations.

Status: Debian/package-managed and transitive fonts are
`IDENTIFIED_UNREVIEWED`; remotely loaded fonts are `EXTERNAL_TERMS`; both need
final-distributable inventory and license/notice verification.

Font review must cover embedding in PPTX/PDF, editable redistribution to users,
web serving, modification/subsetting, app-store distribution, and any required
copyright/license fields. `pptx_font_utils.py` can read font metadata when
available, but metadata absence or a blank license field is not permission.

## Icon corpus and logos

`servers/fastapi/static/icons/` contains 9,073 tracked SVG files, including the
placeholder. The corpus is organized into regular, thin, light, bold, fill, and
duotone weights. `servers/fastapi/assets/icons.json` explicitly labels set 1 as
"Phosphor Icons," and filenames/content match that catalog family.

No tracked file records the exact Phosphor version/commit, acquisition URL,
archive hash, transformation process, or applicable license text for these exact
SVGs. The corpus also includes brand/logo glyphs (for example Amazon, Discord,
and Phosphor names), for which trademark rules are separate from copyright
license terms.

Status: `IDENTIFIED_UNREVIEWED`; public redistribution remains blocked until the
exact upstream version and license/notice obligations are proven and brand-logo
use is reviewed.

`servers/fastapi/assets/icons-vectorstore.json` is a derived search index over
the icon catalog. Approval of the SVG input and the vector/model-generation
process is required before the derived index can be approved.

## UI, documentation, and marketing media

### Next.js public assets

`servers/nextjs/public/` contains 27 PNG, 33 SVG, one GIF, and one JPEG. This set
includes product logos, onboarding/report imagery, backgrounds, empty-state
graphics, provider logos, and social/service logos.

The previously identified `servers/nextjs/public/404.svg` contained Freepik-shaped
identifiers without acquisition evidence. Phase 0 removed it and replaced the 404
illustration with code-native UI; it is no longer part of the distributable.

Provider assets under `public/providers/` and dashboard social icons represent
OpenAI, Anthropic/Claude, Google/Gemini, ComfyUI, Ollama, Pexels, Pixabay,
SearXNG, Tavily, Exa, Brave, Discord, GitHub, and other third-party marks. A logo
file's availability does not grant trademark endorsement rights.

Status: `UNKNOWN_BLOCKED`, with the provider/social subset also requiring
trademark/brand-guideline review.

### README and repository media

`readme_assets/` contains 12 PNG files, two GIFs, and one MP4, including product
banners, feature screenshots, template previews, and a product video. There is no
asset manifest identifying creator, depicted user/private data, source, embedded
third-party media, model/property releases, or redistribution terms.

Status: `UNKNOWN_BLOCKED` for use outside an internal development context.

### Backend placeholder images

`servers/fastapi/static/images/` contains `placeholder.jpg` and
`replaceable_template_image.png`. No provenance sidecars are present.

Status: `UNKNOWN_BLOCKED`.

### Electron branding/media

Electron resources include application/product PNGs and UI styling in addition
to the four font files listed above. No separate branding ownership or trademark
approval record is committed.

Status: `UNKNOWN_BLOCKED` until tied to product-owned source/design records.

## Examples, prompts, and fixtures

The repository has text/JSON fixtures under `servers/nextjs/cypress/fixtures/`,
test fixtures throughout the backend, inline sample layout HTML in
`servers/fastapi/api/v1/ppt/endpoints/prompts.py`, and product examples in source
and documentation. Ordinary synthetic test text appears project-specific, but no
formal copied-source register exists.

Two concrete remote media examples in `prompts.py` require attention:

- a hardcoded Pexels image URL for photo ID `31527637`; and
- a hardcoded Unsplash URL for photo ID `1552664730-d307ca884978`.

These URLs can be emitted into generated content. The repository does not record
the photographers, source pages, retrieval dates, provider license/terms at that
date, attribution requirements, or downstream output rights.

Status: synthetic code/text fixtures are `DECLARED_NOT_FINAL`; hardcoded remote
media is `EXTERNAL_TERMS` and `UNKNOWN_BLOCKED` for bundled/default examples.
Replace it with owned test media or add a rights/attribution record and tests that
preserve required metadata.

## Stock and generated images

Presenton can query Pexels and Pixabay, and it can receive images from AI/provider
services. The Pexels/Pixabay implementation currently returns only image URLs;
it does not retain creator, source-page, provider item ID, license/terms snapshot,
or attribution metadata alongside the selected image.

Status: `EXTERNAL_TERMS` and unresolved for a paid/public offering.

Before enabling stock content in such an offering:

1. authorized counsel/product owners must review current provider API and content
   terms for SaaS use, caching, modification, redistribution, and exported decks;
2. the application must retain the provider item ID, creator, source page,
   retrieval time, terms/license reference, and required attribution;
3. the UI/export must present attribution where required;
4. deletion/DMCA/takedown and provider-term changes need an operational process;
5. users must receive clear responsibility/rights guidance; and
6. tests must prove metadata survives search, selection, persistence, duplication,
   and every export format.

AI-generated and user-uploaded content is not automatically covered by the
Presenton Apache license. Provider/customer terms, privacy, copyright, publicity,
trademark, and retention obligations remain external. Do not label output
"royalty free" or "commercially safe" without a separately reviewed basis.

## Preview scripts and remote font styles

Phase 0 removed the Tailwind and jsDelivr executable CDN injections. Tailwind is
compiled from the locked dependency graph, while exact Chart.js `4.5.1` bytes are
copied from `node_modules` into local Next.js/FastAPI vendor paths during locked
installation. The package license still requires final notice/distribution review.

Template and font utilities can still load Google Fonts CSS/bytes from live service
URLs. Those are external content/terms rather than remotely executed application
scripts, but exact font licenses, embedding rights, attribution, and byte revisions
remain unresolved. Status: `EXTERNAL_TERMS` / `REQUIRES_LEGAL_REVIEW`.

## Electron and Chromium

### Electron framework

`electron/package.json` pins Electron `42.2.0`; the npm lockfile pins its package
graph. The Electron npm package declares MIT in its own package metadata and
publishes platform checksums. Electron distributions also contain Chromium,
Node.js, codecs, and many third-party notices that are not represented by a
single MIT declaration.

Status: Electron package identity is `DECLARED_NOT_FINAL`. Each downloaded
platform archive and final installer must be checksum-verified, scanned, and
inspected to ensure Electron/Chromium third-party license notices are shipped.
App-store, codec, patent, auto-update, signing, and trademark obligations require
platform-specific review.

### Server Chromium

The server image pins Debian Chromium package
`149.0.7827.196-1~deb13u1` from snapshot `20260625T180000Z`. Base images are
digest-pinned, but the repository's package-manager SBOM command does not inventory
Debian packages or preserve their full copyright files as release evidence.

Status: `IDENTIFIED_UNREVIEWED` and `INVENTORY_GAP`.

### Separate Electron export Chromium

`electron/package.json` records Chrome build `149.0.7827.196` and macOS build IDs
`1625085`/`1625072`. `config/artifact-integrity.json` says platform archive
SHA-256 values are still required. Acquisition is gated by an explicit unverified
override.

Status: `DISABLED_PENDING_REVIEW`. Do not use the override in a distributable
build. Add every platform archive source/hash, Chromium notices/source-offer
obligations, and installed binary hash before approval.

## Presentation export runtime

The export runtime is `presenton/presenton-export v0.4.2`. SHA-256 values are
recorded for Linux ARM64/x64, macOS ARM64/x64, and Windows x64 archives in
`config/artifact-integrity.json`. The same policy explicitly records:

```text
trustStatus: REQUIRES_LEGAL_REVIEW
licenseStatus: UNKNOWN
enabledByDefaultInProduction: false
```

Status: `DISABLED_PENDING_REVIEW`.

The hashes establish the reviewed archive identity only. Before enabling export,
obtain the export repository's exact license/NOTICE/source provenance, inventory
every bundled binary/library/font, reconcile extracted files to an SBOM, review
commercial redistribution and output-format obligations, and test all platform
packages. If unapproved runtime bytes remain in a distributable even while the
feature is disabled, the release review must explicitly address their presence.

## ImageMagick, models, OCR, and other native components

| Component | Evidence in repository | Status and missing evidence |
| --- | --- | --- |
| ImageMagick (Electron) | Version `7.1.2-18`, source tag, and five portable/AppImage hashes in `config/artifact-integrity.json`. | `IDENTIFIED_UNREVIEWED`; policy itself says legal review required. Inspect delegate libraries/config and include license/notice in every package. |
| ImageMagick (server) | Installed from Debian during Docker build. | `INVENTORY_GAP`; exact installed package/delegates and copyright files need final-image evidence. |
| spaCy `en_core_web_sm` | Version `3.8.0`, GitHub release source, and SHA-256 pinned in Docker/policy. | `IDENTIFIED_UNREVIEWED`; policy says legal review required. Model/data terms must be reviewed separately from spaCy code. |
| FastEmbed/Hugging Face icon embedding model/cache | Not downloaded or copied into the default Docker image; lexical icon search uses tracked JSON. Semantic mode needs two explicit opt-in/risk flags. | `UNKNOWN_BLOCKED`/`INVENTORY_GAP`; exact model revision, files, hashes, model card, dataset/model license, and redistribution terms are not in the artifact policy. |
| Mem0 local data/model integrations | Python packages are locked; external embedding/LLM models are configurable. | Package code is SBOM-covered, but model/service terms are `EXTERNAL_TERMS`. |
| Tesseract and English OCR data | Debian packages installed when `INSTALL_TESSERACT=true`. | `IDENTIFIED_UNREVIEWED`/`INVENTORY_GAP`; exact versions/licenses/data terms must come from final image inventory. |
| `@llamaindex/liteparse` | Locked npm dependency; shared runner at `electron/resources/document-extraction/liteparse_runner.mjs`. | Package is SBOM-covered but final native/runtime contents, notices, and runner provenance require review. |
| Sharp and platform-native add-ons | Locked npm dependency at root/Next/Electron, including optional platform packages. | Node SBOM/NOTICE review plus final-platform binary/license verification required. |
| PyInstaller-built backend | Electron build invokes PyInstaller through uv and bundles the Python graph. | Python SBOM is an input, not proof of the frozen package contents/notices. Produce per-platform installer inventory. |
| Nginx, Python, Node.js, zstd, system libraries, Debian Noto fonts | Base image and apt installation in Dockerfile. | `INVENTORY_GAP`; generate final OCI OS/filesystem SBOM and include required licenses. |

No native component in this table is marked legally approved by this document.

## Copied, generated, and derived source

The Phase 0 search found no comprehensive third-party copied-source register or
per-file origin headers outside package notices/licenses. Areas requiring explicit
review include:

- the 9,073-file icon corpus and derived vectorstore;
- template JSON, SVG freeforms, images, thumbnails, and converted design data;
- the Freepik-marked 404 illustration;
- `servers/fastapi/openai_spec.json`, which is consumed by the MCP server but does
  not carry generation/source revision metadata;
- `electron/resources/document-extraction/liteparse_runner.mjs`, which integrates
  a third-party package but has no separate provenance note;
- copied build/license helper scripts and any generated/frozen Electron/backend
  output; and
- inline example HTML/prompts/media URLs.

Status: `INVENTORY_GAP`. This does not assert that the files are third-party; it
states that the repository evidence is insufficient to prove origin for a public
distribution review.

For generated files, record the generator name/version/hash, input sources and
rights, deterministic command, transformation, output hashes, and whether the
output incorporates copyrightable source material.

## Required provenance record per asset

Every retained static/downloaded asset should have a machine-readable record with:

- stable asset ID and all shipped paths;
- human title/type and purpose;
- creator/copyright owner;
- exact original source URL/repository/release/commit and retrieval date;
- original and shipped SHA-256;
- transformations and tool versions;
- exact license identifier and preserved license text;
- commercial redistribution, modification, embedding, export, app-store, and
  SaaS-use decision;
- attribution/NOTICE/source-offer/trademark/model-release obligations;
- reviewer, decision date, platforms/releases, and evidence link;
- expiration/re-review trigger; and
- replacement/removal owner.

Purchase receipts or private agreements belong in the approved restricted legal
system, not Git. The repository record should reference them without including
personal, payment, account, or secret data.

## Release gate and remediation order

Before a paid/public release:

1. remove or replace the Freepik-marked 404 illustration and every other asset
   without a defensible rights chain;
2. establish per-template and per-media provenance, including all 12 local fonts;
3. pin/document the Phosphor corpus version and include its exact required
   license/notice while separately reviewing brand logos;
4. replace hardcoded Pexels/Unsplash examples with owned fixtures and preserve
   stock-provider metadata/attribution for runtime selections;
5. vendor and hash reviewed preview scripts/fonts or keep remote-code paths
   disabled;
6. finish Electron/Chromium, export, ImageMagick, spaCy, FastEmbed, OCR, OS-package,
   and installer inventory/license reviews;
7. generate and archive package, OCI, model/artifact, and installer SBOMs;
8. inspect the final shipped bytes and user-facing notice/attribution surfaces;
   and
9. obtain explicit authorized legal/release approval tied to immutable hashes.

Until then, unknown assets and the export/runtime categories identified above are
release blockers, even if the application source code itself declares Apache-2.0.

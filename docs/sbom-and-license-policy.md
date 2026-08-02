# SBOM and license review policy

Last reviewed: 2026-08-02

This policy covers dependency inventories, third-party notices, license review,
and release exceptions. It is an engineering control, not legal advice. The
organization's authorized legal reviewer makes final distribution decisions.

## Release rule

Every release candidate must have a reproducible inventory for all shipped
dependency graphs and artifacts. A component with an unknown license, unknown
source, missing required notice/source offer, unresolved Critical/High security
finding, or unclear redistribution right blocks release unless:

1. the component/feature is excluded or disabled in production;
2. automated tests prove the disabled state fails closed;
3. the release record identifies the residual packaged bytes, if any; and
4. a time-limited exception is approved under the process below.

A hash proves file identity, not ownership or redistribution permission. An SBOM
proves inventory, not license compliance or absence of vulnerabilities.

## Authoritative inputs

| Ecosystem | Manifest and lock input | Inventory output |
| --- | --- | --- |
| Repository Node runtime/tools | `package.json`, `package-lock.json` | `artifacts/sbom/root-node.cdx.json` |
| Next.js | `servers/nextjs/package.json`, `servers/nextjs/package-lock.json` | `artifacts/sbom/nextjs.cdx.json` |
| Electron | `electron/package.json`, `electron/package-lock.json` | `artifacts/sbom/electron.cdx.json` |
| FastAPI | `servers/fastapi/pyproject.toml`, `servers/fastapi/uv.lock` | `artifacts/sbom/python.cdx.json` |
| Checksum-policy artifacts | `config/artifact-integrity.json` | `artifacts/sbom/external-artifacts.cdx.json` |

`config/artifact-integrity.json` is the inventory/checksum policy for downloaded
export, Chromium, ImageMagick, and model artifacts. The generated external BOM
records only policy entries with known hashes (presentation-export archives,
ImageMagick archives, and the spaCy model) and records the unresolved Electron
Chromium status as metadata. It is not an inventory of extracted bytes and does
not make unresolved artifacts complete or approved.

Root `LICENSE` is the Apache License 2.0 for Presenton code. Root `NOTICE` and
`servers/fastapi/NOTICE` contain generated dependency notices, but their presence
does not establish coverage of every Node graph, Debian package, model, static
asset, or downloaded binary. Static/non-package assets are tracked separately in
`docs/license-and-asset-provenance.md`.

## Reproducible generation

Use the pinned repository toolchain and a clean checkout. Node inventories use
`@cyclonedx/cyclonedx-npm 6.0.0`, package-lock-only analysis, CycloneDX JSON 1.6,
reproducible output, schema validation, and the three committed lockfiles. Python
uses the locked `cyclonedx-bom 7.3.1` development dependency and the active
Python 3.11 uv environment.

From the repository root:

```text
npm ci
cd servers/fastapi
uv sync --locked --dev
cd ../..
npm run sbom
```

Focused commands are:

```text
npm run sbom:node
npm run sbom:python
```

`sbom:node` emits the three Node package BOMs and the policy-derived
external-artifact BOM; `sbom:python` emits the FastAPI environment BOM.

The output directory is ignored by Git because these are generated evidence
files. Release automation must archive the exact five JSON outputs, their
SHA-256 hashes, the source commit, tool versions, build timestamp, and reviewer
decision. The test workflow currently retains the Node/external outputs and the
Python output as two CI artifacts. A release process must still bring them into
one immutable evidence set tied to the released image/installers.

The Node generator validates its three package BOMs and fails on invalid or
inconsistent lock input. The release process must additionally schema-validate
the Python and policy-derived external BOMs and fail if any input is missing,
inconsistent, or invalid. Do not edit generated JSON by hand. A review
annotation belongs in the release record or an exception record, not inside
regenerated inventory data.

## Coverage gaps requiring supplemental inventory

The repository command covers four package-manager dependency graphs plus the
known-hash entries in the external-artifact policy. Before a distributable
release, also inventory:

- every Debian package and version in the final server image, including Nginx,
  Chromium, ImageMagick, font packages, Tesseract, zstd, and their transitive OS
  libraries;
- the final OCI image filesystem and its base-image digests;
- Electron itself, Chromium bundled inside Electron, native npm add-ons, unpacked
  resources, installers, and platform signing/update components;
- the separate export Chromium archive used by Electron;
- presentation-export runtime archives and the files extracted from them;
- ImageMagick portable/AppImage assets;
- spaCy, FastEmbed/Hugging Face, OCR, and other downloaded model/data files;
- fonts, icons, template media, sample files, screenshots, GIFs, video, provider
  logos, and other static assets;
- code copied or generated from another repository/specification; and
- build-time-only tools when their output embeds runtime code or notices.

The Docker release workflow requests a BuildKit SBOM attestation. Verify that it
is attached to the final image digest, record the actual generator/version, and
reconcile its coverage. The repository does not pin a separate approved
OCI/filesystem scanner, so select one by immutable version/digest if the BuildKit
attestation does not meet the required OS/filesystem coverage.

## NOTICE generation and review

`scripts/rebuild_notice_all.py` scans one Python virtual environment and one Node
`node_modules` tree, then overwrites root `NOTICE`. Its default Node tree is
`servers/nextjs/node_modules`. It is useful for rebuilding its covered inventory,
but it does not merge root, Next.js, and Electron Node trees and does not cover OS
packages/static assets.

To reproduce its current default inputs after locked installs:

```text
python scripts/rebuild_notice_all.py \
  --python-venv servers/fastapi/.venv \
  --node-modules servers/nextjs/node_modules
```

Before accepting a generated NOTICE diff:

1. confirm the virtual environment and `node_modules` tree came from the committed
   lockfiles;
2. compare package names/versions with the matching SBOMs;
3. identify missing license text, `UNKNOWN`, `SEE LICENSE IN`, custom terms,
   attribution, source-offer, notice, patent, or trademark requirements;
4. preserve upstream license and notice text verbatim where required;
5. ensure the distributable actually includes the appropriate LICENSE/NOTICE
   material in a user-accessible location; and
6. have the authorized reviewer approve the result.

Do not run the script successively for different Node trees and treat the last
overwritten file as a combined inventory. A future improvement should generate a
deterministic merged NOTICE from all four SBOM/installation graphs.

## Review workflow

### 1. Inventory reconciliation

For each release candidate, reconcile:

- direct manifests against lockfiles;
- SBOM components against installed/package contents;
- downloaded artifact policy against actual downloaded and installed hashes;
- final container/installer inventory against package-manager SBOMs; and
- static asset paths against the provenance register.

Investigate every missing, extra, duplicated, or version-ambiguous component.
Development-only dependencies must be marked as such, but still reviewed if a
build tool can embed them into output.

### 2. Security review

Scan the final SBOMs and artifacts with approved, version-pinned vulnerability
sources/tools. Record database snapshot time because vulnerability data changes.

- Critical and High findings block release unless the affected component is
  absent from production or production-disabled with a regression test and an
  approved, expiring exception.
- Medium and Low findings require triage, an owner, and a remediation/review date.
- "Not reachable" is a technical assertion that requires call-path/build evidence;
  it is not inferred from the dependency being transitive.
- A scanner false positive requires package/version/path evidence and should be
  rechecked when either the component or advisory changes.

### 3. License and obligations review

Classify every component by the exact license text shipped by that version. Do
not infer a license solely from a package registry label, repository homepage, or
another release.

At minimum, check:

- permission for source and binary redistribution and commercial use;
- attribution and NOTICE preservation;
- modification notices;
- patent terms and termination clauses;
- reciprocal, copyleft, and network-copyleft triggers;
- source-code or relinking offer requirements;
- restrictions on models, data, media, fonts, stock content, and trademarks;
- conflicts between app-store terms and third-party licenses; and
- whether SaaS use, downloadable output, or user-generated presentations creates
  additional terms/attribution duties.

"Permissive" is not a substitute for fulfilling notices. `NOASSERTION`, empty,
custom, non-SPDX, source-available, research-only, non-commercial, or unknown
terms require explicit legal review and block release by default.

### 4. Distribution verification

Inspect the final OCI image and every Electron installer—not only the source
tree—to confirm:

- required license/notice files are actually included and readable;
- excluded/unapproved bytes are absent;
- source offers or relinking materials are available where required;
- version/hash metadata matches the release record; and
- the application does not claim ownership of third-party trademarks/assets.

## Exception policy

An exception is a temporary release decision, not a permanent allowlist. It must
be stored in the release/security tracking system and contain:

- a stable exception ID;
- component name, exact version/hash, paths, dependency relationship, and
  affected release/platforms;
- finding type (security, license, provenance, notice, vulnerability-tool gap);
- severity and concrete user/deployment exposure;
- why removal or upgrade is not currently feasible;
- compensating control, including the exact feature flag or packaging exclusion;
- automated test proving the control fails closed;
- owner and approving security/legal/release authorities as applicable;
- issue/remediation link;
- approval and expiration dates; and
- rollback/kill-switch instructions.

Exceptions expire after at most one planned release cycle or 30 days, whichever
is shorter, unless the authorized policy owner explicitly sets a stricter limit.
Renewal requires fresh SBOM, advisory, reachability, and legal review. Unknown
provenance for static media or an executable is not eligible for silent acceptance;
exclude it or obtain evidence.

## Dependency and artifact update policy

Every dependency update must be isolated enough to review and must include:

1. the reason for change and upstream release/security notes;
2. a locked manifest/lockfile diff produced by the supported package manager;
3. install-script and transitive dependency review;
4. fresh SBOMs and NOTICE/license analysis;
5. vulnerability results and resolved/new finding comparison;
6. relevant unit, integration, build, packaging, and platform tests; and
7. the immutable source revision and final artifact/image hashes.

Additional rules:

- Never use `npm install` or unlocked uv resolution in a release build.
- Keep uv `index-strategy = "first-index"`; private indexes must be authenticated
  and ordered deliberately.
- Pin GitHub Actions by full commit SHA and base images by digest.
- Avoid runtime package installation. Download executable artifacts at build time
  over HTTPS, verify them before extraction/execution, and record the installed
  binary hash.
- Never use `curl | sh` or an unpinned "latest" URL.
- A change to an expected checksum must cite an independently authenticated
  upstream release; never bless unexpected bytes after a mismatch.
- Keep the unreviewed export feature disabled until both integrity and license
  gates pass on every platform.

## Release evidence checklist

- [ ] Four package-manager CycloneDX JSON files generated from a clean locked
      install and schema-validated.
- [ ] Policy-derived external-artifact CycloneDX JSON generated, validated, and
      reconciled to downloaded and extracted bytes.
- [ ] Final OCI image SBOM tied to the image digest.
- [ ] Each desktop installer/package SBOM tied to its SHA-256 and signing identity.
- [ ] Downloaded/model/static asset inventory reconciled to provenance records.
- [ ] Root and packaged NOTICE/LICENSE materials reviewed in final artifacts.
- [ ] Vulnerability scan snapshot and disposition for every Critical/High finding.
- [ ] License/obligation review with no unknown or unapproved shipped component.
- [ ] Exceptions are approved, tested, unexpired, and included in release notes
      where disclosure is required.
- [ ] SBOMs, hashes, tool versions, source revision, and review decisions are
      archived according to the release-retention policy.

If any checkbox is incomplete, label the output a development/pre-release
artifact and do not offer it as a paid public release.

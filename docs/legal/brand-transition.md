# Bayanly brand and legal transition

Status: engineering identity migration complete for Sprint 2; production
release approval is **not** granted by this document.

## Approved display identity

The product display name is **Bayanly AI** (short name **Bayanly**) and its
approved description is “An AI-powered platform for creating professional
presentations in Arabic and English.” The display publisher is **Bayanly
Technologies** and support contact is `Ayman.Naeem@gmail.com`. The palette and
approved source assets are recorded in `config/product-identity.json`; copied
runtime assets live under versioned `brand/v1` paths and their source files in
`assets/branding` are retained unchanged.

The publisher value is a display request only. Its registry status is
`REQUIRES_LEGAL_REVIEW`; nothing in code, package metadata, or this document
asserts incorporation, trademark ownership, code-signing authority, store
ownership, or legal clearance.

## Operational release gates

| Requested value | Current status | Why it is not activated automatically | Required approval/evidence |
| --- | --- | --- | --- |
| `example.ai` | `REQUIRES_DOMAIN_CONFIGURATION`, placeholder | would publish invalid metadata/links | owned production domain, DNS/TLS, deployment configuration, security review |
| `ai.bayanly.desktop` | `COMPATIBILITY_RETAINED` (active ID remains `com.presenton.presenton`) | changing an app ID can create a second install and break updates/data paths | signing/store ownership, installed-upgrade test, migration/rollback plan, legal approval |
| `bayanly://open` | `REQUIRES_INSTALLER_AND_SECURITY_REVIEW` | no existing protocol contract was found and deep links expand attack surface | installer registration, strict URL parser/allowlist, platform tests, threat review |
| `updates.bayanly.ai` | `REQUIRES_UPDATE_CHANNEL_CONFIGURATION` | domain/channel/artifact signing is not configured | owned TLS endpoint, signed manifests/artifacts, rollout/rollback test |
| Bayanly Technologies | `REQUIRES_LEGAL_REVIEW` | display instruction is not evidence of a legal entity or trademark clearance | counsel/owner approval and signing identity evidence |

`npm run brand:release-check` fails closed while any of these release gates
remain unresolved. Ordinary development and CI use `npm run brand:scan`, which
allows explicitly documented compatibility surfaces but still checks generated
metadata, active brand surfaces, approved assets, and attribution.

## Upstream attribution and compatibility

Bayanly is derived from Presenton and continues under the repository’s
Apache-2.0 license. LICENSE remains unchanged. NOTICE and README carry explicit
derivation attribution. Presenton references are intentionally retained when
they identify upstream documentation/repositories, legacy release downloads,
stable event/token/environment names, Docker volumes, Sentry contexts, local
data directories, app IDs, runtime manifests, or update compatibility URLs.

Those identifiers must not be renamed as cosmetic cleanup. Each requires an
upgrade-compatible alias or migration, installed-version testing, and the exit
evidence in `docs/architecture/deprecation-register.md`.

## Rollback controls

`NEW_BRAND_SHELL_ENABLED` / `NEXT_PUBLIC_NEW_BRAND_SHELL_ENABLED` default to
enabled for the new display shell. `NEW_EXPORT_METADATA_ENABLED` defaults to
disabled because the separately versioned exporter has not completed its legal
and supply-chain gate. The older assets and compatibility updater endpoint are
retained so an operator can roll the shell back without changing stored data or
desktop identity.

## Human checklist before a public release

- Confirm name/trademark and publisher clearance in every target jurisdiction.
- Replace the placeholder domain and verify canonical/Open Graph/update URLs.
- Establish code-signing, notarization, Microsoft Store, and update-channel
  ownership; test an upgrade from the currently installed app ID.
- Review every approved asset for license/trademark provenance and archive the
  signed approval record outside the repository.
- Run the production brand release check and the full repository validation.
- Review README, LICENSE, NOTICE, privacy disclosures, support contact, and
  third-party attribution with counsel or the accountable owner.

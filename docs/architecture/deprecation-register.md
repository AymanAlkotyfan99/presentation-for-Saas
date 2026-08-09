# Deprecation register

Nothing in this register may be deleted merely because its name says V1 or an
import search is small. Removal requires all exit evidence and owner approval.

| Surface | State | Active callers/evidence | Compatibility promise | Owner | Exit evidence | Earliest removal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `V1ContentRender` | deprecated, active | `PresentationRender`, `SlideThumbnailCard` | persisted V1 decks remain readable/exportable | presentations | zero V1 read telemetry for one release; golden render/export conversion passes | after V1 read shutdown |
| `V1SelectEdit` | deprecated candidate | no static importer found in Sprint 1 | do not restore new callers | slide-editor | production bundle/runtime telemetry confirms no dynamic use; manual V1 editing smoke | next cleanup sprint after evidence |
| `PresentationVersion.V1_STANDARD` | compatibility schema | legacy rows and tests | reads/writes default enabled; flags are reversible | presentations/data | conversion audited, backup/restore rehearsed, no V1 traffic | explicit data migration sprint |
| legacy `presentations`/`slides` content, UI, HTML and layout fields | compatibility data, active | current renderer/editor/export paths and canonical conversion adapter | retained unchanged; canonical records are additive and fallback defaults enabled | presentations/data | canonical cohort parity, migration audit, Sprint 5/6/16 compatibility evidence, explicit data-owner approval | never in Sprint 4 |
| `presentation_layout_code` model/table | legacy persistence | migration history and legacy helpers/tests | schema retained | presentations/data | live-row audit zero or conversion complete; migration approved | schema migration sprint |
| `templates/custom_layout_from_db.py` | compatibility adapter | legacy template resolution | legacy stored layouts continue to resolve | templates | caller/row telemetry zero; V2 equivalent verified | after V1 shutdown |
| old Presenton web/Electron assets | compatibility assets | old installs/docs/export/updater may refer to paths | do not overwrite; new shell uses `/brand/v1` | release-engineering | updater and installed-upgrade test proves no old path lookup | later asset cleanup sprint |
| `PRESENTON_*` environment variables and runtime manifest names | stable technical IDs | packaging, deployments, scripts | continue accepting existing names | release-engineering | alias migration released and observed; deployment owners approve | not scheduled |
| `com.presenton.presenton` desktop app ID | compatibility retained | installed desktop upgrade identity | must not change without signing/update migration | release-engineering/legal | signing identities, store records, updater migration and legal approval | not scheduled |
| upstream `presenton/presenton` attribution/update compatibility URLs | attribution/compatibility | NOTICE/README/update fallback | must remain accurate while derived/upstream channel is used | legal/release-engineering | independent channel live; attribution still remains where legally required | compatibility URL only after channel cutover |

Removed in Sprint 1: `api/v1/ppt/endpoints/layouts.py`, because the router was
not registered, appeared in no OpenAPI operation, and had no repository caller.

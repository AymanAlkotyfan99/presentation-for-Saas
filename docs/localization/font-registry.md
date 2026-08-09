# Arabic font registry

Core UI fonts must be immutable repository assets. Runtime downloads and
mutable third-party font CSS are not allowed for the core shell.

| Family | Source/version | License and redistribution | Web | Desktop | Export | Fallback/status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Noto Sans Arabic | Google Fonts `ofl/notosansarabic`, version 2.012, SHA-256 `63111B5B2E074DD48CC67692E0A2726D86EE94C1C37FE8598257B7B4E87E869E` | SIL OFL 1.1; unmodified redistribution permitted with included license | bundled variable TTF, active Arabic UI font | available when packaged Next assets are used | availability only; no embedding promise | Tahoma, Arial, sans-serif; `TECHNICALLY_MIGRATED`, human legal/font confirmation required |
| Cairo | candidate only | source/version/license must be reviewed before bundling | not bundled | not bundled | not assessed | `REQUIRES_FONT_REVIEW` |
| Tajawal | candidate only | source/version/license must be reviewed before bundling | not bundled | not bundled | not assessed | `REQUIRES_FONT_REVIEW` |
| IBM Plex Sans Arabic | candidate only | source/version/license must be reviewed before bundling | not bundled | not bundled | not assessed | `REQUIRES_FONT_REVIEW` |
| Noto Kufi Arabic | candidate only | source/version/license must be reviewed before bundling | not bundled | not bundled | not assessed | `REQUIRES_FONT_REVIEW` |

The exact Noto license is stored beside the font at
`servers/nextjs/app/fonts/licenses/NotoSansArabic-OFL.txt`. UI availability does
not imply PPTX embedding or editable-export support.


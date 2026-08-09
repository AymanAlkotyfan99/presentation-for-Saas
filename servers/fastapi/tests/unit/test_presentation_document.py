import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.presentation_document import CanonicalConversionStatus
from models.sql.slide import SlideModel
from modules.presentations.adapters import canonical_to_safe_html, canonical_to_v2_editor
from modules.presentations.domain import (
    CanonicalValidationError,
    canonical_checksum,
    canonical_json,
    validate_presentation_document,
)
from modules.presentations.domain.conversion_status import require_conversion_transition
from modules.presentations.migrations.legacy_document import convert_legacy_presentation
from modules.presentations.observability import record_canonical_metric
from modules.presentations.shadow_parity import compare_shadow_parity


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ROOT = REPOSITORY_ROOT / "schemas" / "presentation-document" / "fixtures"
SCHEMA = json.loads((FIXTURE_ROOT.parent / "v1.schema.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _load(folder: str, name: str):
    return json.loads((FIXTURE_ROOT / folder / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", MANIFEST["valid"])
def test_shared_valid_fixtures_match_json_schema_python_model_and_checksum(name):
    payload = _load("valid", name)
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(payload)
    document = validate_presentation_document(payload)
    assert canonical_checksum(document) == MANIFEST["valid"][name]["checksum"]
    assert canonical_json(document) == canonical_json(json.loads(canonical_json(document)))


@pytest.mark.parametrize("name", MANIFEST["invalid"])
def test_shared_invalid_fixtures_have_stable_codes(name):
    with pytest.raises(CanonicalValidationError) as raised:
        validate_presentation_document(_load("invalid", name))
    assert raised.value.code == MANIFEST["invalid"][name]["expectedCode"]


def test_schema_rejects_unknown_fields_and_authoring_html():
    payload = _load("valid", "minimal-en.json")
    payload["unknown"] = True
    assert list(Draft202012Validator(SCHEMA).iter_errors(payload))


def test_runtime_rejects_local_paths_data_urls_and_private_note_links():
    local_path = _load("valid", "minimal-en.json")
    local_path["metadata"]["description"] = "file at C:\\private\\deck.json"
    with pytest.raises(CanonicalValidationError) as path_error:
        validate_presentation_document(local_path)
    assert path_error.value.code == "CANONICAL_LOCAL_PATH_FORBIDDEN"

    data_url = _load("valid", "minimal-en.json")
    data_url["metadata"]["description"] = "data:image/svg+xml;base64,PHN2Zz4="
    with pytest.raises(CanonicalValidationError) as data_error:
        validate_presentation_document(data_url)
    assert data_error.value.code == "CANONICAL_EXECUTABLE_CONTENT"

    note_link = _load("valid", "speaker-notes.json")
    note_link["slides"][0]["speakerNotes"]["paragraphs"][0]["runs"][0][
        "hyperlink"
    ] = {"kind": "external", "href": "https://127.0.0.1/private"}
    with pytest.raises(CanonicalValidationError) as url_error:
        validate_presentation_document(note_link)
    assert url_error.value.code == "CANONICAL_URL_UNSAFE"


def test_runtime_is_strict_without_rejecting_json_schema_integer_floats():
    coerced = _load("valid", "text-heavy.json")
    coerced["slides"][0]["elements"][0]["zOrder"] = "0"
    with pytest.raises(CanonicalValidationError) as type_error:
        validate_presentation_document(coerced)
    assert type_error.value.code == "CANONICAL_SCHEMA_INVALID"

    equivalent = _load("valid", "text-heavy.json")
    equivalent["slides"][0]["elements"][0]["zOrder"] = 0.0
    normalized = validate_presentation_document(equivalent)
    assert normalized.slides[0].elements[0].z_order == 0
    payload = _load("valid", "minimal-en.json")
    payload["title"] = "<b>raw HTML</b>"
    assert list(Draft202012Validator(SCHEMA).iter_errors(payload))


def _legacy(version=PresentationVersion.V2_STANDARD, language="en", *, custom=False):
    presentation_id = uuid4()
    presentation = PresentationModel(
        id=presentation_id,
        version=version,
        content="Legacy topic",
        n_slides=1,
        language=language,
        title="عرض mixed" if language == "ar" else "Legacy deck",
        layout={"name": "custom-executable" if custom else "basic"},
        fonts={
            "Noto Sans Arabic": "https://example.com/font.css",
            "Inter": "https://example.com/inter.css",
        },
    )
    slide = SlideModel(
        id=uuid4(),
        presentation=presentation_id,
        layout_group="basic",
        layout="title",
        index=0,
        content={"title": "Structured content"},
        speaker_note="ملاحظة آمنة" if language == "ar" else "Safe note",
        html_content="<script>never execute()</script>",
        ui={
            "elements": [
                {
                    "type": "text",
                    "position": {"x": 80, "y": 80},
                    "size": {"width": 900, "height": 160},
                    "runs": [
                        {"text": "مرحبا ", "font": {"family": "Noto Sans Arabic"}},
                        {"text": "ARR +24%", "font": {"family": "Inter"}},
                    ],
                },
                {
                    "type": "image",
                    "position": {"x": 80, "y": 260},
                    "size": {"width": 640, "height": 360},
                    "data": "C:\\private\\legacy-image.png",
                    "fit": "cover",
                },
            ]
        },
    )
    return presentation, [slide]


@pytest.mark.parametrize("version", [PresentationVersion.V1_STANDARD, PresentationVersion.V2_STANDARD])
def test_legacy_conversion_is_deterministic_preserves_notes_and_hides_paths(version):
    presentation, slides = _legacy(version)
    first = convert_legacy_presentation(presentation, slides)
    second = convert_legacy_presentation(presentation, slides)

    assert first.checksum == second.checksum
    assert first.document.document_id == second.document.document_id
    assert first.document.slides[0].speaker_notes.paragraphs[0].runs[0].text == "Safe note"
    assert first.status == CanonicalConversionStatus.CONVERTED
    assert "legacy-html-ignored" in first.warnings
    assert "C:\\private" not in first.document.model_dump_json(by_alias=True)
    assert first.asset_mappings
    editor = canonical_to_v2_editor(first.document)
    assert editor[0]["elements"]


def test_arabic_mixed_direction_conversion_and_safe_html_adapter():
    presentation, slides = _legacy(language="ar")
    preview = convert_legacy_presentation(presentation, slides)
    assert preview.document.locale == "ar"
    assert preview.document.base_direction == "rtl"
    runs = preview.document.slides[0].elements[0].paragraphs[0].runs
    assert [run.text for run in runs] == ["مرحبا", "ARR +24%"]
    html_output = canonical_to_safe_html(preview.document)
    assert "<script>" not in html_output
    assert "C:\\private" not in html_output


def test_unsupported_custom_layout_is_visible_and_reviewable():
    presentation, slides = _legacy(custom=True)
    slides[0].ui = {"elements": [{"type": "svg", "svg": "<svg onload='x'>"}]}
    preview = convert_legacy_presentation(presentation, slides)
    assert preview.status == CanonicalConversionStatus.NEEDS_REVIEW
    assert "custom-layout-source-unsupported" in preview.unsupported_features
    assert "raw-svg-unsupported" in preview.unsupported_features
    assert preview.document.compatibility.requires_legacy_renderer is True


def test_conversion_status_machine_rejects_invalid_transition():
    require_conversion_transition(CanonicalConversionStatus.FAILED, CanonicalConversionStatus.CONVERTING)
    with pytest.raises(ValueError):
        require_conversion_transition(CanonicalConversionStatus.CONVERTED, CanonicalConversionStatus.FAILED)


def test_shadow_parity_covers_match_difference_unsupported_and_private_metrics():
    presentation, slides = _legacy()
    converted = convert_legacy_presentation(presentation, slides)
    matching = compare_shadow_parity(presentation, slides, converted.document)
    assert matching.status == "match"

    changed_payload = converted.document.model_dump(mode="json", by_alias=True, exclude_none=True)
    changed_payload["slides"][0]["elements"] = []
    changed = validate_presentation_document(changed_payload)
    assert compare_shadow_parity(presentation, slides, changed).status == "structural-difference"

    unsupported_presentation, unsupported_slides = _legacy(custom=True)
    unsupported = convert_legacy_presentation(unsupported_presentation, unsupported_slides)
    assert compare_shadow_parity(unsupported_presentation, unsupported_slides, unsupported.document).status == "unsupported"

    metric = record_canonical_metric(
        "shadow_parity",
        schema_version="1.0.0",
        parity_status="match",
        title="must be dropped",
        slide_text="must be dropped",
        image_url="must be dropped",
    )
    assert metric == {"event": "shadow_parity", "schema_version": "1.0.0", "parity_status": "match"}

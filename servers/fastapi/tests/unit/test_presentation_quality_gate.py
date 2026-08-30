from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.presentation_layout import PresentationLayoutModel, SlideLayoutModel
from models.presentation_outline_model import EvidenceSourceModel, PresentationOutlineModel, SlideOutlineModel
from models.presentation_structure_model import PresentationStructureModel
from modules.presentations.quality.bindings import apply_system_bindings, sanitize_generation_schema
from modules.presentations.quality.contracts import PresentationQualityError, RepairBudget
from modules.presentations.quality.facts import fact_issues
from modules.presentations.quality.gate import (
    finalize_generated_slide_content,
    validate_final_presentation,
)
from modules.presentations.quality.layout import (
    is_layout_compatible,
    repair_structure_for_content,
    reselect_layout_after_quality_failure,
)
from modules.presentations.quality.visual import final_ui_issues
from utils.llm_calls import generate_slide_content as slide_content_module


def _quality(*, claims=None, charts=None):
    return {
        "quantitative_claims": claims or [],
        "charts": charts or [],
    }


def _outline(content="## Title\nContent", evidence=None):
    return SlideOutlineModel(content=content, evidence=evidence or [])


def _web_source(snippet="The projected CAGR is 31%."):
    return EvidenceSourceModel(
        id="web-1",
        provenance="web_search",
        title="Authoritative report",
        url="https://example.com/report",
        snippet=snippet,
    )


def _text_element(name, text, *, width=500, height=80, font_size=20):
    return {
        "type": "text",
        "decorative": False,
        "name": name,
        "text": text,
        "runs": [{"text": text}],
        "size": {"width": width, "height": height},
        "font": {"size": font_size, "line_height": 1.1},
    }


def _ui(*elements):
    return {"components": [{"elements": list(elements)}], "elements": []}


def _rules(issues):
    return {issue.rule_id for issue in issues}


def test_english_slide_rejects_unexpected_chinese_script():
    with pytest.raises(PresentationQualityError) as exc:
        finalize_generated_slide_content(
            {"title": "Accessible content formats for学习", "__quality__": _quality()},
            outline=_outline(),
            language="English",
        )
    assert "LANGUAGE.UNEXPECTED_SCRIPT_EN" in _rules(exc.value.issues)


def test_arabic_slide_allows_english_technical_acronym():
    result = finalize_generated_slide_content(
        {"title": "استخدام AI و AR/VR في التعليم", "__quality__": _quality()},
        outline=_outline("## التعليم"),
        language="Arabic",
    )
    assert result.passed


def test_unbalanced_markdown_title_is_repaired_as_plain_text():
    result = finalize_generated_slide_content(
        {"title": "Impact on **Critical Thinking", "__quality__": _quality()},
        outline=_outline(),
        language="English",
    )
    assert result.value["title"] == "Impact on Critical Thinking"


@pytest.mark.parametrize("break_tag", ["<br>", "<br/>", "<br />"])
def test_html_break_variants_are_normalized(break_tag):
    result = finalize_generated_slide_content(
        {"body": f"First{break_tag}Second", "__quality__": _quality()},
        outline=_outline(),
        language="English",
    )
    assert result.value["body"] == "First\nSecond"


def test_metric_value_without_unit_is_rejected():
    issues = fact_issues(
        {
            "metric_value": "31",
            "__quality__": _quality(
                claims=[{
                    "path": "metric_value", "value": 31, "unit": "", "label": "CAGR",
                    "provenance": "web_search", "source_id": "web-1",
                }]
            ),
        },
        [_web_source()],
    )
    assert "FACT.METRIC_UNIT_MISSING" in _rules(issues)


def test_metric_without_evidence_is_rejected():
    issues = fact_issues(
        {
            "metric_value": "31%",
            "__quality__": _quality(
                claims=[{
                    "path": "metric_value", "value": 31, "unit": "%", "label": "CAGR",
                    "provenance": "web_search", "source_id": "missing",
                }]
            ),
        },
        [],
    )
    assert "FACT.METRIC_SOURCE_INVALID" in _rules(issues)


def test_grounded_metric_with_source_passes():
    result = finalize_generated_slide_content(
        {
            "metric_value": "31%",
            "__quality__": _quality(
                claims=[{
                    "path": "metric_value", "value": 31, "unit": "%", "label": "Projected CAGR",
                    "provenance": "web_search", "source_id": "web-1",
                }]
            ),
        },
        outline=_outline(evidence=[_web_source()]),
        language="English",
    )
    assert result.passed


def test_chart_with_unproven_values_is_rejected():
    chart = {
        "chart_type": "bar",
        "title": "Adoption",
        "categories": ["Students", "Teachers"],
        "series": [{"name": "Rate", "values": [89, 73]}],
    }
    issues = fact_issues(
        {
            "chart": chart,
            "__quality__": _quality(
                charts=[{
                    "path": "chart", "unit": "%", "label": "Adoption",
                    "provenance": "web_search", "source_id": "web-1",
                }]
            ),
        },
        [_web_source("This report discusses adoption without numerical values.")],
    )
    assert "FACT.CHART_VALUES_NOT_SUPPORTED_BY_SOURCE" in _rules(issues)


def test_grounded_chart_retains_verified_unit_provenance_and_source_url():
    chart = {
        "chart_type": "bar",
        "title": "Projected CAGR",
        "categories": ["2025", "2026"],
        "series": [{"name": "Rate", "values": [31, 28]}],
    }
    result = finalize_generated_slide_content(
        {
            "chart": chart,
            "__quality__": _quality(
                charts=[{
                    "path": "chart", "unit": "%", "label": "Projected CAGR",
                    "provenance": "web_search", "source_id": "web-1",
                }]
            ),
        },
        outline=_outline(evidence=[_web_source("Projected CAGR is 31% in 2025 and 28% in 2026.")]),
        language="English",
    )
    assert result.value["chart"]["unit"] == "%"
    assert result.value["chart"]["provenance"] == "web_search"
    assert result.value["chart"]["source_id"] == "web-1"
    assert result.value["chart"]["source"] == "https://example.com/report"


def test_invalid_page_value_is_not_accepted_without_binding():
    issues = final_ui_issues(_ui(_text_element("page_number", "Page AI", width=100, height=30)))
    assert "METADATA.PAGE_NOT_SYSTEM_BOUND" in _rules(issues)


def test_page_number_is_derived_from_canonical_order_and_preserves_style():
    bound = apply_system_bindings(
        _ui(_text_element("page_number", "Page 03", width=100, height=30)),
        slide_number=5,
        total_slides=10,
        layout_id="content",
    )
    page = list(bound["components"])[0]["elements"][0]
    assert page["text"] == "Page 05"
    assert page["system_value"] == 5
    assert not final_ui_issues(bound)


def test_presenter_metadata_not_provided_is_omitted():
    bound = apply_system_bindings(
        _ui(_text_element("presenter_name", "Higher Ed AI Group")),
        slide_number=1,
        total_slides=10,
        layout_id="cover",
    )
    presenter = bound["components"][0]["elements"][0]
    assert presenter["text"] == ""
    assert presenter["system_binding"] == "omitted_metadata"


def test_model_generated_organization_is_removed_from_schema_and_ui():
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "organization": {"type": "string"},
        },
        "required": ["title", "organization"],
    }
    sanitized = sanitize_generation_schema(schema)
    assert list(sanitized["properties"]) == ["title"]
    assert sanitized["required"] == ["title"]
    assert sanitized["properties"]["title"]["x-bayanly-text-format"] == "plain_text"


def test_short_ar_vr_identifier_fits_without_character_breaking():
    element = _text_element("badge_label", "AR/VR", width=60, height=24, font_size=18)
    assert "VISUAL.SHORT_LABEL_DOES_NOT_FIT" not in _rules(final_ui_issues(_ui(element)))


def test_long_card_title_is_rejected_when_it_cannot_fit():
    element = _text_element("card_title", "A very long card title that cannot fit", width=90, height=22, font_size=18)
    assert "VISUAL.TEXT_HEIGHT_OVERFLOW" in _rules(final_ui_issues(_ui(element)))


def test_long_body_copy_is_rejected_when_it_cannot_fit():
    element = _text_element("body", "word " * 120, width=220, height=50, font_size=16)
    assert "VISUAL.TEXT_HEIGHT_OVERFLOW" in _rules(final_ui_issues(_ui(element)))


def test_semantically_duplicated_comparison_columns_are_rejected():
    group = {
        "type": "grid",
        "children": [
            _text_element("body", "Fast adaptive learning for every student"),
            _text_element("body", "Adaptive learning that is fast for every student"),
        ],
    }
    assert "CONSISTENCY.DUPLICATE_SIBLING_CONTENT" in _rules(final_ui_issues(_ui(group)))


def test_missing_image_asset_is_rejected():
    image = {
        "type": "image",
        "decorative": False,
        "name": "hero",
        "data": "/static/images/placeholder.jpg",
    }
    assert "ASSET.IMAGE_MISSING" in _rules(final_ui_issues(_ui(image)))


def test_metric_layout_without_supported_metrics_is_incompatible():
    layout = SlideLayoutModel(
        id="metrics",
        json_schema={
            "type": "object",
            "properties": {"metric_value": {"type": "string"}},
            "required": ["metric_value"],
        },
    )
    assert not is_layout_compatible(layout, _outline("## Benefits\nMore personalized support"))


def test_chart_layout_without_chart_quality_data_is_incompatible():
    layout = SlideLayoutModel(
        id="chart",
        json_schema={
            "type": "object",
            "properties": {
                "chart": {
                    "type": "object",
                    "properties": {
                        "chart_type": {"type": "string"},
                        "categories": {"type": "array"},
                        "series": {"type": "array"},
                    },
                }
            },
        },
    )
    assert not is_layout_compatible(layout, _outline("## Adoption trends\nAdoption is growing"))


def test_english_product_proper_nouns_are_allowed():
    result = finalize_generated_slide_content(
        {"body": "OpenAI ChatGPT works with Microsoft Teams and Canvas LMS.", "__quality__": _quality()},
        outline=_outline(),
        language="English",
    )
    assert result.passed


def test_arabic_english_mixed_technical_content_is_allowed():
    result = finalize_generated_slide_content(
        {"body": "يساعد ChatGPT و LMS المعلمين في تصميم محتوى AI.", "__quality__": _quality()},
        outline=_outline("## الذكاء الاصطناعي"),
        language="Arabic",
    )
    assert result.passed


def test_repairs_keep_text_structured_and_editable():
    bound = apply_system_bindings(
        _ui(_text_element("page_number", "Page ED", width=100, height=30)),
        slide_number=2,
        total_slides=10,
        layout_id="content",
    )
    page = bound["components"][0]["elements"][0]
    assert page["type"] == "text"
    assert page["runs"] == [{"text": "2"}]


def test_layout_repair_budget_is_bounded_and_cannot_loop_forever():
    layouts = PresentationLayoutModel(
        name="test",
        slides=[
            SlideLayoutModel(id="metrics", json_schema={"type": "object", "properties": {"metric_value": {"type": "string"}}}),
            SlideLayoutModel(id="plain", json_schema={"type": "object", "properties": {"title": {"type": "string"}}}),
        ],
    )
    with pytest.raises(ValueError, match="budget exhausted"):
        repair_structure_for_content(
            PresentationStructureModel(slides=[0]),
            PresentationOutlineModel(slides=[_outline("## Qualitative topic")]),
            layouts,
            budget=RepairBudget(max_layout_reselections=0),
        )


def test_fact_failure_reselects_one_non_metric_layout_with_shared_budget():
    layouts = PresentationLayoutModel(
        name="test",
        slides=[
            SlideLayoutModel(
                id="metrics",
                json_schema={
                    "type": "object",
                    "properties": {"metric_value": {"type": "string"}},
                },
            ),
            SlideLayoutModel(
                id="plain",
                json_schema={
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                },
            ),
        ],
    )
    budget = RepairBudget(max_layout_reselections=1, max_slide_regenerations=1)
    selected = reselect_layout_after_quality_failure(
        layouts,
        _outline("## Adoption rose 31%", [_web_source()]),
        current_index=0,
        slide_index=1,
        rule_ids={"FACT.METRIC_EVIDENCE_MISSING"},
        budget=budget,
    )

    assert selected == 1
    assert budget.layout_reselections_used == 1
    assert budget.slide_regenerations_used == 1
    assert (
        reselect_layout_after_quality_failure(
            layouts,
            _outline("## Adoption rose 31%", [_web_source()]),
            current_index=0,
            slide_index=1,
            rule_ids={"FACT.METRIC_EVIDENCE_MISSING"},
            budget=budget,
        )
        is None
    )


def test_final_presentation_gate_rejects_wrong_slide_count():
    slides = [SimpleNamespace(id="slide-1", index=0, ui=_ui())]
    with pytest.raises(PresentationQualityError) as exc:
        validate_final_presentation(slides, expected_slide_count=2)
    assert "STRUCTURE.WRONG_SLIDE_COUNT" in _rules(exc.value.issues)


def test_presentation_auto_fix_budget_is_enforced():
    with pytest.raises(PresentationQualityError) as exc:
        finalize_generated_slide_content(
            {"title": "**One", "body": "Two<br>Three", "__quality__": _quality()},
            outline=_outline(),
            language="English",
            repair_budget=RepairBudget(max_auto_fixes=1),
        )
    assert "REPAIR.PRESENTATION_BUDGET_EXHAUSTED" in _rules(exc.value.issues)


def test_quality_failure_does_not_multiply_provider_fallback_or_retry(monkeypatch):
    generated = {
        "title": "English text with 学习 contamination",
        "__speaker_note__": "Plain speaker note " * 10,
        "__quality__": _quality(),
    }
    structured = AsyncMock(return_value=generated)
    monkeypatch.setattr(slide_content_module, "generate_structured_with_schema_retries", structured)
    monkeypatch.setattr(slide_content_module, "get_client", lambda config=None: object())
    monkeypatch.setattr(slide_content_module, "get_llm_config", lambda **kwargs: {})
    monkeypatch.setattr(slide_content_module, "get_model", lambda: "provider-neutral-model")

    layout = SlideLayoutModel(
        id="plain",
        json_schema={
            "type": "object",
            "properties": {"title": {"type": "string", "maxLength": 100}},
            "required": ["title"],
        },
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            slide_content_module.get_slide_content_from_type_and_outline(
                layout,
                _outline(),
                "English",
            )
        )
    assert exc.value.status_code == 422
    assert structured.await_count == 1

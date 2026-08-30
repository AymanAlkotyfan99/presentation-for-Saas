from __future__ import annotations

import math
import re
from typing import Any, Iterable

from models.presentation_outline_model import EvidenceSourceModel

from .contracts import QualityAction, QualityIssue, QualitySeverity
from .text import iter_string_values


METRIC_NAME_RE = re.compile(
    r"(?:metric|stat|value|amount|percent|percentage|rate|ratio|cagr|price|revenue|cost|growth|adoption|score|kpi)",
    re.IGNORECASE,
)
QUANTIFIED_VALUE_RE = re.compile(
    r"(?<![\w])(?P<currency>[$€£¥])?\s*(?P<value>-?\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>%|x|×|bps?|percent|percentage|million|billion|trillion|thousand|hours?|days?|years?|usd|eur|gbp)?(?![\w])",
    re.IGNORECASE,
)
ILLUSTRATIVE_RE = re.compile(
    r"\b(?:illustrative|illustration|example|sample|hypothetical|estimate|estimated|scenario)\b",
    re.IGNORECASE,
)


def quality_metadata_schema() -> dict[str, Any]:
    provenance = {
        "type": "string",
        "enum": ["web_search", "user_provided", "illustrative"],
    }
    claim = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 256},
            "value": {"type": "number"},
            "unit": {"type": "string", "minLength": 1, "maxLength": 64},
            "label": {"type": "string", "minLength": 1, "maxLength": 256},
            "provenance": provenance,
            "source_id": {"type": ["string", "null"], "maxLength": 128},
        },
        "required": ["path", "value", "unit", "label", "provenance", "source_id"],
    }
    chart = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 256},
            "unit": {"type": "string", "minLength": 1, "maxLength": 64},
            "label": {"type": "string", "minLength": 1, "maxLength": 256},
            "provenance": provenance,
            "source_id": {"type": ["string", "null"], "maxLength": 128},
        },
        "required": ["path", "unit", "label", "provenance", "source_id"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "description": (
            "Non-visual provenance metadata. List every factual quantitative claim and "
            "every chart. Use only supplied evidence source IDs. Use illustrative only "
            "when the visible label explicitly says it is illustrative or estimated."
        ),
        "properties": {
            "quantitative_claims": {
                "type": "array",
                "items": claim,
                "maxItems": 32,
            },
            "charts": {"type": "array", "items": chart, "maxItems": 8},
        },
        "required": ["quantitative_claims", "charts"],
    }


def fact_issues(
    content: dict[str, Any],
    evidence: Iterable[EvidenceSourceModel],
) -> list[QualityIssue]:
    evidence_by_id = {source.id: source for source in evidence}
    metadata = content.get("__quality__")
    if not isinstance(metadata, dict):
        return [_issue("FACT.PROVENANCE_METADATA_MISSING", "__quality__")]

    raw_claims = metadata.get("quantitative_claims")
    claims = raw_claims if isinstance(raw_claims, list) else []
    raw_charts = metadata.get("charts")
    chart_claims = raw_charts if isinstance(raw_charts, list) else []
    issues: list[QualityIssue] = []

    for path, text in iter_string_values(content):
        if not _path_is_quantitative(path, text):
            continue
        for match in QUANTIFIED_VALUE_RE.finditer(text):
            if not _is_material_metric(path, text, match):
                continue
            claim = _matching_claim(claims, path, match.group("value"))
            if claim is None:
                issues.append(_issue("FACT.METRIC_EVIDENCE_MISSING", path))
                continue
            issues.extend(_validate_claim(claim, text, evidence_by_id, path))

    chart_objects = list(_iter_chart_objects(content))
    for path, chart in chart_objects:
        chart_claim = _matching_path_claim(chart_claims, path)
        if chart_claim is None:
            issues.append(_issue("FACT.CHART_PROVENANCE_MISSING", path))
            continue
        values = _chart_values(chart)
        if not values or any(not math.isfinite(value) for value in values):
            issues.append(_issue("FACT.CHART_VALUES_INVALID", path))
            continue
        categories = chart.get("categories")
        if not isinstance(categories, list) or any(
            not isinstance(label, str) or not label.strip() for label in categories
        ):
            issues.append(_issue("FACT.CHART_DIMENSIONS_INVALID", path))
        for series in chart.get("series", []):
            if not isinstance(series, dict) or len(series.get("values", [])) != len(categories or []):
                issues.append(_issue("FACT.CHART_DOMAIN_MISMATCH", path))
                break
        issues.extend(
            _validate_dataset_claim(chart_claim, chart, values, evidence_by_id, path)
        )

    return _deduplicate_issues(issues)


def materialize_verified_chart_sources(
    content: dict[str, Any],
    evidence: Iterable[EvidenceSourceModel],
) -> None:
    """Attach only resolved, provider-ingested URLs to chart UI content.

    The model supplies a source ID, never a URL. This prevents fabricated URLs
    while retaining a source string in the existing editable chart model.
    """

    evidence_by_id = {source.id: source for source in evidence}
    metadata = content.get("__quality__")
    if not isinstance(metadata, dict):
        return
    chart_claims = metadata.get("charts")
    if not isinstance(chart_claims, list):
        return
    for path, chart in _iter_chart_objects(content):
        claim = _matching_path_claim(chart_claims, path)
        if not isinstance(claim, dict):
            continue
        source = evidence_by_id.get(str(claim.get("source_id") or ""))
        chart["unit"] = str(claim.get("unit") or "").strip()
        chart["provenance"] = str(claim.get("provenance") or "")
        chart["source_id"] = str(claim.get("source_id") or "") or None
        if source and source.url and source.provenance == claim.get("provenance"):
            chart["source"] = source.url


def outline_has_supported_quantitative_content(
    content: str,
    evidence: Iterable[EvidenceSourceModel],
) -> bool:
    matches = list(QUANTIFIED_VALUE_RE.finditer(content or ""))
    if not matches:
        return False
    if ILLUSTRATIVE_RE.search(content or ""):
        return True
    source_texts = [source.snippet or "" for source in evidence]
    for match in matches:
        token = _numeric_token(match.group("value"))
        if token and any(_text_contains_numeric(source_text, token) for source_text in source_texts):
            return True
    return False


def _validate_claim(
    claim: dict[str, Any],
    visible_text: str,
    evidence_by_id: dict[str, EvidenceSourceModel],
    path: str,
) -> list[QualityIssue]:
    unit = str(claim.get("unit") or "").strip()
    label = str(claim.get("label") or "").strip()
    if not unit:
        return [_issue("FACT.METRIC_UNIT_MISSING", path)]
    provenance = claim.get("provenance")
    if provenance == "illustrative":
        if not ILLUSTRATIVE_RE.search(f"{visible_text} {label}"):
            return [_issue("FACT.ILLUSTRATIVE_LABEL_MISSING", path)]
        return []
    source = evidence_by_id.get(str(claim.get("source_id") or ""))
    if source is None or source.provenance != provenance:
        return [_issue("FACT.METRIC_SOURCE_INVALID", path)]
    if provenance == "web_search" and not source.url:
        return [_issue("FACT.METRIC_SOURCE_URL_MISSING", path)]
    value = _numeric_token(claim.get("value"))
    if not value or not _text_contains_numeric(source.snippet or "", value):
        return [_issue("FACT.METRIC_NOT_SUPPORTED_BY_SOURCE", path)]
    return []


def _validate_dataset_claim(
    claim: dict[str, Any],
    chart: dict[str, Any],
    values: list[float],
    evidence_by_id: dict[str, EvidenceSourceModel],
    path: str,
) -> list[QualityIssue]:
    if not str(claim.get("unit") or "").strip():
        return [_issue("FACT.CHART_UNIT_MISSING", path)]
    provenance = claim.get("provenance")
    if provenance == "illustrative":
        visible_label = f"{chart.get('title') or ''} {claim.get('label') or ''}"
        if not ILLUSTRATIVE_RE.search(visible_label):
            return [_issue("FACT.CHART_ILLUSTRATIVE_LABEL_MISSING", path)]
        return []
    source = evidence_by_id.get(str(claim.get("source_id") or ""))
    if source is None or source.provenance != provenance:
        return [_issue("FACT.CHART_SOURCE_INVALID", path)]
    if provenance == "web_search" and not source.url:
        return [_issue("FACT.CHART_SOURCE_URL_MISSING", path)]
    unsupported = [
        value
        for value in values
        if not _text_contains_numeric(source.snippet or "", _numeric_token(value))
    ]
    if unsupported:
        return [_issue("FACT.CHART_VALUES_NOT_SUPPORTED_BY_SOURCE", path)]
    return []


def _path_is_quantitative(path: str, text: str) -> bool:
    return bool(METRIC_NAME_RE.search(path) or re.search(r"(?:%|[$€£¥]|\b\d+(?:\.\d+)?\s*[x×]\b|\b(?:million|billion|cagr)\b)", text, re.IGNORECASE))


def _is_material_metric(path: str, text: str, match: re.Match[str]) -> bool:
    if match.group("currency") or match.group("unit"):
        return True
    return bool(METRIC_NAME_RE.search(path))


def _matching_claim(claims: list[Any], path: str, value: str) -> dict[str, Any] | None:
    numeric = _numeric_token(value)
    for claim in claims:
        if not isinstance(claim, dict) or str(claim.get("path")) != path:
            continue
        if _numeric_token(claim.get("value")) == numeric:
            return claim
    return None


def _matching_path_claim(claims: list[Any], path: str) -> dict[str, Any] | None:
    return next(
        (
            claim
            for claim in claims
            if isinstance(claim, dict) and str(claim.get("path")) == path
        ),
        None,
    )


def _iter_chart_objects(value: Any, path: str = ""):
    if isinstance(value, dict):
        if {"chart_type", "categories", "series"}.issubset(value):
            yield path, value
            return
        for key, nested in value.items():
            if key in {"__quality__", "__speaker_note__"}:
                continue
            nested_path = f"{path}.{key}" if path else str(key)
            yield from _iter_chart_objects(nested, nested_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_path = f"{path}.{index}" if path else str(index)
            yield from _iter_chart_objects(nested, nested_path)


def _chart_values(chart: dict[str, Any]) -> list[float]:
    values: list[float] = []
    series = chart.get("series")
    if not isinstance(series, list):
        return values
    for item in series:
        if not isinstance(item, dict) or not isinstance(item.get("values"), list):
            continue
        values.extend(float(value) for value in item["values"] if isinstance(value, (int, float)))
    return values


def _numeric_token(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):g}"
    raw = str(value or "").strip().replace(",", "")
    try:
        return f"{float(raw):g}"
    except ValueError:
        return ""


def _text_contains_numeric(text: str, token: str) -> bool:
    if not token:
        return False
    for match in QUANTIFIED_VALUE_RE.finditer(text or ""):
        if _numeric_token(match.group("value")) == token:
            return True
    return False


def _issue(rule_id: str, path: str) -> QualityIssue:
    return QualityIssue(
        rule_id=rule_id,
        severity=QualitySeverity.ERROR,
        action=QualityAction.RESELECT_LAYOUT,
        path=path,
    )


def _deduplicate_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, str | None]] = set()
    result: list[QualityIssue] = []
    for issue in issues:
        key = (issue.rule_id, issue.path)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result

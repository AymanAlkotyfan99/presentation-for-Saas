from __future__ import annotations

import logging
from typing import Any

from models.presentation_outline_model import SlideOutlineModel

from .contracts import (
    PresentationQualityError,
    QualityAction,
    QualityIssue,
    QualityResult,
    QualitySeverity,
    RepairBudget,
)
from .facts import fact_issues, materialize_verified_chart_sources
from .text import language_issues, normalize_content_strings, text_contract_issues
from .visual import final_ui_issues


LOGGER = logging.getLogger(__name__)


def finalize_generated_slide_content(
    content: dict[str, Any],
    *,
    outline: SlideOutlineModel,
    language: str | None,
    presentation_id: str | None = None,
    slide_id: str | None = None,
    repair_budget: RepairBudget | None = None,
) -> QualityResult:
    normalized, fixes = normalize_content_strings(content)
    budget = repair_budget or RepairBudget()
    accepted_fixes: list[QualityIssue] = []
    budget_exhausted = False
    for issue in fixes:
        if budget.use_auto_fix():
            accepted_fixes.append(issue)
        else:
            budget_exhausted = True
            break
    issues: list[QualityIssue] = [
        *accepted_fixes,
        *text_contract_issues(normalized),
        *language_issues(normalized, language),
        *fact_issues(normalized, outline.evidence),
    ]
    if budget_exhausted:
        issues.append(
            QualityIssue(
                rule_id="REPAIR.PRESENTATION_BUDGET_EXHAUSTED",
                severity=QualitySeverity.FATAL,
                action=QualityAction.BLOCK_PRESENTATION,
            )
        )
    result = QualityResult(value=normalized, issues=issues)
    _log_issues(result.blocking_issues, presentation_id, slide_id)
    if result.blocking_issues:
        raise PresentationQualityError(result.blocking_issues)
    materialize_verified_chart_sources(normalized, outline.evidence)
    return result


def validate_final_slide_ui(
    ui: dict[str, Any] | None,
    *,
    presentation_id: str | None = None,
    slide_id: str | None = None,
) -> QualityResult:
    issues = final_ui_issues(ui)
    result = QualityResult(value=ui, issues=issues)
    _log_issues(result.blocking_issues, presentation_id, slide_id)
    if result.blocking_issues:
        raise PresentationQualityError(result.blocking_issues)
    return result


def validate_final_presentation(
    slides: list[Any],
    *,
    expected_slide_count: int,
    presentation_id: str | None = None,
) -> QualityResult:
    issues: list[QualityIssue] = []
    if len(slides) != expected_slide_count:
        issues.append(
            QualityIssue(
                rule_id="STRUCTURE.WRONG_SLIDE_COUNT",
                severity=QualitySeverity.FATAL,
                action=QualityAction.BLOCK_PRESENTATION,
                details={"expected": expected_slide_count, "actual": len(slides)},
            )
        )
    indexes = [getattr(slide, "index", None) for slide in slides]
    if indexes != list(range(len(slides))):
        issues.append(
            QualityIssue(
                rule_id="STRUCTURE.NONCONTIGUOUS_SLIDE_ORDER",
                severity=QualitySeverity.FATAL,
                action=QualityAction.BLOCK_PRESENTATION,
            )
        )
    ids = [str(getattr(slide, "id", "")) for slide in slides]
    if len(ids) != len(set(ids)):
        issues.append(
            QualityIssue(
                rule_id="STRUCTURE.DUPLICATE_SLIDE_ID",
                severity=QualitySeverity.FATAL,
                action=QualityAction.BLOCK_PRESENTATION,
            )
        )
    for slide in slides:
        issues.extend(final_ui_issues(getattr(slide, "ui", None)))

    result = QualityResult(value=slides, issues=issues)
    _log_issues(result.blocking_issues, presentation_id, None)
    if result.blocking_issues:
        raise PresentationQualityError(result.blocking_issues)
    return result


def _log_issues(
    issues: list[QualityIssue],
    presentation_id: str | None,
    slide_id: str | None,
) -> None:
    for issue in issues:
        LOGGER.warning(
            "quality_gate_failed presentation_id=%s slide_id=%s rule_id=%s "
            "severity=%s repair_action=%s path=%s",
            presentation_id or "unbound",
            slide_id or "unbound",
            issue.rule_id,
            issue.severity.value,
            issue.action.value,
            issue.path or "",
        )

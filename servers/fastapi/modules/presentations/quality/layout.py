from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from models.presentation_layout import PresentationLayoutModel, SlideLayoutModel
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from models.presentation_structure_model import PresentationStructureModel

from .bindings import is_protected_metadata_field
from .contracts import RepairBudget
from .facts import outline_has_supported_quantitative_content


LOGGER = logging.getLogger(__name__)
METRIC_FIELD_RE = re.compile(
    r"(?:^|_)(?:metric|kpi|stat|price|percentage|percent|cagr|rate|revenue|cost)(?:_|$)",
    re.IGNORECASE,
)
COMPARISON_RE = re.compile(r"\b(?:versus|vs\.?|compare|comparison|difference|pros? and cons?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LayoutRequirements:
    chart: bool = False
    metrics: bool = False
    protected_metadata: bool = False
    comparison: bool = False


def layout_requirements(layout: SlideLayoutModel) -> LayoutRequirements:
    chart = False
    metrics = False
    protected = False
    comparison = bool(
        re.search(r"compar", f"{layout.id} {layout.name or ''} {layout.description or ''}", re.IGNORECASE)
    )

    def walk(value: Any, name: str = "") -> None:
        nonlocal chart, metrics, protected
        if is_protected_metadata_field(name):
            protected = True
        if METRIC_FIELD_RE.search(name):
            metrics = True
        if not isinstance(value, dict):
            if isinstance(value, list):
                for nested in value:
                    walk(nested, name)
            return
        if value.get("x-element-type") == "chart" or (
            value.get("type") == "object"
            and {"chart_type", "categories", "series"}.issubset(
                (value.get("properties") or {}).keys()
            )
        ):
            chart = True
        for key, nested in value.items():
            walk(nested, key if key not in {"properties", "items"} else name)
        properties = value.get("properties")
        if isinstance(properties, dict):
            for key, nested in properties.items():
                walk(nested, key)

    walk(layout.json_schema)
    return LayoutRequirements(chart, metrics, protected, comparison)


def is_layout_compatible(
    layout: SlideLayoutModel,
    outline: SlideOutlineModel,
    *,
    protected_metadata_available: bool = False,
) -> bool:
    requirements = layout_requirements(layout)
    quantitative = outline_has_supported_quantitative_content(
        outline.content,
        outline.evidence,
    )
    if (requirements.chart or requirements.metrics) and not quantitative:
        return False
    if requirements.protected_metadata and not protected_metadata_available:
        return False
    if requirements.comparison and not COMPARISON_RE.search(outline.content):
        return False
    return True


def repair_structure_for_content(
    structure: PresentationStructureModel,
    outlines: PresentationOutlineModel,
    layout: PresentationLayoutModel,
    *,
    protected_metadata_available: bool = False,
    budget: RepairBudget | None = None,
    presentation_id: str | None = None,
) -> PresentationStructureModel:
    if not layout.slides:
        raise ValueError("presentation layout has no slides")
    repair_budget = budget or RepairBudget()
    selected = list(structure.slides[: len(outlines.slides)])
    while len(selected) < len(outlines.slides):
        selected.append(-1)

    for slide_index, outline in enumerate(outlines.slides):
        current = selected[slide_index]
        if 0 <= current < len(layout.slides) and is_layout_compatible(
            layout.slides[current],
            outline,
            protected_metadata_available=protected_metadata_available,
        ):
            continue
        candidates = [
            index
            for index, candidate in enumerate(layout.slides)
            if is_layout_compatible(
                candidate,
                outline,
                protected_metadata_available=protected_metadata_available,
            )
        ]
        if not candidates:
            raise ValueError(f"no compatible layout for slide {slide_index + 1}")
        if not repair_budget.use_layout_reselection():
            raise ValueError("presentation layout repair budget exhausted")
        replacement = _choose_candidate(candidates, layout, slide_index)
        LOGGER.info(
            "quality_gate_repaired presentation_id=%s slide_index=%s "
            "rule_id=LAYOUT.INCOMPATIBLE action=RESELECT_LAYOUT from_index=%s to_index=%s",
            presentation_id or "unbound",
            slide_index,
            current,
            replacement,
        )
        selected[slide_index] = replacement
    return PresentationStructureModel(slides=selected)


def reselect_layout_after_quality_failure(
    layout: PresentationLayoutModel,
    outline: SlideOutlineModel,
    *,
    current_index: int,
    slide_index: int,
    rule_ids: set[str],
    protected_metadata_available: bool = False,
    budget: RepairBudget,
    presentation_id: str | None = None,
) -> int | None:
    """Choose one deterministic recovery layout for a failed generated slide.

    This is deliberately a single-shot reservation.  The caller may regenerate
    the slide content once with the returned layout, but must not loop if that
    second result also fails the quality contract.
    """

    fact_failure = any(rule_id.startswith("FACT.") for rule_id in rule_ids)
    visual_failure = any(rule_id.startswith("VISUAL.") for rule_id in rule_ids)
    if not fact_failure and not visual_failure:
        return None

    candidates: list[int] = []
    for index, candidate in enumerate(layout.slides):
        if index == current_index:
            continue
        requirements = layout_requirements(candidate)
        if fact_failure and (requirements.chart or requirements.metrics):
            continue
        if not is_layout_compatible(
            candidate,
            outline,
            protected_metadata_available=protected_metadata_available,
        ):
            continue
        candidates.append(index)
    if not candidates or not budget.reserve_layout_regeneration():
        return None

    replacement = _choose_candidate(candidates, layout, slide_index)
    LOGGER.info(
        "quality_gate_repaired presentation_id=%s slide_index=%s "
        "rule_id=%s action=RESELECT_LAYOUT from_index=%s to_index=%s",
        presentation_id or "unbound",
        slide_index,
        ",".join(sorted(rule_ids)),
        current_index,
        replacement,
    )
    return replacement


def _choose_candidate(
    candidates: list[int],
    layout: PresentationLayoutModel,
    slide_index: int,
) -> int:
    if slide_index == 0:
        cover_candidates = [
            index
            for index in candidates
            if re.search(
                r"\b(?:title|cover|opening|intro)\b",
                f"{layout.slides[index].id} {layout.slides[index].name or ''} {layout.slides[index].description or ''}",
                re.IGNORECASE,
            )
        ]
        if cover_candidates:
            return cover_candidates[0]
    return candidates[slide_index % len(candidates)]

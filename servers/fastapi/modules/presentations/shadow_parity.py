"""Privacy-safe structural parity for the controlled canonical shadow path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from modules.presentations.adapters.editor_v2 import canonical_to_v2_editor
from modules.presentations.domain.document import PresentationDocument
from modules.presentations.migrations.legacy_document import convert_legacy_presentation
from modules.presentations.observability import count_bucket, record_canonical_metric, size_bucket


@dataclass(frozen=True, slots=True)
class ShadowParityResult:
    status: str
    legacy_slide_count: int
    canonical_slide_count: int
    legacy_element_count: int
    canonical_element_count: int
    supported_categories: tuple[str, ...]
    unsupported_categories: tuple[str, ...]


def _signature(editor_slides: list[dict[str, Any]]) -> tuple[int, int, tuple[str, ...]]:
    count = 0
    categories: set[str] = set()
    stack: list[Any] = []
    for slide in editor_slides:
        stack.extend(slide.get("elements", []))
        for component in slide.get("components", []):
            if isinstance(component, dict):
                stack.extend(component.get("elements", []))
    while stack:
        element = stack.pop()
        if not isinstance(element, dict):
            continue
        count += 1
        categories.add(str(element.get("type") or "unknown")[:32])
        children = element.get("children")
        if isinstance(children, list):
            stack.extend(children)
    return len(editor_slides), count, tuple(sorted(categories))


def compare_shadow_parity(
    presentation: PresentationModel,
    slides: list[SlideModel],
    document: PresentationDocument,
) -> ShadowParityResult:
    converted = convert_legacy_presentation(presentation, slides)
    legacy_editor = canonical_to_v2_editor(converted.document)
    canonical_editor = canonical_to_v2_editor(document)
    legacy_slide_count, legacy_elements, legacy_categories = _signature(legacy_editor)
    canonical_slide_count, canonical_elements, canonical_categories = _signature(canonical_editor)
    unsupported = tuple(sorted(set(converted.unsupported_features)))
    if unsupported:
        status = "unsupported"
    elif (legacy_slide_count, legacy_elements, legacy_categories) == (
        canonical_slide_count, canonical_elements, canonical_categories,
    ):
        status = "match"
    else:
        status = "structural-difference"
    result = ShadowParityResult(
        status=status,
        legacy_slide_count=legacy_slide_count,
        canonical_slide_count=canonical_slide_count,
        legacy_element_count=legacy_elements,
        canonical_element_count=canonical_elements,
        supported_categories=canonical_categories,
        unsupported_categories=unsupported,
    )
    document_bytes = len(json.dumps(document.model_dump(mode="json", by_alias=True), separators=(",", ":")).encode("utf-8"))
    record_canonical_metric(
        "shadow_parity",
        schema_version=document.schema_version,
        parity_status=status,
        document_size_bucket=size_bucket(document_bytes),
        slide_count_bucket=count_bucket(canonical_slide_count),
        element_count_bucket=count_bucket(canonical_elements),
        supported_categories=list(canonical_categories),
        unsupported_categories=list(unsupported),
    )
    return result

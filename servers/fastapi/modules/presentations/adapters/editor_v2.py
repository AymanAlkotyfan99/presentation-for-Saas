"""Pure compatibility transformations between canonical and current V2 UI data."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel
from modules.presentations.domain.document import PresentationDocument
from modules.presentations.migrations.legacy_document import convert_legacy_presentation


def _element_to_v2(element: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(element.id),
        "type": element.type,
        "position": {"x": element.geometry.x, "y": element.geometry.y},
        "size": {"width": element.geometry.width, "height": element.geometry.height},
        "rotation": element.transform.rotation if element.transform else 0,
    }
    if element.style:
        if element.style.fill:
            result["fill"] = {"color": element.style.fill}
        if element.style.opacity is not None:
            result["opacity"] = element.style.opacity
    if element.type == "text":
        result["runs"] = [
            {"text": run.text, "font": {"family": run.font_family_ref, "size": run.font_size, "color": run.color}}
            for paragraph in element.paragraphs for run in paragraph.runs
        ]
    elif element.type == "image":
        result.update({"data": f"asset:{element.asset_id}", "fit": element.fit})
    elif element.type == "shape":
        result["shape"] = element.shape_kind
    elif element.type in {"line", "arrow", "vector"}:
        result["points"] = [point.model_dump() for point in element.points]
        if element.type == "vector":
            result["closed"] = element.closed
    elif element.type == "icon":
        result.update({"is_icon": True, "data": f"asset:{element.asset_id}" if element.asset_id else None, "name": element.icon_name})
    elif element.type == "table":
        result["rows"] = [
            [{"runs": [run.model_dump(mode="json", exclude_none=True) for paragraph in cell.paragraphs for run in paragraph.runs]} for cell in row.cells]
            for row in element.rows
        ]
    elif element.type == "chart":
        result.update({"chart_type": element.chart_type.replace("-", "_"), "series": [series.model_dump(mode="json", exclude_none=True) for series in element.series]})
    elif element.type in {"container", "group"}:
        result["children"] = [_element_to_v2(child) for child in element.children]
    return {key: value for key, value in result.items() if value is not None}


def canonical_to_v2_editor(document: PresentationDocument) -> list[dict[str, Any]]:
    return [
        {
            "id": str(slide.id),
            "background": slide.background.color if slide.background and slide.background.color else "#FFFFFF",
            "components": [],
            "elements": [_element_to_v2(element) for element in slide.elements],
        }
        for slide in sorted(document.slides, key=lambda value: value.order)
    ]


def v2_editor_to_canonical(
    *, presentation_id: UUID, title: str, language: str, slides: list[dict[str, Any]]
) -> PresentationDocument:
    presentation = PresentationModel(
        id=presentation_id, version=PresentationVersion.V2_STANDARD,
        content=title, n_slides=len(slides), language=language, title=title,
    )
    legacy_slides = [
        SlideModel(
            id=UUID(slide["id"]) if isinstance(slide.get("id"), str) else UUID(int=index + 1),
            presentation=presentation_id, layout_group="canonical", layout="free",
            index=index, content={}, ui=slide,
        )
        for index, slide in enumerate(slides)
    ]
    return convert_legacy_presentation(presentation, legacy_slides).document

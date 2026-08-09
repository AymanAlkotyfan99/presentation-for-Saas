"""Deterministic, non-destructive legacy-to-canonical conversion."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from models.sql.presentation import PresentationModel
from models.sql.presentation_document import CanonicalConversionStatus
from models.sql.slide import SlideModel
from modules.presentations.domain import canonical_checksum, validate_presentation_document
from modules.presentations.domain.document import PresentationDocument


MAX_LEGACY_STRING = 100_000
HTML_TAG = re.compile(r"<[^>]{1,2048}>")
SAFE_REFERENCE = re.compile(r"[^A-Za-z0-9._:-]+")
SUPPORTED_IMAGES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}


@dataclass(slots=True)
class ConversionPreview:
    document: PresentationDocument
    status: CanonicalConversionStatus
    warnings: list[str]
    unsupported_features: list[str]
    asset_mappings: dict[str, str]

    @property
    def checksum(self) -> str:
        return canonical_checksum(self.document)

    def safe_asset_summary(self) -> list[dict[str, str | bool]]:
        assets = {str(asset.asset_id): asset for asset in self.document.assets}
        return [
            {
                "assetId": asset_id,
                "sourceType": assets[asset_id].source_type,
                "resolved": True,
            }
            for asset_id in sorted(self.asset_mappings)
            if asset_id in assets
        ]


def _stable(namespace: UUID, path: str) -> str:
    return str(uuid5(namespace, path))


def _safe_reference(value: Any, fallback: str) -> str:
    candidate = SAFE_REFERENCE.sub("-", str(value or "").strip()).strip("-")[:128]
    return candidate if candidate and candidate[0].isalnum() else fallback


def _plain_text(value: Any, maximum: int = MAX_LEGACY_STRING) -> str:
    text = html.unescape(str(value or ""))[:maximum]
    return HTML_TAG.sub("", text).replace("\x00", "").strip()


def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return min(max(float(value), minimum), maximum)
    return default


def _color(value: Any, default: str = "#111827") -> str:
    if isinstance(value, str):
        candidate = value.strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", candidate):
            return candidate.upper()
        if re.fullmatch(r"#[0-9A-Fa-f]{3}", candidate):
            return "#" + "".join(character * 2 for character in candidate[1:]).upper()
    return default


def _geometry(raw: dict[str, Any], offset_x: float = 0, offset_y: float = 0) -> dict[str, Any]:
    position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
    size = raw.get("size") if isinstance(raw.get("size"), dict) else {}
    return {
        "x": _number(position.get("x"), 0, -5120, 5120) + offset_x,
        "y": _number(position.get("y"), 0, -2880, 2880) + offset_y,
        "width": _number(size.get("width"), 320, 1, 5120),
        "height": _number(size.get("height"), 180, 1, 2880),
        "anchor": "top-start",
    }


def _style(raw: dict[str, Any]) -> dict[str, Any] | None:
    result: dict[str, Any] = {}
    fill = raw.get("fill")
    if isinstance(fill, dict) and fill.get("color"):
        result["fill"] = _color(fill.get("color"), "#FFFFFF")
    if isinstance(raw.get("opacity"), (int, float)):
        result["opacity"] = _number(raw.get("opacity"), 1, 0, 1)
    stroke = raw.get("stroke")
    if isinstance(stroke, dict) and stroke.get("color"):
        result["stroke"] = {
            "color": _color(stroke.get("color")),
            "width": _number(stroke.get("width"), 1, 0, 100),
        }
    return result or None


class _Converter:
    def __init__(self, presentation: PresentationModel):
        self.presentation = presentation
        self.namespace = uuid5(NAMESPACE_URL, f"bayanly:canonical:{presentation.id}")
        self.warnings: set[str] = set()
        self.unsupported: set[str] = set()
        self.assets: dict[str, dict[str, Any]] = {}
        self.asset_mappings: dict[str, str] = {}

    def stable(self, path: str) -> str:
        return _stable(self.namespace, path)

    def register_asset(self, raw_path: Any, path: str, role: str = "content", kind: str = "image") -> str | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        raw_path = raw_path.strip()[:4096]
        try:
            existing = str(UUID(raw_path))
        except ValueError:
            existing = ""
        if existing:
            self.assets.setdefault(existing, {
                "assetId": existing,
                "kind": kind,
                "mimeType": "image/png",
                "sourceType": "legacy",
                "role": role,
            })
            return existing
        suffix = PurePath(raw_path.split("?", 1)[0]).suffix.lower()
        mime_type = SUPPORTED_IMAGES.get(suffix)
        if not mime_type:
            self.warnings.add("legacy-asset-type-unsupported")
            return None
        asset_id = self.stable(f"asset:{path}:{raw_path}")
        self.assets.setdefault(asset_id, {
            "assetId": asset_id,
            "kind": kind,
            "mimeType": mime_type,
            "sourceType": "legacy",
            "role": role,
        })
        self.asset_mappings[asset_id] = raw_path
        return asset_id

    def text_run(self, raw: Any, path: str, language: str) -> dict[str, Any]:
        source = raw if isinstance(raw, dict) else {"text": raw}
        text = _plain_text(source.get("text"))
        font = source.get("font") if isinstance(source.get("font"), dict) else {}
        result: dict[str, Any] = {
            "id": self.stable(f"{path}:run"),
            "text": text,
            "language": language,
        }
        if font.get("family"):
            result["fontFamilyRef"] = _safe_reference(font["family"], "body")
        if isinstance(font.get("size"), (int, float)):
            result["fontSize"] = _number(font["size"], 32, 1, 512)
        if font.get("color"):
            result["color"] = _color(font["color"])
        if font.get("bold"):
            result["fontWeight"] = 700
        if font.get("italic"):
            result["fontStyle"] = "italic"
        decorations = []
        if font.get("underline"):
            decorations.append("underline")
        if font.get("strikethrough") or font.get("line_through"):
            decorations.append("line-through")
        if decorations:
            result["decorations"] = decorations
        return result

    def paragraph(self, runs: list[Any], path: str, language: str, direction: str) -> dict[str, Any]:
        normalized = [self.text_run(run, f"{path}:{index}", language) for index, run in enumerate(runs)]
        if not normalized:
            normalized = [self.text_run("", f"{path}:0", language)]
        return {
            "id": self.stable(f"{path}:paragraph"),
            "direction": direction,
            "logicalAlignment": "start",
            "runs": normalized,
        }

    def element(self, raw: Any, path: str, z_order: int, offset_x: float = 0, offset_y: float = 0) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            self.unsupported.add("non-object-element")
            return None
        element_type = str(raw.get("type") or "").lower().replace("_", "-")
        language = "ar" if str(self.presentation.language).lower().startswith("ar") else "en"
        direction = "rtl" if language == "ar" else "ltr"
        base: dict[str, Any] = {
            "id": self.stable(f"{path}:element"),
            "geometry": _geometry(raw, offset_x, offset_y),
            "zOrder": z_order,
            "compatibility": {"source": "v1" if self.presentation.version.value == "v1-standard" else "v2"},
        }
        style = _style(raw)
        if style:
            base["style"] = style
        rotation = raw.get("rotation")
        if isinstance(rotation, (int, float)):
            base["transform"] = {"rotation": _number(rotation, 0, -360, 360)}

        if element_type in {"text", "text-list", "bullets"}:
            paragraphs = []
            if element_type == "text":
                runs = raw.get("runs") if isinstance(raw.get("runs"), list) else [{"text": raw.get("text") or raw.get("content") or ""}]
                paragraphs.append(self.paragraph(runs, f"{path}:0", language, direction))
            else:
                items = raw.get("items") if isinstance(raw.get("items"), list) else []
                for index, item in enumerate(items):
                    runs = item if isinstance(item, list) else [{"text": item}]
                    paragraph = self.paragraph(runs, f"{path}:{index}", language, direction)
                    paragraph["list"] = {"kind": "number" if raw.get("marker") == "number" else "bullet", "level": 0}
                    paragraphs.append(paragraph)
            return {**base, "type": "text", "paragraphs": paragraphs or [self.paragraph([], f"{path}:0", language, direction)]}

        if element_type == "image":
            data = raw.get("assetId") or raw.get("asset_id") or raw.get("data") or raw.get("src") or raw.get("path")
            if raw.get("is_icon"):
                icon_name = _safe_reference(raw.get("prompt") or raw.get("name"), "legacy-icon")
                return {**base, "type": "icon", "iconName": icon_name}
            asset_id = self.register_asset(data, path)
            if not asset_id:
                self.unsupported.add("image-without-resolvable-asset")
                return None
            return {**base, "type": "image", "assetId": asset_id, "fit": raw.get("fit") if raw.get("fit") in {"contain", "cover", "fill"} else "cover", "altText": _plain_text(raw.get("alt") or raw.get("prompt"), 2048)}

        if element_type in {"shape", "rectangle", "ellipse"}:
            kind = raw.get("shape") if raw.get("shape") in {"rectangle", "rounded-rectangle", "ellipse", "triangle", "diamond"} else ("ellipse" if element_type == "ellipse" else "rectangle")
            return {**base, "type": "shape", "shapeKind": kind}

        if element_type in {"line", "arrow", "vector"}:
            points = raw.get("points") if isinstance(raw.get("points"), list) else []
            normalized_points = [
                {"x": _number(point.get("x"), 0, -5120, 5120), "y": _number(point.get("y"), 0, -2880, 2880)}
                for point in points if isinstance(point, dict)
            ]
            if len(normalized_points) < 2:
                width = base["geometry"]["width"]
                normalized_points = [{"x": 0, "y": 0}, {"x": width, "y": 0}]
            if element_type == "arrow":
                return {**base, "type": "arrow", "points": normalized_points, "head": "end"}
            if element_type == "line":
                return {**base, "type": "line", "points": normalized_points}
            return {**base, "type": "vector", "points": normalized_points, "closed": bool(raw.get("closed"))}

        if element_type == "table":
            source_rows = raw.get("rows") if isinstance(raw.get("rows"), list) else []
            rows = []
            expected_width = None
            for row_index, row in enumerate(source_rows[:100]):
                cells_source = row if isinstance(row, list) else row.get("cells") if isinstance(row, dict) else []
                if not isinstance(cells_source, list) or not cells_source:
                    continue
                cells = []
                for cell_index, cell in enumerate(cells_source[:50]):
                    cell_source = cell if isinstance(cell, dict) else {"text": cell}
                    runs = cell_source.get("runs") if isinstance(cell_source.get("runs"), list) else [{"text": cell_source.get("text") or cell_source.get("value") or ""}]
                    cells.append({"paragraphs": [self.paragraph(runs, f"{path}:row:{row_index}:cell:{cell_index}", language, direction)]})
                expected_width = expected_width or len(cells)
                if len(cells) != expected_width:
                    self.unsupported.add("irregular-table")
                    return None
                rows.append({"cells": cells})
            if not rows:
                self.unsupported.add("empty-table")
                return None
            return {**base, "type": "table", "rows": rows, "headerRows": 1 if raw.get("header") else 0}

        if element_type == "chart":
            chart_type = str(raw.get("chart_type") or raw.get("chartType") or "bar").replace("_", "-")
            allowed = {"area", "bar", "bubble", "donut", "horizontal-bar", "line", "pie", "polar-area", "radar", "scatter", "stacked-bar"}
            if chart_type not in allowed:
                self.unsupported.add("chart-type-unsupported")
                chart_type = "bar"
            series = []
            source_series = raw.get("series") if isinstance(raw.get("series"), list) else []
            if source_series:
                for index, item in enumerate(source_series[:100]):
                    if not isinstance(item, dict):
                        continue
                    values = [float(value) for value in item.get("values", [])[:5000] if isinstance(value, (int, float))]
                    if values:
                        series.append({"id": self.stable(f"{path}:series:{index}"), "name": _plain_text(item.get("name") or f"Series {index + 1}", 512), "values": values})
            else:
                data = raw.get("data") if isinstance(raw.get("data"), list) else []
                values = [float(item.get("value")) for item in data[:5000] if isinstance(item, dict) and isinstance(item.get("value"), (int, float))]
                if values:
                    series = [{"id": self.stable(f"{path}:series:0"), "name": "Series 1", "values": values}]
            if not series:
                self.unsupported.add("chart-data-unsupported")
                return None
            return {**base, "type": "chart", "chartId": self.stable(f"{path}:chart"), "chartType": chart_type, "series": series, "title": _plain_text(raw.get("title"), 1024)}

        if element_type in {"container", "group"}:
            children_source = raw.get("children") if isinstance(raw.get("children"), list) else ([raw.get("child")] if raw.get("child") else [])
            children = [
                converted for index, child in enumerate(children_source[:500])
                if (converted := self.element(child, f"{path}:child:{index}", index)) is not None
            ]
            if element_type == "group" and not children:
                self.unsupported.add("empty-group")
                return None
            result = {**base, "type": element_type, "children": children}
            if element_type == "container":
                result["layoutIntent"] = "free"
            return result

        if element_type in {"svg", "html", "jsx", "react"}:
            self.unsupported.add(f"raw-{element_type}-unsupported")
        else:
            self.unsupported.add("unknown-element-type")
        return None

    def slide(self, slide: SlideModel, order: int) -> dict[str, Any]:
        ui = slide.ui if isinstance(slide.ui, dict) else {}
        elements: list[dict[str, Any]] = []
        root_elements = ui.get("elements") if isinstance(ui.get("elements"), list) else []
        for index, raw in enumerate(root_elements):
            converted = self.element(raw, f"slide:{slide.id}:root:{index}", len(elements))
            if converted:
                elements.append(converted)
        components = ui.get("components") if isinstance(ui.get("components"), list) else []
        for component_index, component in enumerate(components):
            if not isinstance(component, dict):
                continue
            component_position = component.get("position") if isinstance(component.get("position"), dict) else {}
            offset_x = _number(component_position.get("x"), 0, -5120, 5120)
            offset_y = _number(component_position.get("y"), 0, -2880, 2880)
            component_elements = component.get("elements") if isinstance(component.get("elements"), list) else []
            for index, raw in enumerate(component_elements):
                converted = self.element(raw, f"slide:{slide.id}:component:{component_index}:{index}", len(elements), offset_x, offset_y)
                if converted:
                    elements.append(converted)

        if not elements and isinstance(slide.content, dict):
            values: list[str] = []
            stack = [slide.content]
            while stack and len(values) < 50:
                value = stack.pop()
                if isinstance(value, dict):
                    stack.extend(reversed(list(value.values())[:100]))
                elif isinstance(value, list):
                    stack.extend(reversed(value[:100]))
                elif isinstance(value, (str, int, float)):
                    text = _plain_text(value, 4096)
                    if text:
                        values.append(text)
            if values:
                language = "ar" if str(self.presentation.language).lower().startswith("ar") else "en"
                direction = "rtl" if language == "ar" else "ltr"
                elements.append({
                    "id": self.stable(f"slide:{slide.id}:semantic:element"),
                    "type": "text",
                    "geometry": {"x": 80, "y": 80, "width": 1120, "height": 560, "anchor": "top-start"},
                    "zOrder": 0,
                    "paragraphs": [self.paragraph([{"text": "\n".join(values)}], f"slide:{slide.id}:semantic", language, direction)],
                    "compatibility": {"source": "v1" if self.presentation.version.value == "v1-standard" else "v2"},
                })
                self.warnings.add("semantic-content-fallback")
        if slide.html_content and not elements:
            self.unsupported.add("html-only-slide")
        elif slide.html_content:
            self.warnings.add("legacy-html-ignored")

        locale = "ar" if str(self.presentation.language).lower().startswith("ar") else "en"
        result: dict[str, Any] = {
            "id": self.stable(f"slide:{slide.id}"),
            "order": order,
            "layoutIntent": "template" if slide.layout else "free",
            "elements": elements,
            "locale": locale,
            "direction": "rtl" if locale == "ar" else "ltr",
            "compatibility": {
                "legacySlideId": str(slide.id),
                "legacyLayoutGroup": _plain_text(slide.layout_group, 128),
                "legacyLayout": _plain_text(slide.layout, 128),
                "requiresLegacyRenderer": False,
                "warnings": [],
            },
        }
        background = ui.get("background")
        if isinstance(background, str):
            result["background"] = {"color": _color(background, "#FFFFFF")}
        if slide.speaker_note:
            result["speakerNotes"] = {
                "id": self.stable(f"slide:{slide.id}:notes"),
                "locale": locale,
                "direction": "rtl" if locale == "ar" else "ltr",
                "paragraphs": [self.paragraph([{"text": slide.speaker_note}], f"slide:{slide.id}:notes:0", locale, "rtl" if locale == "ar" else "ltr")],
            }
        return result


def convert_legacy_presentation(
    presentation: PresentationModel,
    slides: list[SlideModel],
) -> ConversionPreview:
    converter = _Converter(presentation)
    custom_layout = "custom" in json.dumps(presentation.layout or {}, ensure_ascii=False).lower()
    if custom_layout:
        converter.unsupported.add("custom-layout-source-unsupported")
    for index, raw_path in enumerate(presentation.file_paths or []):
        converter.register_asset(raw_path, f"presentation:file:{index}", role="content")

    ordered = sorted(slides, key=lambda slide: (slide.index, str(slide.id)))
    canonical_slides = [converter.slide(slide, order) for order, slide in enumerate(ordered)]
    if not canonical_slides:
        canonical_slides = [{
            "id": converter.stable("slide:placeholder"), "order": 0,
            "layoutIntent": "free", "elements": [],
            "compatibility": {"requiresLegacyRenderer": False, "warnings": ["missing-legacy-slides"]},
        }]
        converter.warnings.add("missing-legacy-slides")

    locale = "ar" if str(presentation.language).lower().startswith("ar") else "en"
    font_families = []
    if isinstance(presentation.fonts, dict):
        for family in list(presentation.fonts)[:128]:
            if isinstance(family, str) and family.strip():
                ref = _safe_reference(family, f"font-{len(font_families)}")
                font_families.append({"id": ref, "family": _plain_text(family, 128), "fallbacks": ["Arial", "sans-serif"]})
    if not font_families:
        font_families = [{"id": "body", "family": "Noto Sans Arabic" if locale == "ar" else "Inter", "fallbacks": ["Tahoma", "Arial"] if locale == "ar" else ["Arial", "sans-serif"]}]

    warnings = sorted(converter.warnings)
    unsupported = sorted(converter.unsupported)
    requires_legacy = bool(unsupported)
    payload = {
        "schemaVersion": "1.0.0",
        "documentId": converter.stable("document"),
        "presentationId": str(presentation.id),
        "title": _plain_text(presentation.title or presentation.content or "Untitled presentation", 512) or "Untitled presentation",
        "locale": locale,
        "baseDirection": "rtl" if locale == "ar" else "ltr",
        "aspectRatio": {"width": 16, "height": 9},
        "theme": {"themeRef": "legacy-theme", "colorTokens": [], "defaultBackground": "#FFFFFF"},
        "fontPolicy": {"families": font_families, "defaultBodyRef": font_families[0]["id"], "defaultHeadingRef": font_families[0]["id"], "allowSystemFallback": True},
        "metadata": {"authoringIntent": "imported"},
        "slides": canonical_slides,
        "assets": [converter.assets[key] for key in sorted(converter.assets)],
        "exportHints": {"preferredAspect": "16:9", "editablePreference": "preferred", "includeNotes": any(slide.speaker_note for slide in slides), "rendererFallback": "legacy"},
        "compatibility": {
            "sourceVersion": presentation.version.value,
            "legacyPresentationVersion": presentation.version.value,
            "legacyLayoutRef": _safe_reference((presentation.layout or {}).get("name") if isinstance(presentation.layout, dict) else None, "legacy-layout"),
            "requiresLegacyRenderer": requires_legacy,
            "warnings": warnings,
            "unsupportedFeatures": unsupported,
        },
    }
    document = validate_presentation_document(payload)
    status = CanonicalConversionStatus.NEEDS_REVIEW if unsupported else CanonicalConversionStatus.CONVERTED
    return ConversionPreview(document, status, warnings, unsupported, converter.asset_mappings)

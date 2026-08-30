from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterator

from .bindings import (
    is_page_field,
    is_protected_metadata_field,
    iter_ui_elements,
)
from .contracts import QualityAction, QualityIssue, QualitySeverity
from .text import normalized_similarity_text, semantic_similarity


PLACEHOLDER_ASSET_RE = re.compile(r"(?:^|/)(?:placeholder)(?:\.[a-z0-9]+)?(?:$|[?#])", re.IGNORECASE)
SHORT_IDENTIFIER_RE = re.compile(
    r"^[^\s/]{1,12}(?:[/+&.-][^\s/]{1,12})+$",
    re.UNICODE,
)
TITLE_NAME_RE = re.compile(r"(?:title|headline|heading)", re.IGNORECASE)


def final_ui_issues(ui: dict[str, Any] | None) -> list[QualityIssue]:
    if not isinstance(ui, dict):
        return [_issue("STRUCTURE.SLIDE_UI_MISSING", None, QualityAction.BLOCK_PRESENTATION)]
    issues: list[QualityIssue] = []
    for index, element in enumerate(iter_ui_elements(ui)):
        path = f"ui.elements.{index}"
        name = element.get("name") if isinstance(element.get("name"), str) else ""
        element_type = element.get("type")
        if element_type == "text":
            text = _element_text(element)
            if is_page_field(name):
                if element.get("system_binding") not in {"slide_number", "toc_page"}:
                    issues.append(_issue("METADATA.PAGE_NOT_SYSTEM_BOUND", path))
                system_value = element.get("system_value")
                if not isinstance(system_value, int) or system_value < 1:
                    issues.append(_issue("METADATA.PAGE_VALUE_INVALID", path))
                rendered_numbers = [int(value) for value in re.findall(r"\d+", text)]
                if text and system_value not in rendered_numbers:
                    issues.append(_issue("METADATA.PAGE_DISPLAY_MISMATCH", path))
            if is_protected_metadata_field(name):
                if element.get("system_binding") == "omitted_metadata" and text.strip():
                    issues.append(_issue("METADATA.UNPROVEN_IDENTITY", path))
            if element.get("decorative") is False or element.get("system_binding"):
                issues.extend(_text_fit_issues(element, text, name, path))
        elif element_type == "image" and element.get("decorative") is False:
            if not _has_valid_image_asset(element):
                issues.append(_issue("ASSET.IMAGE_MISSING", path, QualityAction.REGENERATE_SLIDE))
    issues.extend(_duplicate_group_issues(ui))
    return _deduplicate(issues)


def _text_fit_issues(
    element: dict[str, Any],
    text: str,
    name: str,
    path: str,
) -> list[QualityIssue]:
    if not text.strip():
        return []
    font = element.get("font") if isinstance(element.get("font"), dict) else {}
    font_size = _number(font.get("size"), 18.0)
    if is_page_field(name):
        minimum = 8.0
    elif TITLE_NAME_RE.search(name):
        minimum = 18.0
    else:
        minimum = 12.0
    issues: list[QualityIssue] = []
    if font_size < minimum:
        issues.append(_issue("VISUAL.FONT_BELOW_MINIMUM", path, QualityAction.RESELECT_LAYOUT))

    size = element.get("size") if isinstance(element.get("size"), dict) else None
    if not size:
        return issues
    width = _number(size.get("width"), 0.0)
    height = _number(size.get("height"), 0.0)
    if width <= 0 or height <= 0:
        issues.append(_issue("VISUAL.INVALID_TEXT_BOUNDS", path, QualityAction.RESELECT_LAYOUT))
        return issues
    line_height = _number(font.get("line_height", font.get("lineHeight")), 1.15)
    available_lines = max(1, int(height // max(1.0, font_size * line_height)))
    estimated_lines = _estimated_line_count(text, width, font_size)
    if estimated_lines > available_lines:
        issues.append(_issue("VISUAL.TEXT_HEIGHT_OVERFLOW", path, QualityAction.RESELECT_LAYOUT))

    for token in re.findall(r"\S+", text):
        if SHORT_IDENTIFIER_RE.match(token) and _estimated_width(token, font_size) > width:
            issues.append(_issue("VISUAL.SHORT_LABEL_DOES_NOT_FIT", path, QualityAction.RESELECT_LAYOUT))
            break
    return issues


def _estimated_line_count(text: str, width: float, font_size: float) -> int:
    total = 0
    for paragraph in text.splitlines() or [text]:
        words = re.findall(r"\S+|\s+", paragraph)
        if not words:
            total += 1
            continue
        line_width = 0.0
        lines = 1
        for word in words:
            word_width = _estimated_width(word, font_size)
            if not word.isspace() and line_width > 0 and line_width + word_width > width:
                lines += 1
                line_width = word_width
            else:
                line_width += word_width
        total += lines
    return max(1, total)


def _estimated_width(text: str, font_size: float) -> float:
    em = 0.0
    for char in text:
        if char.isspace():
            em += 0.28
            continue
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x0600 <= code <= 0x06FF:
            em += 0.82
        elif unicodedata.category(char).startswith("P"):
            em += 0.36
        elif char.isupper():
            em += 0.62
        else:
            em += 0.52
    return em * font_size


def _duplicate_group_issues(ui: dict[str, Any]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for group_index, group in enumerate(_iter_repeated_groups(ui)):
        children = group.get("children")
        if not isinstance(children, list) or len(children) < 2:
            continue
        blocks = [_text_from_tree(child) for child in children]
        for left in range(len(blocks)):
            if len(normalized_similarity_text(blocks[left])) < 12:
                continue
            for right in range(left + 1, len(blocks)):
                normalized_left = normalized_similarity_text(blocks[left])
                normalized_right = normalized_similarity_text(blocks[right])
                if not normalized_right:
                    continue
                if normalized_left == normalized_right or semantic_similarity(blocks[left], blocks[right]) >= 0.82:
                    issues.append(
                        _issue(
                            "CONSISTENCY.DUPLICATE_SIBLING_CONTENT",
                            f"ui.groups.{group_index}.children.{right}",
                            QualityAction.REGENERATE_FIELD,
                        )
                    )
    return issues


def _iter_repeated_groups(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("type") in {"flex", "grid"} and isinstance(value.get("children"), list):
            yield value
        for nested in value.values():
            yield from _iter_repeated_groups(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_repeated_groups(nested)


def _text_from_tree(value: Any) -> str:
    if isinstance(value, dict):
        pieces = []
        if value.get("type") == "text":
            pieces.append(_element_text(value))
        for nested in value.values():
            pieces.append(_text_from_tree(nested))
        return " ".join(piece for piece in pieces if piece).strip()
    if isinstance(value, list):
        return " ".join(_text_from_tree(item) for item in value).strip()
    return ""


def _element_text(element: dict[str, Any]) -> str:
    runs = element.get("runs")
    if isinstance(runs, list):
        return "".join(
            str(run.get("text") or "") for run in runs if isinstance(run, dict)
        )
    return str(element.get("text") or "")


def _has_valid_image_asset(element: dict[str, Any]) -> bool:
    if element.get("assetId") or element.get("asset_id"):
        return True
    for key in ("data", "url", "image_url", "src", "path"):
        value = element.get(key)
        if isinstance(value, str) and value.strip() and not PLACEHOLDER_ASSET_RE.search(value):
            return True
    return False


def _number(value: Any, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else fallback


def _issue(
    rule_id: str,
    path: str | None,
    action: QualityAction = QualityAction.BLOCK_PRESENTATION,
) -> QualityIssue:
    return QualityIssue(
        rule_id=rule_id,
        severity=QualitySeverity.ERROR,
        action=action,
        path=path,
    )


def _deduplicate(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, str | None]] = set()
    result = []
    for issue in issues:
        key = (issue.rule_id, issue.path)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result

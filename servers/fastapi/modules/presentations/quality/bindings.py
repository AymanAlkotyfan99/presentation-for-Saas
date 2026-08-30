from __future__ import annotations

import copy
import re
from typing import Any, Iterator


PAGE_FIELD_RE = re.compile(
    r"(?:^|_)page_(?:number|marker|label|value|folio)(?:_|$)|"
    r"(?:^|_)slide_(?:number|marker|index|count)(?:_|$)|"
    r"(?:^|_)(?:pagination|folio)(?:_|$)|"
    r"^(?:footer_(?:value|number)|page_marker_text)$",
    re.IGNORECASE,
)
PROTECTED_METADATA_RE = re.compile(
    r"(?:^|_)(?:presenter|author|organization|organisation|company|department)(?:_|$)|"
    r"^(?:date_(?:label|value|metadata)|event_(?:label|name)|presenter_metadata)$",
    re.IGNORECASE,
)
PLAIN_TEXT_FORMAT = "plain_text"


def is_page_field(name: str | None) -> bool:
    return bool(name and PAGE_FIELD_RE.search(_normalize_name(name)))


def is_protected_metadata_field(name: str | None) -> bool:
    return bool(name and PROTECTED_METADATA_RE.search(_normalize_name(name)))


def sanitize_generation_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove application-owned fields from an LLM response schema.

    Page values and identity metadata are derived by Bayanly. Unknown JSON
    Schema extension keys are intentionally retained as explicit field-format
    contracts for provider prompts and local validation.
    """

    sanitized = _sanitize_schema_node(copy.deepcopy(schema), property_name=None)
    return sanitized if isinstance(sanitized, dict) else {}


def _sanitize_schema_node(value: Any, property_name: str | None) -> Any:
    if isinstance(value, list):
        return [_sanitize_schema_node(item, property_name=None) for item in value]
    if not isinstance(value, dict):
        return value

    result = {
        key: _sanitize_schema_node(nested, property_name=None)
        for key, nested in value.items()
        if key not in {"properties", "required"}
    }
    properties = value.get("properties")
    kept_properties: dict[str, Any] = {}
    if isinstance(properties, dict):
        for name, nested in properties.items():
            if is_page_field(name) or is_protected_metadata_field(name):
                continue
            sanitized = _sanitize_schema_node(nested, property_name=name)
            if _empty_object_schema(sanitized):
                continue
            kept_properties[name] = sanitized
        result["properties"] = kept_properties
        required = value.get("required")
        if isinstance(required, list):
            result["required"] = [name for name in required if name in kept_properties]

    schema_type = result.get("type")
    if schema_type == "string":
        result.setdefault("x-bayanly-text-format", PLAIN_TEXT_FORMAT)
        result.setdefault(
            "description",
            "Audience-facing plain text. Do not emit Markdown, HTML, JSON, or template tokens.",
        )
    items = result.get("items")
    if isinstance(items, dict):
        result["items"] = _sanitize_schema_node(items, property_name=property_name)
    for key in ("oneOf", "anyOf", "allOf"):
        if isinstance(result.get(key), list):
            result[key] = [
                _sanitize_schema_node(item, property_name=property_name)
                for item in result[key]
            ]
    return result


def _empty_object_schema(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("type") == "object"
        and isinstance(value.get("properties"), dict)
        and not value["properties"]
    )


def apply_system_bindings(
    ui: dict[str, Any] | None,
    *,
    slide_number: int,
    total_slides: int,
    layout_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(ui, dict):
        return ui
    bound = copy.deepcopy(ui)
    toc_layout = bool(
        layout_id
        and re.search(r"(?:table[_ -]?of[_ -]?contents|\btoc\b)", layout_id, re.IGNORECASE)
    )
    toc_counter = 0
    for element in iter_ui_elements(bound):
        name = element.get("name") if isinstance(element.get("name"), str) else ""
        if is_page_field(name) and element.get("type") == "text":
            number = slide_number
            if toc_layout:
                toc_counter += 1
                number = min(total_slides, slide_number + toc_counter)
            _set_text_value(element, _format_derived_number(_text_value(element), number))
            element["system_binding"] = "toc_page" if toc_layout else "slide_number"
            element["system_value"] = number
            continue
        if is_protected_metadata_field(name) and element.get("type") == "text":
            source_value = (metadata or {}).get(_normalize_name(name))
            if source_value:
                _set_text_value(element, source_value)
                element["system_binding"] = "verified_metadata"
            else:
                _set_text_value(element, "")
                element["system_binding"] = "omitted_metadata"
    return bound


def iter_ui_elements(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for key in ("elements", "children"):
            nested = value.get(key)
            if isinstance(nested, list):
                for child in nested:
                    yield from iter_ui_elements(child)
        child = value.get("child")
        if isinstance(child, dict):
            yield from iter_ui_elements(child)
        components = value.get("components")
        if isinstance(components, list):
            for component in components:
                yield from iter_ui_elements(component)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_ui_elements(nested)


def _text_value(element: dict[str, Any]) -> str:
    runs = element.get("runs")
    if isinstance(runs, list):
        joined = "".join(
            str(run.get("text") or "") for run in runs if isinstance(run, dict)
        )
        if joined:
            return joined
    return str(element.get("text") or "")


def _set_text_value(element: dict[str, Any], value: str) -> None:
    runs = element.get("runs")
    if isinstance(runs, list) and runs:
        first = copy.deepcopy(runs[0]) if isinstance(runs[0], dict) else {}
        first["text"] = value
        element["runs"] = [first]
    else:
        element["runs"] = [{"text": value}]
    element["text"] = value


def _format_derived_number(template_text: str, number: int) -> str:
    template = template_text or ""
    for token in ("{{page}}", "{page}", "{{slide}}", "{slide}"):
        if token in template.lower():
            return re.sub(re.escape(token), str(number), template, flags=re.IGNORECASE)
    match = re.search(r"\d+", template)
    if match:
        raw = match.group(0)
        width = len(raw) if raw.startswith("0") else 0
        replacement = str(number).zfill(width) if width else str(number)
        return f"{template[:match.start()]}{replacement}{template[match.end():]}".strip()
    # A corrupt or non-numeric template seed ("Page AI", "Page ED") must not
    # become semantic metadata. A bare localized-independent number is safe.
    return str(number)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

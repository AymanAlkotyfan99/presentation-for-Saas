"""Bounded semantic validation, normalization, and checksums for canonical documents."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError

from .document import (
    ChartElement,
    ContainerElement,
    GroupElement,
    IconElement,
    ImageElement,
    PresentationDocument,
    TableElement,
    TextRun,
    TextElement,
)


SCHEMA_VERSION = "1.0.0"
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_TOTAL_ELEMENTS = 5_000
MAX_GROUP_DEPTH = 8
MAX_TOTAL_TEXT_CHARS = 2_000_000
MAX_NOTES_CHARS = 50_000
MAX_CHART_POINTS = 5_000
PROTOTYPE_KEYS = {"__proto__", "constructor", "prototype"}
UNSAFE_TEXT = re.compile(
    r"<\s*/?[a-z][^>]*>|javascript\s*:|data\s*:[^\s]+|on[a-z]+\s*=",
    re.IGNORECASE,
)
ABSOLUTE_LOCAL_PATH = re.compile(
    r"(?:^|[\s\"'])(?:[a-z]:[\\/]|file://|/(?:home|users|tmp|var|etc|opt)/)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class CanonicalValidationError(ValueError):
    code: str
    detail: str
    params: dict[str, str | int | float | bool]

    def __init__(self, code: str, detail: str, **params: str | int | float | bool):
        ValueError.__init__(self, detail)
        self.code = code
        self.detail = detail
        self.params = params


def _bounded_raw_scan(payload: Any) -> None:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalValidationError("CANONICAL_JSON_INVALID", "Document is not finite JSON") from exc
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise CanonicalValidationError("CANONICAL_DOCUMENT_TOO_LARGE", "Document exceeds the JSON byte limit", maxBytes=MAX_DOCUMENT_BYTES)

    stack: list[tuple[Any, int]] = [(payload, 0)]
    while stack:
        value, depth = stack.pop()
        if depth > 32:
            raise CanonicalValidationError("CANONICAL_NESTING_EXCESSIVE", "Document nesting is excessive", maxDepth=32)
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in PROTOTYPE_KEYS:
                    raise CanonicalValidationError("CANONICAL_PROTOTYPE_KEY", "Prototype-pollution key is forbidden")
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str) and UNSAFE_TEXT.search(value):
            raise CanonicalValidationError(
                "CANONICAL_EXECUTABLE_CONTENT",
                "Executable, HTML, or data-URL content is forbidden",
            )
        elif isinstance(value, str) and ABSOLUTE_LOCAL_PATH.search(value):
            raise CanonicalValidationError(
                "CANONICAL_LOCAL_PATH_FORBIDDEN",
                "Absolute local paths are forbidden",
            )
        elif isinstance(value, float) and not math.isfinite(value):
            raise CanonicalValidationError("CANONICAL_NONFINITE_NUMBER", "Nonfinite numbers are forbidden")


def _walk_elements(elements: Iterable[Any], depth: int = 1):
    if depth > MAX_GROUP_DEPTH:
        raise CanonicalValidationError("CANONICAL_GROUP_DEPTH_EXCEEDED", "Group nesting exceeds the supported depth", maxDepth=MAX_GROUP_DEPTH)
    for element in elements:
        yield element, depth
        if isinstance(element, (ContainerElement, GroupElement)):
            yield from _walk_elements(element.children, depth + 1)


def _check_external_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CanonicalValidationError("CANONICAL_URL_UNSAFE", "Only credential-free HTTPS references are allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise CanonicalValidationError("CANONICAL_URL_UNSAFE", "Local network references are forbidden")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise CanonicalValidationError("CANONICAL_URL_UNSAFE", "Private and loopback references are forbidden")


def _check_text_run(
    run: TextRun,
    *,
    font_ids: set[str],
    asset_ids: set[UUID],
) -> None:
    if run.font_family_ref and run.font_family_ref not in font_ids:
        raise CanonicalValidationError(
            "CANONICAL_FONT_REFERENCE_INVALID",
            "Text run references an unknown font",
        )
    if not run.hyperlink:
        return
    if run.hyperlink.kind == "external":
        if not run.hyperlink.href or run.hyperlink.asset_id:
            raise CanonicalValidationError(
                "CANONICAL_URL_INVALID",
                "External hyperlinks require only href",
            )
        _check_external_url(run.hyperlink.href)
    elif (
        not run.hyperlink.asset_id
        or run.hyperlink.href
        or run.hyperlink.asset_id not in asset_ids
    ):
        raise CanonicalValidationError(
            "CANONICAL_ASSET_REFERENCE_INVALID",
            "Asset hyperlink is invalid",
        )


def _semantic_validation(document: PresentationDocument) -> None:
    seen: set[UUID] = set()

    def add_id(value: UUID) -> None:
        if value in seen:
            raise CanonicalValidationError("CANONICAL_DUPLICATE_ID", "Document IDs must be unique")
        seen.add(value)

    add_id(document.document_id)
    slide_orders: set[int] = set()
    asset_ids: set[UUID] = set()
    for asset in document.assets:
        add_id(asset.asset_id)
        asset_ids.add(asset.asset_id)
    font_ids = {family.id for family in document.font_policy.families}
    if len(font_ids) != len(document.font_policy.families):
        raise CanonicalValidationError("CANONICAL_DUPLICATE_FONT_REFERENCE", "Font references must be unique")
    if document.font_policy.default_body_ref and document.font_policy.default_body_ref not in font_ids:
        raise CanonicalValidationError("CANONICAL_FONT_REFERENCE_INVALID", "Default body font reference is unknown")
    if document.font_policy.default_heading_ref and document.font_policy.default_heading_ref not in font_ids:
        raise CanonicalValidationError("CANONICAL_FONT_REFERENCE_INVALID", "Default heading font reference is unknown")
    if any(family.asset_id and family.asset_id not in asset_ids for family in document.font_policy.families):
        raise CanonicalValidationError("CANONICAL_ASSET_REFERENCE_INVALID", "Font references an unknown asset")

    total_elements = 0
    total_text = len(document.title)
    for slide in document.slides:
        add_id(slide.id)
        if slide.order in slide_orders:
            raise CanonicalValidationError("CANONICAL_DUPLICATE_SLIDE_ORDER", "Slide orders must be unique")
        slide_orders.add(slide.order)
        if slide.background and slide.background.asset_id and slide.background.asset_id not in asset_ids:
            raise CanonicalValidationError("CANONICAL_ASSET_REFERENCE_INVALID", "Slide background references an unknown asset")
        if slide.speaker_notes:
            add_id(slide.speaker_notes.id)
            note_chars = 0
            for paragraph in slide.speaker_notes.paragraphs:
                add_id(paragraph.id)
                for run in paragraph.runs:
                    add_id(run.id)
                    note_chars += len(run.text)
                    _check_text_run(run, font_ids=font_ids, asset_ids=asset_ids)
            if note_chars > MAX_NOTES_CHARS:
                raise CanonicalValidationError("CANONICAL_NOTES_TOO_LARGE", "Speaker notes exceed the supported size", maxCharacters=MAX_NOTES_CHARS)

        for element, _depth in _walk_elements(slide.elements):
            total_elements += 1
            add_id(element.id)
            if isinstance(element, ImageElement) and element.asset_id not in asset_ids:
                raise CanonicalValidationError("CANONICAL_ASSET_REFERENCE_INVALID", "Image references an unknown asset")
            if isinstance(element, IconElement) and not element.asset_id and not element.icon_name:
                raise CanonicalValidationError("CANONICAL_ICON_REFERENCE_REQUIRED", "Icon requires an asset ID or icon name")
            if isinstance(element, IconElement) and element.asset_id and element.asset_id not in asset_ids:
                raise CanonicalValidationError("CANONICAL_ASSET_REFERENCE_INVALID", "Icon references an unknown asset")
            if isinstance(element, TextElement):
                for paragraph in element.paragraphs:
                    add_id(paragraph.id)
                    for run in paragraph.runs:
                        add_id(run.id)
                        total_text += len(run.text)
                        _check_text_run(run, font_ids=font_ids, asset_ids=asset_ids)
            if isinstance(element, TableElement):
                width = len(element.rows[0].cells)
                if any(len(row.cells) != width for row in element.rows):
                    raise CanonicalValidationError("CANONICAL_TABLE_SHAPE_INVALID", "Table rows must have a consistent cell count")
                for row in element.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            add_id(paragraph.id)
                            for run in paragraph.runs:
                                add_id(run.id)
                                total_text += len(run.text)
                                _check_text_run(
                                    run,
                                    font_ids=font_ids,
                                    asset_ids=asset_ids,
                                )
            if isinstance(element, ChartElement):
                add_id(element.chart_id)
                points = sum(len(series.values) for series in element.series)
                for series in element.series:
                    add_id(series.id)
                if points > MAX_CHART_POINTS:
                    raise CanonicalValidationError("CANONICAL_CHART_TOO_LARGE", "Chart exceeds the point limit", maxPoints=MAX_CHART_POINTS)

    if total_elements > MAX_TOTAL_ELEMENTS:
        raise CanonicalValidationError("CANONICAL_ELEMENTS_EXCESSIVE", "Document exceeds the total element limit", maxElements=MAX_TOTAL_ELEMENTS)
    if total_text > MAX_TOTAL_TEXT_CHARS:
        raise CanonicalValidationError("CANONICAL_TEXT_EXCESSIVE", "Document exceeds the total text limit", maxCharacters=MAX_TOTAL_TEXT_CHARS)
    if slide_orders != set(range(len(document.slides))):
        raise CanonicalValidationError("CANONICAL_SLIDE_ORDER_INVALID", "Slide orders must be contiguous from zero")


def validate_presentation_document(payload: Any) -> PresentationDocument:
    _bounded_raw_scan(payload)

    def normalize_integral_numbers(value: Any) -> Any:
        # JSON Schema treats 1 and 1.0 equivalently for integer fields. Apply
        # that rule before strict Pydantic validation without coercing strings,
        # booleans, or other input types.
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [normalize_integral_numbers(item) for item in value]
        if isinstance(value, Mapping):
            return {
                key: normalize_integral_numbers(item)
                for key, item in value.items()
            }
        return value

    try:
        document = PresentationDocument.model_validate_json(
            json.dumps(
                normalize_integral_numbers(payload),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        raise CanonicalValidationError(
            "CANONICAL_SCHEMA_INVALID",
            "Document does not match Presentation Document v1",
            field=location[:256],
        ) from exc
    _semantic_validation(document)
    return document


def canonical_json(document: PresentationDocument | Mapping[str, Any]) -> str:
    validated = document if isinstance(document, PresentationDocument) else validate_presentation_document(document)
    def normalize_numbers(value: Any) -> Any:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [normalize_numbers(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize_numbers(item) for key, item in value.items()}
        return value

    return json.dumps(
        normalize_numbers(validated.model_dump(mode="json", by_alias=True, exclude_none=True)),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_checksum(document: PresentationDocument | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()

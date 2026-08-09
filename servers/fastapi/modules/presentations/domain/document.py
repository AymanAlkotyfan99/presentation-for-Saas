"""Strict renderer-independent Presentation Document v1 domain types.

The generated JSON Schema is the interchange source of truth. These Pydantic
models provide Python ergonomics and a deliberately strict application
boundary; they have no ORM, FastAPI, editor, renderer, or provider coupling.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CanonicalModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: "".join(
            [value.split("_")[0]]
            + [part[:1].upper() + part[1:] for part in value.split("_")[1:]]
        ),
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


Direction = Literal["ltr", "rtl", "auto"]
Locale = Literal["en", "ar"]
LogicalAlignment = Literal["start", "center", "end", "justify"]
Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")]
StableReference = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
SafeText = Annotated[str, Field(max_length=100_000)]


class Geometry(CanonicalModel):
    x: Annotated[float, Field(ge=-5120, le=5120)]
    y: Annotated[float, Field(ge=-2880, le=2880)]
    width: Annotated[float, Field(gt=0, le=5120)]
    height: Annotated[float, Field(gt=0, le=2880)]
    anchor: Literal[
        "top-start", "top-center", "top-end", "center",
        "bottom-start", "bottom-center", "bottom-end",
    ] | None = None


class Transform(CanonicalModel):
    rotation: Annotated[float, Field(ge=-360, le=360)] | None = None
    flip_horizontal: bool | None = None
    flip_vertical: bool | None = None


class Stroke(CanonicalModel):
    color: Color
    width: Annotated[float, Field(ge=0, le=100)]
    opacity: Annotated[float, Field(ge=0, le=1)] | None = None
    dash: Annotated[list[Annotated[float, Field(ge=0, le=1000)]], Field(max_length=32)] | None = None


class Shadow(CanonicalModel):
    color: Color
    blur: Annotated[float, Field(ge=0, le=500)] | None = None
    offset_x: Annotated[float, Field(ge=-1000, le=1000)] | None = None
    offset_y: Annotated[float, Field(ge=-1000, le=1000)] | None = None
    opacity: Annotated[float, Field(ge=0, le=1)] | None = None


class Style(CanonicalModel):
    opacity: Annotated[float, Field(ge=0, le=1)] | None = None
    fill: Color | None = None
    stroke: Stroke | None = None
    shadow: Shadow | None = None
    corner_radius: Annotated[float, Field(ge=0, le=2000)] | None = None


class Accessibility(CanonicalModel):
    label: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    description: Annotated[str, Field(max_length=2048)] | None = None
    decorative: bool | None = None


class ElementCompatibility(CanonicalModel):
    source: Literal["v1", "v2", "template", "canonical"] | None = None
    legacy_id: Annotated[str, Field(max_length=128)] | None = None
    source_layout_ref: StableReference | None = None
    warnings: Annotated[list[StableReference], Field(max_length=64)] | None = None


class Hyperlink(CanonicalModel):
    kind: Literal["external", "asset"]
    href: Annotated[str, Field(min_length=9, max_length=2048, pattern=r"^https://")] | None = None
    asset_id: UUID | None = None


class TextRun(CanonicalModel):
    id: UUID
    text: SafeText
    language: Annotated[str, Field(min_length=2, max_length=35)] | None = None
    font_family_ref: StableReference | None = None
    font_weight: Annotated[int, Field(ge=100, le=900, multiple_of=100)] | None = None
    font_style: Literal["normal", "italic"] | None = None
    decorations: Annotated[list[Literal["underline", "line-through"]], Field(max_length=2)] | None = None
    font_size: Annotated[float, Field(gt=0, le=512)] | None = None
    color: Color | None = None
    line_height: Annotated[float, Field(ge=0.5, le=10)] | None = None
    letter_spacing: Annotated[float, Field(ge=-100, le=100)] | None = None
    hyperlink: Hyperlink | None = None


class ListIntent(CanonicalModel):
    kind: Literal["bullet", "number"]
    level: Annotated[int, Field(ge=0, le=8)]
    start: Annotated[int, Field(ge=1, le=100_000)] | None = None


class Paragraph(CanonicalModel):
    id: UUID
    direction: Direction
    logical_alignment: LogicalAlignment
    list_intent: ListIntent | None = Field(default=None, alias="list")
    runs: Annotated[list[TextRun], Field(min_length=1, max_length=10_000)]


class Crop(CanonicalModel):
    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]
    width: Annotated[float, Field(gt=0, le=1)]
    height: Annotated[float, Field(gt=0, le=1)]
    focal_x: Annotated[float, Field(ge=0, le=1)] | None = None
    focal_y: Annotated[float, Field(ge=0, le=1)] | None = None


class Point(CanonicalModel):
    x: Annotated[float, Field(ge=-5120, le=5120)]
    y: Annotated[float, Field(ge=-2880, le=2880)]


class ElementBase(CanonicalModel):
    id: UUID
    geometry: Geometry
    transform: Transform | None = None
    style: Style | None = None
    accessibility: Accessibility | None = None
    z_order: Annotated[int, Field(ge=0, le=100_000)]
    locked: bool | None = None
    hidden: bool | None = None
    compatibility: ElementCompatibility | None = None


class TextElement(ElementBase):
    type: Literal["text"]
    paragraphs: Annotated[list[Paragraph], Field(min_length=1, max_length=1000)]
    vertical_alignment: Literal["top", "middle", "bottom"] | None = None
    overflow: Literal["clip", "ellipsis", "shrink"] | None = None


class ImageElement(ElementBase):
    type: Literal["image"]
    asset_id: UUID
    fit: Literal["contain", "cover", "fill"]
    crop: Crop | None = None
    alt_text: Annotated[str, Field(max_length=2048)] | None = None


class ShapeElement(ElementBase):
    type: Literal["shape"]
    shape_kind: Literal["rectangle", "rounded-rectangle", "ellipse", "triangle", "diamond"]


class LineElement(ElementBase):
    type: Literal["line"]
    points: Annotated[list[Point], Field(min_length=2, max_length=1000)]


class ArrowElement(ElementBase):
    type: Literal["arrow"]
    points: Annotated[list[Point], Field(min_length=2, max_length=1000)]
    head: Literal["start", "end", "both"]


class VectorElement(ElementBase):
    type: Literal["vector"]
    points: Annotated[list[Point], Field(min_length=2, max_length=10_000)]
    closed: bool


class IconElement(ElementBase):
    type: Literal["icon"]
    asset_id: UUID | None = None
    icon_name: StableReference | None = None


class TableCell(CanonicalModel):
    paragraphs: Annotated[list[Paragraph], Field(min_length=1, max_length=100)]
    column_span: Annotated[int, Field(ge=1, le=50)] | None = None
    row_span: Annotated[int, Field(ge=1, le=100)] | None = None
    background: Color | None = None


class TableRow(CanonicalModel):
    cells: Annotated[list[TableCell], Field(min_length=1, max_length=50)]


class TableElement(ElementBase):
    type: Literal["table"]
    rows: Annotated[list[TableRow], Field(min_length=1, max_length=100)]
    header_rows: Annotated[int, Field(ge=0, le=100)] | None = None


class ChartSeries(CanonicalModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=512)]
    values: Annotated[list[Annotated[float, Field(ge=-1e12, le=1e12)]], Field(min_length=1, max_length=5000)]
    color: Color | None = None


class ChartElement(ElementBase):
    type: Literal["chart"]
    chart_id: UUID
    chart_type: Literal["area", "bar", "bubble", "donut", "horizontal-bar", "line", "pie", "polar-area", "radar", "scatter", "stacked-bar"]
    category_labels: Annotated[list[Annotated[str, Field(max_length=512)]], Field(max_length=5000)] | None = None
    series: Annotated[list[ChartSeries], Field(min_length=1, max_length=100)]
    title: Annotated[str, Field(max_length=1024)] | None = None


class ContainerElement(ElementBase):
    type: Literal["container"]
    layout_intent: Literal["free", "row", "column", "grid", "stack"]
    children: Annotated[list["Element"], Field(max_length=500)]


class GroupElement(ElementBase):
    type: Literal["group"]
    children: Annotated[list["Element"], Field(min_length=1, max_length=500)]


Element = Annotated[
    Union[
        TextElement, ImageElement, ShapeElement, LineElement, ArrowElement,
        VectorElement, IconElement, TableElement, ChartElement,
        ContainerElement, GroupElement,
    ],
    Field(discriminator="type"),
]


class SpeakerNotes(CanonicalModel):
    id: UUID
    locale: Locale
    direction: Direction
    paragraphs: Annotated[list[Paragraph], Field(max_length=1000)]


class SlideBackground(CanonicalModel):
    color: Color | None = None
    asset_id: UUID | None = None


class SlideCompatibility(CanonicalModel):
    legacy_slide_id: Annotated[str, Field(max_length=128)] | None = None
    legacy_layout_group: Annotated[str, Field(max_length=128)] | None = None
    legacy_layout: Annotated[str, Field(max_length=128)] | None = None
    requires_legacy_renderer: bool | None = None
    warnings: Annotated[list[StableReference], Field(max_length=128)] | None = None


class Slide(CanonicalModel):
    id: UUID
    order: Annotated[int, Field(ge=0, le=199)]
    title: Annotated[str, Field(max_length=512)] | None = None
    semantic_role: Literal["title", "content", "section", "table-of-contents", "closing", "other"] | None = None
    background: SlideBackground | None = None
    layout_intent: Literal["free", "row", "column", "grid", "stack", "template"]
    elements: Annotated[list[Element], Field(max_length=500)]
    speaker_notes: SpeakerNotes | None = None
    locale: Locale | None = None
    direction: Direction | None = None
    transition_hint: Literal["none", "fade", "push"] | None = None
    export_capabilities: Annotated[list[Literal["raster", "pdf", "editable-text", "notes", "requires-fallback"]], Field(max_length=5)] | None = None
    compatibility: SlideCompatibility | None = None


class AssetMetadata(CanonicalModel):
    width: Annotated[int, Field(ge=1, le=100_000)] | None = None
    height: Annotated[int, Field(ge=1, le=100_000)] | None = None
    byte_size: Annotated[int, Field(ge=0, le=2_000_000_000)] | None = None
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    original_name: Annotated[str, Field(max_length=255)] | None = None


class Asset(CanonicalModel):
    asset_id: UUID
    kind: Literal["image", "icon", "font"]
    mime_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif", "font/ttf", "font/otf", "font/woff", "font/woff2"]
    source_type: Literal["uploaded", "generated", "stock", "template", "legacy"]
    role: Literal["content", "background", "logo", "decoration", "icon", "font"]
    metadata: AssetMetadata | None = None


class ThemeToken(CanonicalModel):
    name: StableReference
    value: Color


class Theme(CanonicalModel):
    theme_ref: StableReference
    revision_ref: StableReference | None = None
    color_tokens: Annotated[list[ThemeToken], Field(max_length=128)]
    spacing_scale: Annotated[list[Annotated[float, Field(ge=0, le=1000)]], Field(max_length=64)] | None = None
    default_background: Color | None = None


class FontFamily(CanonicalModel):
    id: StableReference
    family: Annotated[str, Field(min_length=1, max_length=128)]
    fallbacks: Annotated[list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=16)]
    asset_id: UUID | None = None


class FontPolicy(CanonicalModel):
    families: Annotated[list[FontFamily], Field(max_length=128)]
    default_body_ref: StableReference | None = None
    default_heading_ref: StableReference | None = None
    allow_system_fallback: bool


class DocumentMetadata(CanonicalModel):
    description: Annotated[str, Field(max_length=4096)] | None = None
    tags: Annotated[list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=100)] | None = None
    authoring_intent: Literal["generated", "edited", "imported", "template-derived"] | None = None
    source_application_version: Annotated[str, Field(max_length=64)] | None = None


class ExportHints(CanonicalModel):
    preferred_aspect: Literal["16:9", "4:3", "custom"]
    editable_preference: Literal["preferred", "not-required", "raster-ok"] | None = None
    accessibility_title: Annotated[str, Field(max_length=512)] | None = None
    include_notes: bool
    capability_requirements: Annotated[list[Literal["mixed-direction", "custom-fonts", "charts", "tables", "transparency", "speaker-notes"]], Field(max_length=16)] | None = None
    renderer_fallback: Literal["legacy", "raster", "fail"]


class DocumentCompatibility(CanonicalModel):
    source_version: Literal["canonical-v1", "v1-standard", "v2-standard", "template-v2"]
    legacy_presentation_version: Annotated[str, Field(max_length=64)] | None = None
    legacy_layout_ref: Annotated[str, Field(max_length=128)] | None = None
    requires_legacy_renderer: bool
    warnings: Annotated[list[StableReference], Field(max_length=256)]
    unsupported_features: Annotated[list[StableReference], Field(max_length=256)]


class Extension(CanonicalModel):
    namespace: Annotated[str, Field(pattern=r"^[a-z][a-z0-9.-]{2,127}$")]
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]
    value: Annotated[str, Field(max_length=2048)] | Annotated[float, Field(ge=-1e12, le=1e12)] | bool


class AspectRatio(CanonicalModel):
    width: Annotated[float, Field(gt=0, le=100)]
    height: Annotated[float, Field(gt=0, le=100)]


class PresentationDocument(CanonicalModel):
    schema_version: Literal["1.0.0"]
    document_id: UUID
    presentation_id: UUID
    title: Annotated[str, Field(min_length=1, max_length=512)]
    locale: Locale
    base_direction: Direction
    aspect_ratio: AspectRatio
    theme: Theme
    font_policy: FontPolicy
    metadata: DocumentMetadata
    slides: Annotated[list[Slide], Field(min_length=1, max_length=200)]
    assets: Annotated[list[Asset], Field(max_length=2000)]
    export_hints: ExportHints
    compatibility: DocumentCompatibility
    extensions: Annotated[list[Extension], Field(max_length=64)] | None = None


ContainerElement.model_rebuild()
GroupElement.model_rebuild()
PresentationDocument.model_rebuild()

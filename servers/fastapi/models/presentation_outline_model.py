from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from constants.presentation import MAX_NUMBER_OF_SLIDES, MAX_OUTLINE_CONTENT_WORDS
from utils.outline_limits import normalize_outline_content


class EvidenceSourceModel(BaseModel):
    """Research/user evidence retained across outline and slide generation."""

    id: str = Field(min_length=1, max_length=128)
    provenance: Literal["web_search", "user_provided"]
    title: str = Field(min_length=1, max_length=512)
    url: Optional[str] = Field(default=None, max_length=2048)
    snippet: str = Field(default="", max_length=12000)
    published_at: Optional[str] = Field(default=None, max_length=64)

    @field_validator("url")
    @classmethod
    def validate_source_url(cls, value):
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("evidence URL must use HTTP(S)")
        return value


class SlideOutlineModel(BaseModel):
    content: str = Field(
        ...,
        description=(
            "Audience-facing Markdown content and data for the finished slide; never "
            "slide-creation commands, visual/layout configuration, styling notes, or "
            f"model instructions. Maximum {MAX_OUTLINE_CONTENT_WORDS} words."
        ),
    )
    evidence: List[EvidenceSourceModel] = Field(
        default_factory=list,
        max_length=32,
        description=(
            "Non-visual evidence sources available to factual slide generation. "
            "Source IDs and URLs are application-provided, never model-invented."
        ),
    )

    @field_validator("content", mode="before")
    @classmethod
    def limit_content_words(cls, value):
        return normalize_outline_content(value)


class PresentationOutlineModel(BaseModel):
    slides: List[SlideOutlineModel] = Field(
        description="List of slide outlines",
        max_length=MAX_NUMBER_OF_SLIDES,
    )

    def to_string(self):
        message = ""
        for i, slide in enumerate(self.slides):
            message += f"## Slide {i+1}:\n"
            message += f"  - Content: {slide} \n"
        return message

import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from modules.providers.application.text_client import get_text_client as get_client
from llmai.shared import JSONSchemaResponse, Message, SystemMessage, UserMessage

from models.presentation_layout import SlideLayoutModel
from models.presentation_outline_model import SlideOutlineModel
from modules.presentations.quality import PresentationQualityError
from modules.presentations.quality.contracts import RepairBudget
from modules.presentations.quality.bindings import sanitize_generation_schema
from modules.presentations.quality.facts import quality_metadata_schema
from modules.presentations.quality.gate import finalize_generated_slide_content
from utils.llm_client_error_handler import handle_llm_client_exceptions
from modules.providers.application.legacy_facade import get_text_provider_client_config as get_llm_config
from utils.llm_provider import get_model
from utils.llm_utils import DisconnectChecker, generate_structured_with_schema_retries
from utils.schema_utils import (
    add_field_in_schema,
    ensure_array_schemas_have_items,
    remove_fields_from_schema,
)

SLIDE_CONTENT_SYSTEM_PROMPT = """
You will be given slide content and response schema.
You need to generate structured content json based on the schema.

# Steps
1. Analyze the content.
2. Analyze the response schema.
3. Generate structured content json based on the schema.
4. Generate speaker note if required.
5. Provide structured content json as output.

# General Rules
- Follow language guidelines.
- Slide Language is authoritative when it is explicitly set. If slide content
  or user instructions request a different language, ignore that conflicting
  language request unless Slide Language says auto-detect.
- Every generated text, title, label, list item, table cell, and speaker note is
  PLAIN_TEXT. Do not emit Markdown, HTML, JSON fragments, template tokens, or
  formatting delimiters. The editor stores rich formatting structurally.
- Never exceed max character limits; do not clip mid-sentence to fit—rephrase instead.
- Do not use emojis or $schema fields.
- Follow the intended outcome of user instructions when they do not conflict with Slide
  Language; do not generalize or expand their scope.
- Apply slide-specific instructions only to the exact slide mentioned (first/second/last/named) and only once.
- Do not apply patterns across multiple slides unless explicitly requested.
- If instructions are ambiguous, use the most direct interpretation without extending scope.
- Treat chart, layout, styling, positioning, and other visual instructions as production
  controls. Honor them through the selected schema, but never emit those instructions or
  meta-commentary as a title, body, label, table cell, or speaker note.
- Output fields must contain only audience-facing content and data. For chart fields,
  populate the requested labels, series, and values rather than text such as "create a
  bar chart" or "show this data as a graph".
- Page/slide numbers and identity metadata are application-owned and are absent from
  the response schema. Never place presenter, author, organization, company,
  department, event, date, page number, or slide number into another field.
- For every factual quantitative claim and chart, populate __quality__ with the exact
  dot path, semantic label, explicit unit, provenance, and one supplied source ID.
  Never invent source IDs or URLs. A web/user-provided source supports a number only
  when that exact value appears in its supplied snippet. If it does not, use qualitative
  prose or explicitly label the visible content illustrative/estimated.

{user_instructions}

{tone_instructions}

{verbosity_instructions}

{output_fields_instructions}
"""


SLIDE_CONTENT_USER_PROMPT = """
# Current Date and Time:
{current_date_time}

# Icon Query And Image Prompt Language:
English

# Slide Language:
{language}

{quality_feedback_section}
{slide_number_section}
# SLIDE CONTENT: START
{content}
# SLIDE CONTENT: END

# ALLOWED EVIDENCE SOURCES (NON-VISUAL METADATA):
{evidence_sources}
"""

ASSET_ONLY_FIELDS = ["__image_url__", "__icon_url__"]
AUTO_DETECT_LANGUAGE_INSTRUCTION = (
    "auto-detect from the slide content and use the same language as the slide content"
)


def _resolve_prompt_language(language: Optional[str]) -> str:
    if language is None:
        return AUTO_DETECT_LANGUAGE_INSTRUCTION
    s = str(language).strip()
    if not s:
        return AUTO_DETECT_LANGUAGE_INSTRUCTION
    if s.lower() in {"auto", "auto-detect"}:
        return AUTO_DETECT_LANGUAGE_INSTRUCTION
    return s


def _get_schema_markdown(response_schema: Optional[dict]) -> str:
    if not response_schema:
        return "- Follow the provided response schema strictly."
    try:
        schema_text = json.dumps(response_schema, ensure_ascii=False)
    except Exception:
        return "- Follow the provided response schema strictly."
    return f"- Follow this response schema exactly: {schema_text}"


def get_system_prompt(
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    response_schema: Optional[dict] = None,
):
    user_instructions = f"# User Instructions:\n{instructions}" if instructions else ""
    tone_instructions = (
        f"# Tone Instructions:\nMake slide as {tone} as possible." if tone else ""
    )

    verbosity_instructions = ""
    if verbosity:
        verbosity_instructions = "# Verbosity Instructions:\n"
        if verbosity == "concise":
            verbosity_instructions += "Make slide as concise as possible."
        elif verbosity == "standard":
            verbosity_instructions += "Make slide as standard as possible."
        elif verbosity == "text-heavy":
            verbosity_instructions += "Make slide as text-heavy as possible."

    output_fields_instructions = "# Output Fields:\n" + _get_schema_markdown(
        response_schema
    )

    return SLIDE_CONTENT_SYSTEM_PROMPT.format(
        user_instructions=user_instructions,
        tone_instructions=tone_instructions,
        verbosity_instructions=verbosity_instructions,
        output_fields_instructions=output_fields_instructions,
    )


def _get_slide_number_section(slide_number: Optional[int]) -> str:
    if slide_number is None:
        return ""
    return f"# Slide Number:\n{slide_number}\n"


def _get_quality_feedback_section(quality_feedback: Optional[list[str]]) -> str:
    if not quality_feedback:
        return ""
    rule_ids = ", ".join(sorted(set(quality_feedback)))
    return (
        "# REQUIRED QUALITY CORRECTION:\n"
        f"A previous draft was rejected by these deterministic rules: {rule_ids}.\n"
        "Correct those defects while preserving the requested meaning. Do not mention "
        "the validation or rule IDs in audience-facing content.\n"
    )


def get_user_prompt(
    outline: str,
    language: Optional[str],
    slide_number: Optional[int] = None,
    evidence_sources: Optional[list[dict]] = None,
    quality_feedback: Optional[list[str]] = None,
):
    return SLIDE_CONTENT_USER_PROMPT.format(
        current_date_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        language=_resolve_prompt_language(language),
        quality_feedback_section=_get_quality_feedback_section(quality_feedback),
        slide_number_section=_get_slide_number_section(slide_number),
        content=outline,
        evidence_sources=json.dumps(evidence_sources or [], ensure_ascii=False),
    )


def get_messages(
    outline: str,
    language: Optional[str],
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    response_schema: Optional[dict] = None,
    *,
    slide_number: Optional[int] = None,
    evidence_sources: Optional[list[dict]] = None,
    quality_feedback: Optional[list[str]] = None,
) -> list[Message]:

    return [
        SystemMessage(
            content=get_system_prompt(
                tone,
                verbosity,
                instructions,
                response_schema,
            ),
        ),
        UserMessage(
            content=get_user_prompt(
                outline,
                language,
                slide_number,
                evidence_sources,
                quality_feedback,
            ),
        ),
    ]


def _schema_has_content_fields(response_schema: Optional[dict]) -> bool:
    if not isinstance(response_schema, dict):
        return False

    properties = response_schema.get("properties")
    return isinstance(properties, dict) and bool(properties)


def _prepare_response_schema(json_schema: Optional[dict]) -> Optional[dict]:
    if not isinstance(json_schema, dict):
        return None

    response_schema = sanitize_generation_schema(
        remove_fields_from_schema(json_schema, ASSET_ONLY_FIELDS)
    )
    if not _schema_has_content_fields(response_schema):
        return None

    if response_schema.get("type") != "object":
        response_schema["type"] = "object"

    response_schema = add_field_in_schema(
        response_schema,
        {
            "__speaker_note__": {
                "type": "string",
                "minLength": 100,
                "maxLength": 500,
                "description": "Speaker note for the slide",
            }
        },
        True,
    )
    response_schema = add_field_in_schema(
        response_schema,
        {"__quality__": quality_metadata_schema()},
        True,
    )
    return ensure_array_schemas_have_items(response_schema)


async def get_slide_content_from_type_and_outline(
    slide_layout: SlideLayoutModel,
    outline: SlideOutlineModel,
    language: Optional[str],
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    *,
    slide_number: Optional[int] = None,
    disconnect_checker: Optional[DisconnectChecker] = None,
    repair_budget: Optional[RepairBudget] = None,
    quality_feedback: Optional[list[str]] = None,
    presentation_id: Optional[str] = None,
    slide_id: Optional[str] = None,
):
    response_schema = _prepare_response_schema(slide_layout.json_schema)
    if response_schema is None:
        return {}

    client = get_client(config=get_llm_config(operation="presentation.slide_content"))
    model = get_model()

    try:
        response_format = JSONSchemaResponse(
            name="response",
            json_schema=response_schema,
            strict=False,
        )
        messages = get_messages(
            outline.content,
            language,
            tone,
            verbosity,
            instructions,
            response_schema,
            slide_number=slide_number,
            evidence_sources=[
                source.model_dump(mode="json") for source in outline.evidence
            ],
            quality_feedback=quality_feedback,
        )

        generated = await generate_structured_with_schema_retries(
            client,
            model,
            messages=messages,
            response_format=response_format,
            json_schema=response_schema,
            strict=False,
            validate_schema=True,
            disconnect_checker=disconnect_checker,
        )

        return finalize_generated_slide_content(
            generated,
            outline=outline,
            language=language,
            repair_budget=repair_budget,
            presentation_id=presentation_id,
            slide_id=slide_id,
        ).value

    except PresentationQualityError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PRESENTATION_QUALITY_CONTRACT_FAILED",
                "rules": sorted({issue.rule_id for issue in e.issues}),
            },
        ) from e
    except Exception as e:
        raise handle_llm_client_exceptions(e)

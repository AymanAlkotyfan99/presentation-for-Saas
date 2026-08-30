from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterator

from .contracts import QualityAction, QualityIssue, QualitySeverity


BREAK_TAG_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
LIST_MARKER_RE = re.compile(r"(?m)^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)")
HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
MARKDOWN_CONTROL_RE = re.compile(r"(?:\*\*|__|(?<!\w)[*_](?!\s)|```|`[^`]+`)")
TEMPLATE_TOKEN_RE = re.compile(
    r"(?:\{\{[^{}]{1,200}\}\}|\[\[[^\[\]]{1,200}\]\]|\$\{[^{}]{1,200}\}|<<[^<>]{1,200}>>)")
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
JSON_FRAGMENT_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)
MOJIBAKE_RE = re.compile(r"(?:Ã.|Â.|â€|å.{0,2}[¤¦ä¹]|ðŸ)")
MODEL_PAGE_LABEL_RE = re.compile(
    r"^\s*(?:page|slide)\s+(?:\d+|[A-Z]{1,4})(?:\s|$|[:\-â€“â€”])",
    re.IGNORECASE,
)


def iter_string_values(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"__speaker_note__", "__quality__"}:
                continue
            nested_path = f"{path}.{key}" if path else str(key)
            yield from iter_string_values(nested, nested_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_path = f"{path}.{index}" if path else str(index)
            yield from iter_string_values(nested, nested_path)
    elif isinstance(value, str):
        yield path, value


def normalize_plain_text(value: str) -> str:
    """Normalize generation syntax for a field whose contract is plain text.

    This only runs on model-generated fields. It does not rewrite arbitrary
    user-authored editor text.
    """

    normalized = BREAK_TAG_RE.sub("\n", value or "")
    normalized = normalized.replace("\\n", "\n")
    normalized = normalized.replace("```json", "").replace("```", "")
    normalized = HEADING_RE.sub("", normalized)
    normalized = LIST_MARKER_RE.sub("", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", normalized)
    normalized = re.sub(r"`([^`]+)`", r"\1", normalized)
    # Generated fields have a PLAIN_TEXT contract. Removing control delimiters
    # is deterministic and retains the authored words, including malformed
    # unbalanced emphasis such as "**Critical Thinking".
    normalized = normalized.replace("**", "").replace("__", "")
    normalized = re.sub(r"(?<!\w)\*([^\n*]+)\*", r"\1", normalized)
    normalized = re.sub(r"(?<!\w)_([^\n_]+)_", r"\1", normalized)
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines())
    return normalized.strip()


def normalize_content_strings(value: Any, path: str = "") -> tuple[Any, list[QualityIssue]]:
    issues: list[QualityIssue] = []
    if isinstance(value, dict):
        result = {}
        for key, nested in value.items():
            if key in {"__quality__", "__speaker_note__"}:
                result[key] = nested
                continue
            next_path = f"{path}.{key}" if path else str(key)
            result[key], nested_issues = normalize_content_strings(nested, next_path)
            issues.extend(nested_issues)
        return result, issues
    if isinstance(value, list):
        result_list = []
        for index, nested in enumerate(value):
            next_path = f"{path}.{index}" if path else str(index)
            repaired, nested_issues = normalize_content_strings(nested, next_path)
            result_list.append(repaired)
            issues.extend(nested_issues)
        return result_list, issues
    if not isinstance(value, str):
        return value, issues

    normalized = normalize_plain_text(value)
    if normalized != value:
        issues.append(
            QualityIssue(
                rule_id="TEXT.PLAIN_TEXT_NORMALIZED",
                severity=QualitySeverity.INFO,
                action=QualityAction.AUTO_FIXABLE,
                path=path,
            )
        )
    return normalized, issues


def text_contract_issues(value: Any) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for path, text in iter_string_values(value):
        if BREAK_TAG_RE.search(text) or HTML_TAG_RE.search(text):
            issues.append(_issue("TEXT.RAW_HTML", path))
        if MARKDOWN_CONTROL_RE.search(text):
            issues.append(_issue("TEXT.MARKDOWN_LEAKAGE", path))
        if TEMPLATE_TOKEN_RE.search(text):
            issues.append(_issue("TEXT.TEMPLATE_TOKEN", path))
        if JSON_FRAGMENT_RE.match(text):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, (dict, list)):
                issues.append(_issue("TEXT.JSON_FRAGMENT", path))
        if "�" in text or MOJIBAKE_RE.search(text):
            issues.append(_issue("TEXT.MOJIBAKE", path))
        if MODEL_PAGE_LABEL_RE.search(text):
            issues.append(_issue("METADATA.MODEL_GENERATED_PAGE_LABEL", path))
    return issues


def language_issues(value: Any, language: str | None) -> list[QualityIssue]:
    resolved = (language or "").strip().lower()
    is_arabic = resolved.startswith("ar") or "arab" in resolved
    is_english = resolved.startswith("en") or "english" in resolved
    if not is_arabic and not is_english:
        return []

    issues: list[QualityIssue] = []
    for path, raw_text in iter_string_values(value):
        text = URL_RE.sub("", raw_text)
        counts = _script_counts(text)
        letters = sum(counts.values())
        if letters == 0:
            continue
        if is_english:
            unexpected = counts["arabic"] + counts["cjk"] + counts["cyrillic"]
            # A single non-Latin symbol is not contamination. Two letters or a
            # complete foreign-script token is suspicious in English prose.
            if unexpected >= 2 and unexpected / letters >= 0.03:
                issues.append(_issue("LANGUAGE.UNEXPECTED_SCRIPT_EN", path))
        else:
            # Arabic decks intentionally allow English product names, acronyms,
            # URLs and technical terminology. CJK/Cyrillic remain suspicious.
            unexpected = counts["cjk"] + counts["cyrillic"]
            if unexpected >= 2 and unexpected / letters >= 0.03:
                issues.append(_issue("LANGUAGE.UNEXPECTED_SCRIPT_AR", path))
    return issues


def normalized_similarity_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def semantic_similarity(left: str, right: str) -> float:
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "every", "for",
        "from", "in", "is", "of", "on", "or", "that", "the", "this", "to", "with",
    }
    left_tokens = {
        token for token in normalized_similarity_text(left).split() if token not in stop_words
    }
    right_tokens = {
        token for token in normalized_similarity_text(right).split() if token not in stop_words
    }
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _script_counts(value: str) -> dict[str, int]:
    counts = {"latin": 0, "arabic": 0, "cjk": 0, "cyrillic": 0, "other": 0}
    for char in value:
        code = ord(char)
        if not unicodedata.category(char).startswith("L"):
            continue
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0x08A0 <= code <= 0x08FF:
            counts["arabic"] += 1
        elif 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or 0x3040 <= code <= 0x30FF or 0xAC00 <= code <= 0xD7AF:
            counts["cjk"] += 1
        elif 0x0400 <= code <= 0x052F:
            counts["cyrillic"] += 1
        elif "LATIN" in unicodedata.name(char, ""):
            counts["latin"] += 1
        else:
            counts["other"] += 1
    return counts


def _issue(rule_id: str, path: str) -> QualityIssue:
    return QualityIssue(
        rule_id=rule_id,
        severity=QualitySeverity.ERROR,
        action=QualityAction.REGENERATE_FIELD,
        path=path,
    )

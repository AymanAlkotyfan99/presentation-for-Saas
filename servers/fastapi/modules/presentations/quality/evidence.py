from __future__ import annotations

from collections.abc import Iterable

from models.presentation_outline_model import (
    EvidenceSourceModel,
    PresentationOutlineModel,
)


def user_evidence_source(
    content: str | None,
    *,
    source_id: str = "user-content",
    title: str = "User-provided presentation content",
) -> EvidenceSourceModel | None:
    snippet = (content or "").strip()
    if not snippet:
        return None
    return EvidenceSourceModel(
        id=source_id,
        provenance="user_provided",
        title=title,
        snippet=snippet[:12000],
    )


def attach_shared_evidence(
    outlines: PresentationOutlineModel,
    sources: Iterable[EvidenceSourceModel],
    *,
    replace: bool = False,
) -> PresentationOutlineModel:
    shared = list(sources)
    for slide in outlines.slides:
        combined = {} if replace else {source.id: source for source in slide.evidence}
        for source in shared:
            combined.setdefault(source.id, source)
        slide.evidence = list(combined.values())[:32]
    return outlines

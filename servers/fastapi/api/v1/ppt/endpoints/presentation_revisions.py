"""Revision-safe canonical command, history, diff, and restore APIs."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.auth.context import get_current_owner_id, get_current_workspace_id
from models.sql.presentation import PresentationModel
from models.sql.presentation_revision import PresentationRevisionModel
from modules.presentations.domain import validate_presentation_document
from modules.presentations.revision_commands import RevisionCommandError
from modules.presentations.revision_service import (
    IdempotencyConflictError,
    RevisionConflictError,
    RevisionNotFoundError,
    apply_revision_commands,
    reconstruct_revision,
    restore_revision,
)
from services.database import get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import revision_if_match_required, revision_writes_enabled, version_history_enabled, workspace_rbac_enforcement_enabled


PRESENTATION_REVISIONS_ROUTER = APIRouter(prefix="/presentations", tags=["Presentation Revisions"])


class RevisionPatchRequest(BaseModel):
    base_revision: int = Field(ge=1)
    commands: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


class RestoreRequest(BaseModel):
    base_revision: int = Field(ge=1)
    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


class RevisionResponse(BaseModel):
    revision: int
    parent_revision: int | None
    checksum: str
    source: str
    restored_from_revision: int | None
    replayed: bool = False
    document: dict[str, Any] | None = None
    created_at: Any
    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


def _enabled(value: bool, code: str) -> None:
    if not value:
        raise StableAPIError(404, code, "Revision endpoint is not enabled")


def _if_match(value: str | None) -> int | None:
    if value is None:
        if revision_if_match_required():
            raise StableAPIError(428, "REVISION_PRECONDITION_REQUIRED", "If-Match revision is required")
        return None
    candidate = value.strip()
    if candidate.startswith("W/"):
        candidate = candidate[2:]
    candidate = candidate.strip('"')
    if not candidate.isdigit():
        raise StableAPIError(400, "REVISION_PRECONDITION_INVALID", "If-Match revision is invalid")
    return int(candidate)


async def _presentation(session: AsyncSession, presentation_id: UUID) -> PresentationModel:
    presentation = await session.get(PresentationModel, presentation_id)
    if not presentation or (
        workspace_rbac_enforcement_enabled() and presentation.workspace_id != get_current_workspace_id()
    ) or (
        not workspace_rbac_enforcement_enabled() and presentation.owner_id != get_current_owner_id()
    ):
        raise StableAPIError(404, "PRESENTATION_NOT_FOUND", "Presentation not found")
    return presentation


def _response(revision: PresentationRevisionModel, *, document=None, replayed=False) -> RevisionResponse:
    return RevisionResponse(
        revision=revision.revision,
        parentRevision=revision.parent_revision,
        checksum=revision.checksum,
        source=revision.source,
        restoredFromRevision=revision.restored_from_revision,
        replayed=replayed,
        document=document,
        createdAt=revision.created_at,
    )


def _translate(exc: Exception) -> StableAPIError:
    if isinstance(exc, RevisionConflictError):
        return StableAPIError(409, "REVISION_CONFLICT", "Presentation revision is stale", params={
            "currentRevision": exc.current_revision,
            **({"currentChecksum": exc.current_checksum} if exc.current_checksum else {}),
        })
    if isinstance(exc, IdempotencyConflictError):
        return StableAPIError(409, "REVISION_IDEMPOTENCY_CONFLICT", "Idempotency key was already used with another request", params={"revision": exc.revision})
    if isinstance(exc, RevisionNotFoundError):
        return StableAPIError(404, "REVISION_NOT_FOUND", "Presentation revision not found", params={"revision": exc.revision})
    if isinstance(exc, RevisionCommandError):
        return StableAPIError(422, exc.code, exc.detail, params={"targetId": exc.target_id} if exc.target_id else None)
    return StableAPIError(500, "REVISION_WRITE_FAILED", "Revision write failed")


@PRESENTATION_REVISIONS_ROUTER.patch("/{presentation_id}/revisions", response_model=RevisionResponse, response_model_by_alias=True, response_model_exclude_none=True)
async def patch_revision(
    presentation_id: UUID,
    response: Response,
    payload: Annotated[RevisionPatchRequest, Body()],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_async_session),
):
    _enabled(revision_writes_enabled(), "REVISION_WRITES_DISABLED")
    await _presentation(session, presentation_id)
    header_revision = _if_match(if_match)
    if header_revision is not None and header_revision != payload.base_revision:
        raise StableAPIError(400, "REVISION_PRECONDITION_MISMATCH", "If-Match and baseRevision must match")
    if not idempotency_key:
        raise StableAPIError(400, "REVISION_IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required")
    try:
        result = await apply_revision_commands(
            session, presentation_id=presentation_id, actor_id=get_current_owner_id(),
            base_revision=payload.base_revision, commands=payload.commands,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        await session.rollback()
        raise _translate(exc) from exc
    response.headers["ETag"] = f'"{result.revision.revision}"'
    return _response(result.revision, document=result.document, replayed=result.replayed)


@PRESENTATION_REVISIONS_ROUTER.get("/{presentation_id}/revisions/current", response_model=RevisionResponse, response_model_by_alias=True, response_model_exclude_none=True)
async def current_revision(presentation_id: UUID, response: Response, session: AsyncSession = Depends(get_async_session)):
    _enabled(revision_writes_enabled(), "REVISION_WRITES_DISABLED")
    presentation = await _presentation(session, presentation_id)
    if presentation.current_revision < 1:
        raise StableAPIError(404, "REVISION_NOT_FOUND", "Presentation has no persisted revision")
    revision = await session.scalar(select(PresentationRevisionModel).where(
        PresentationRevisionModel.presentation_id == presentation_id,
        PresentationRevisionModel.revision == presentation.current_revision,
    ))
    if not revision:
        raise StableAPIError(409, "REVISION_POINTER_INVALID", "Current revision pointer is inconsistent")
    document = await reconstruct_revision(session, presentation_id, revision.revision)
    response.headers["ETag"] = f'"{revision.revision}"'
    return _response(revision, document=document)


@PRESENTATION_REVISIONS_ROUTER.get("/{presentation_id}/revisions", response_model=list[RevisionResponse], response_model_by_alias=True, response_model_exclude_none=True)
async def list_revisions(
    presentation_id: UUID,
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    _enabled(version_history_enabled(), "VERSION_HISTORY_DISABLED")
    await _presentation(session, presentation_id)
    statement = select(PresentationRevisionModel).where(PresentationRevisionModel.presentation_id == presentation_id)
    if before is not None:
        statement = statement.where(PresentationRevisionModel.revision < before)
    revisions = list((await session.scalars(statement.order_by(PresentationRevisionModel.revision.desc()).limit(limit))).all())
    return [_response(revision) for revision in revisions]


@PRESENTATION_REVISIONS_ROUTER.get("/{presentation_id}/revisions/{revision_number}", response_model=RevisionResponse, response_model_by_alias=True, response_model_exclude_none=True)
async def revision_metadata(
    presentation_id: UUID, revision_number: int, include_document: bool = Query(default=False, alias="includeDocument"),
    session: AsyncSession = Depends(get_async_session),
):
    _enabled(version_history_enabled(), "VERSION_HISTORY_DISABLED")
    await _presentation(session, presentation_id)
    revision = await session.scalar(select(PresentationRevisionModel).where(
        PresentationRevisionModel.presentation_id == presentation_id,
        PresentationRevisionModel.revision == revision_number,
    ))
    if not revision:
        raise StableAPIError(404, "REVISION_NOT_FOUND", "Presentation revision not found")
    document = await reconstruct_revision(session, presentation_id, revision_number) if include_document else None
    return _response(revision, document=document)


@PRESENTATION_REVISIONS_ROUTER.get("/{presentation_id}/revision-diff")
async def revision_diff(
    presentation_id: UUID,
    from_revision: int = Query(alias="from", ge=1),
    to_revision: int = Query(alias="to", ge=1),
    session: AsyncSession = Depends(get_async_session),
):
    _enabled(version_history_enabled(), "VERSION_HISTORY_DISABLED")
    await _presentation(session, presentation_id)
    try:
        before = await reconstruct_revision(session, presentation_id, from_revision)
        after = await reconstruct_revision(session, presentation_id, to_revision)
    except Exception as exc:
        raise _translate(exc) from exc
    def counts(document):
        def elements(items): return sum(1 + elements(item.get("children", [])) for item in items)
        return {"slides": len(document["slides"]), "elements": sum(elements(slide["elements"]) for slide in document["slides"]), "assets": len(document["assets"])}
    return {"fromRevision": from_revision, "toRevision": to_revision, "before": counts(before), "after": counts(after), "titleChanged": before["title"] != after["title"]}


@PRESENTATION_REVISIONS_ROUTER.post("/{presentation_id}/revisions/{revision_number}/restore", response_model=RevisionResponse, response_model_by_alias=True, response_model_exclude_none=True)
async def restore_presentation_revision(
    presentation_id: UUID,
    revision_number: int,
    response: Response,
    payload: Annotated[RestoreRequest, Body()],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_async_session),
):
    _enabled(revision_writes_enabled() and version_history_enabled(), "VERSION_HISTORY_DISABLED")
    await _presentation(session, presentation_id)
    header_revision = _if_match(if_match)
    if header_revision is not None and header_revision != payload.base_revision:
        raise StableAPIError(400, "REVISION_PRECONDITION_MISMATCH", "If-Match and baseRevision must match")
    if not idempotency_key:
        raise StableAPIError(400, "REVISION_IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required")
    try:
        result = await restore_revision(
            session, presentation_id=presentation_id, actor_id=get_current_owner_id(),
            target_revision=revision_number, base_revision=payload.base_revision,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        await session.rollback()
        raise _translate(exc) from exc
    response.headers["ETag"] = f'"{result.revision.revision}"'
    return _response(result.revision, document=result.document, replayed=result.replayed)

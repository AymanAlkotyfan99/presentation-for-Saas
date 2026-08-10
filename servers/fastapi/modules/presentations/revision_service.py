"""Atomic command-to-revision persistence, replay, restore, and stale-job guards."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.async_task import AsyncTaskModel
from models.sql.presentation import PresentationModel
from models.sql.presentation_document import CanonicalConversionStatus, PresentationDocumentModel
from models.sql.presentation_revision import PresentationRevisionModel, PresentationRevisionPatchModel
from modules.presentations.domain import canonical_checksum, validate_presentation_document
from modules.presentations.revision_commands import RevisionCommandError, apply_commands, flatten_command_count
from api.v1.auth.context import get_current_service_account_id, get_current_workspace_id
from utils.architecture_flags import workspace_rbac_enforcement_enabled
from modules.workspaces.application.audit import append_audit_event


SNAPSHOT_INTERVAL = 20
MAX_IDEMPOTENCY_KEY_BYTES = 128


@dataclass(slots=True)
class RevisionConflictError(RuntimeError):
    current_revision: int
    current_checksum: str | None


@dataclass(slots=True)
class IdempotencyConflictError(RuntimeError):
    revision: int


@dataclass(slots=True)
class RevisionNotFoundError(RuntimeError):
    revision: int


@dataclass(slots=True)
class StaleTaskRevisionError(RuntimeError):
    source_revision: int
    current_revision: int


@dataclass(slots=True)
class RevisionWriteResult:
    revision: PresentationRevisionModel
    document: dict[str, Any]
    replayed: bool = False


def request_checksum(base_revision: int, commands: list[dict[str, Any]]) -> str:
    try:
        encoded = json.dumps(
            {"baseRevision": base_revision, "commands": commands},
            ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RevisionCommandError("EDITOR_COMMAND_NOT_SERIALIZABLE", "Commands must be finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def actor_scope(actor_id: UUID | None) -> str:
    service_account_id = get_current_service_account_id()
    if service_account_id:
        return f"service:{service_account_id}"
    return f"user:{actor_id}" if actor_id else "system"


def validate_idempotency_key(value: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate.encode("utf-8")) > MAX_IDEMPOTENCY_KEY_BYTES:
        raise RevisionCommandError("REVISION_IDEMPOTENCY_KEY_INVALID", "Idempotency key is missing or too long")
    if any(ord(char) < 33 or ord(char) > 126 for char in candidate):
        raise RevisionCommandError("REVISION_IDEMPOTENCY_KEY_INVALID", "Idempotency key contains unsupported characters")
    return candidate


async def _locked_presentation(
    session: AsyncSession, presentation_id: UUID, actor_id: UUID | None
) -> PresentationModel | None:
    statement = select(PresentationModel).where(PresentationModel.id == presentation_id)
    workspace_id = get_current_workspace_id()
    if workspace_rbac_enforcement_enabled() and workspace_id is not None:
        statement = statement.where(PresentationModel.workspace_id == workspace_id)
    elif actor_id is not None:
        statement = statement.where(PresentationModel.owner_id == actor_id)
    return await session.scalar(statement.with_for_update().execution_options(populate_existing=True))


async def seed_current_revision(
    session: AsyncSession,
    presentation: PresentationModel,
    record: PresentationDocumentModel | None,
) -> int:
    """Idempotently adopt a pre-Sprint-6 canonical document as an anchor."""
    if presentation.current_revision > 0:
        return presentation.current_revision
    if not record or not record.document or not record.checksum:
        return 0
    existing = await session.scalar(select(PresentationRevisionModel).where(
        PresentationRevisionModel.presentation_id == presentation.id,
        PresentationRevisionModel.revision == record.revision,
    ))
    if not existing:
        session.add(PresentationRevisionModel(
            presentation_id=presentation.id,
            owner_id=presentation.owner_id,
            workspace_id=presentation.workspace_id,
            revision=record.revision,
            parent_revision=None,
            checksum=record.checksum,
            snapshot_document=record.document,
            source="canonical-bootstrap",
            actor_id=presentation.owner_id,
            retention_class="anchor",
        ))
    presentation.current_revision = record.revision
    await session.flush()
    return record.revision


async def reconstruct_revision(
    session: AsyncSession, presentation_id: UUID, target_revision: int
) -> dict[str, Any]:
    if target_revision < 1:
        raise RevisionNotFoundError(target_revision)
    target = await session.scalar(select(PresentationRevisionModel).where(
        PresentationRevisionModel.presentation_id == presentation_id,
        PresentationRevisionModel.revision == target_revision,
    ))
    if not target:
        raise RevisionNotFoundError(target_revision)
    anchor = await session.scalar(
        select(PresentationRevisionModel).where(
            PresentationRevisionModel.presentation_id == presentation_id,
            PresentationRevisionModel.revision <= target_revision,
            PresentationRevisionModel.snapshot_document.is_not(None),
        ).order_by(PresentationRevisionModel.revision.desc()).limit(1)
    )
    if not anchor or not anchor.snapshot_document:
        raise RevisionNotFoundError(target_revision)
    document = anchor.snapshot_document
    if anchor.revision < target_revision:
        patches = list((await session.scalars(
            select(PresentationRevisionPatchModel).where(
                PresentationRevisionPatchModel.presentation_id == presentation_id,
                PresentationRevisionPatchModel.revision > anchor.revision,
                PresentationRevisionPatchModel.revision <= target_revision,
            ).order_by(PresentationRevisionPatchModel.revision)
        )).all())
        expected = anchor.revision + 1
        for patch in patches:
            if patch.revision != expected:
                raise RevisionNotFoundError(target_revision)
            document = apply_commands(document, patch.commands)
            expected += 1
        if expected - 1 != target_revision:
            raise RevisionNotFoundError(target_revision)
    validated = validate_presentation_document(document)
    if canonical_checksum(validated) != target.checksum:
        raise RevisionCommandError("REVISION_CHECKSUM_MISMATCH", "Revision replay checksum did not match")
    return validated.model_dump(mode="json", by_alias=True, exclude_none=True)


async def apply_revision_commands(
    session: AsyncSession,
    *,
    presentation_id: UUID,
    actor_id: UUID | None,
    base_revision: int,
    commands: list[dict[str, Any]],
    idempotency_key: str,
) -> RevisionWriteResult:
    key = validate_idempotency_key(idempotency_key)
    count = flatten_command_count(commands)
    checksum = request_checksum(base_revision, commands)
    scope = actor_scope(actor_id)
    presentation = await _locked_presentation(session, presentation_id, actor_id)
    if not presentation:
        raise RevisionNotFoundError(base_revision)
    record = await session.scalar(select(PresentationDocumentModel).where(
        PresentationDocumentModel.presentation_id == presentation_id
    ).with_for_update().execution_options(populate_existing=True))
    current = await seed_current_revision(session, presentation, record)

    prior_patch = await session.scalar(select(PresentationRevisionPatchModel).where(
        PresentationRevisionPatchModel.presentation_id == presentation_id,
        PresentationRevisionPatchModel.actor_scope == scope,
        PresentationRevisionPatchModel.idempotency_key == key,
    ))
    if prior_patch:
        if prior_patch.request_checksum != checksum:
            raise IdempotencyConflictError(prior_patch.revision)
        revision = await session.scalar(select(PresentationRevisionModel).where(
            PresentationRevisionModel.presentation_id == presentation_id,
            PresentationRevisionModel.revision == prior_patch.revision,
        ))
        if not revision:
            raise RevisionNotFoundError(prior_patch.revision)
        return RevisionWriteResult(revision, await reconstruct_revision(session, presentation_id, revision.revision), True)

    if current != base_revision:
        raise RevisionConflictError(current, record.checksum if record else None)
    if not record or not record.document or current == 0:
        raise RevisionCommandError("REVISION_DOCUMENT_REQUIRED", "Persist a canonical document before applying commands")
    next_document = apply_commands(record.document, commands)
    next_checksum = canonical_checksum(next_document)
    next_revision = current + 1
    revision = PresentationRevisionModel(
        presentation_id=presentation_id,
        owner_id=presentation.owner_id,
        workspace_id=presentation.workspace_id,
        revision=next_revision,
        parent_revision=current,
        checksum=next_checksum,
        snapshot_document=next_document if next_revision % SNAPSHOT_INTERVAL == 1 else None,
        source="command",
        actor_id=actor_id,
        retention_class="anchor" if next_revision % SNAPSHOT_INTERVAL == 1 else "standard",
    )
    patch = PresentationRevisionPatchModel(
        presentation_id=presentation_id,
        owner_id=presentation.owner_id,
        workspace_id=presentation.workspace_id,
        revision=next_revision,
        base_revision=current,
        actor_scope=scope,
        idempotency_key=key,
        request_checksum=checksum,
        commands=commands,
        command_count=count,
    )
    session.add(revision)
    session.add(patch)
    record.document = next_document
    record.checksum = next_checksum
    record.revision = next_revision
    record.schema_version = "1.0.0"
    record.conversion_status = CanonicalConversionStatus.CONVERTED
    presentation.current_revision = next_revision
    await session.commit()
    await session.refresh(revision)
    return RevisionWriteResult(revision, next_document)


async def write_snapshot_revision(
    session: AsyncSession,
    *,
    presentation_id: UUID,
    actor_id: UUID | None,
    document: dict[str, Any],
    expected_revision: int,
    idempotency_key: str,
    source: str,
    restored_from_revision: int | None = None,
    status: CanonicalConversionStatus = CanonicalConversionStatus.CONVERTED,
    asset_mappings: dict[str, str] | None = None,
) -> RevisionWriteResult:
    validated = validate_presentation_document(document)
    normalized = validated.model_dump(mode="json", by_alias=True, exclude_none=True)
    doc_checksum = canonical_checksum(validated)
    key = validate_idempotency_key(idempotency_key)
    commands: list[dict[str, Any]] = []
    checksum = hashlib.sha256(f"snapshot:{expected_revision}:{doc_checksum}".encode()).hexdigest()
    scope = actor_scope(actor_id)
    presentation = await _locked_presentation(session, presentation_id, actor_id)
    if not presentation:
        raise RevisionNotFoundError(expected_revision)
    record = await session.scalar(select(PresentationDocumentModel).where(
        PresentationDocumentModel.presentation_id == presentation_id
    ).with_for_update().execution_options(populate_existing=True))
    current = await seed_current_revision(session, presentation, record)
    prior = await session.scalar(select(PresentationRevisionPatchModel).where(
        PresentationRevisionPatchModel.presentation_id == presentation_id,
        PresentationRevisionPatchModel.actor_scope == scope,
        PresentationRevisionPatchModel.idempotency_key == key,
    ))
    if prior:
        if prior.request_checksum != checksum:
            raise IdempotencyConflictError(prior.revision)
        revision = await session.scalar(select(PresentationRevisionModel).where(
            PresentationRevisionModel.presentation_id == presentation_id,
            PresentationRevisionModel.revision == prior.revision,
        ))
        return RevisionWriteResult(revision, await reconstruct_revision(session, presentation_id, prior.revision), True)
    if current != expected_revision:
        raise RevisionConflictError(current, record.checksum if record else None)
    next_revision = current + 1
    revision = PresentationRevisionModel(
        presentation_id=presentation_id, owner_id=presentation.owner_id,
        workspace_id=presentation.workspace_id,
        revision=next_revision, parent_revision=current or None,
        checksum=doc_checksum, snapshot_document=normalized, source=source,
        actor_id=actor_id, retention_class="anchor",
        restored_from_revision=restored_from_revision,
    )
    session.add(revision)
    session.add(PresentationRevisionPatchModel(
        presentation_id=presentation_id, owner_id=presentation.owner_id,
        workspace_id=presentation.workspace_id,
        revision=next_revision, base_revision=current, actor_scope=scope,
        idempotency_key=key, request_checksum=checksum, commands=commands, command_count=0,
    ))
    if record:
        record.document = normalized; record.checksum = doc_checksum; record.revision = next_revision
        record.conversion_status = status; record.asset_mappings = asset_mappings or record.asset_mappings
    else:
        record = PresentationDocumentModel(
            presentation_id=presentation_id, owner_id=presentation.owner_id,
            workspace_id=presentation.workspace_id,
            schema_version="1.0.0", document=normalized, checksum=doc_checksum,
            revision=next_revision, conversion_status=status, asset_mappings=asset_mappings,
        )
        session.add(record)
    presentation.current_revision = next_revision
    if restored_from_revision is not None and presentation.workspace_id is not None:
        append_audit_event(
            session, workspace_id=presentation.workspace_id, actor_id=actor_id,
            event_type="presentation.revision.restored",
            subject_type="presentation", subject_id=presentation_id,
            metadata={"targetRevision": restored_from_revision},
        )
    await session.commit()
    await session.refresh(revision)
    return RevisionWriteResult(revision, normalized)


async def restore_revision(
    session: AsyncSession,
    *,
    presentation_id: UUID,
    actor_id: UUID | None,
    target_revision: int,
    base_revision: int,
    idempotency_key: str,
) -> RevisionWriteResult:
    target_document = await reconstruct_revision(session, presentation_id, target_revision)
    result = await write_snapshot_revision(
        session, presentation_id=presentation_id, actor_id=actor_id,
        document=target_document, expected_revision=base_revision,
        idempotency_key=idempotency_key, source="restore",
        restored_from_revision=target_revision,
    )
    return result


async def assert_task_revision_current(session: AsyncSession, task: AsyncTaskModel) -> None:
    if not task.presentation_id or task.source_revision is None:
        return
    presentation = await session.scalar(select(PresentationModel).where(PresentationModel.id == task.presentation_id))
    if presentation is None:
        raise RevisionNotFoundError(task.source_revision)
    if task.workspace_id != presentation.workspace_id:
        raise RevisionCommandError("TASK_WORKSPACE_MISMATCH", "Task workspace does not match its presentation")
    if presentation.current_revision != task.source_revision:
        raise StaleTaskRevisionError(task.source_revision, presentation.current_revision)

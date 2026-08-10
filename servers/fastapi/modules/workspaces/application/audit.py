from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.context import get_current_service_account_id
from modules.workspaces.persistence.models import AuditEventModel


SAFE_METADATA_KEYS = frozenset({"previousRole", "newRole", "scopeCount", "reason", "targetRevision", "enabled"})


def append_audit_event(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    event_type: str,
    subject_type: str,
    subject_id: UUID | str,
    metadata: dict[str, Any] | None = None,
) -> AuditEventModel:
    safe = {
        key: value for key, value in (metadata or {}).items()
        if key in SAFE_METADATA_KEYS and isinstance(value, (str, int, float, bool))
    }
    event = AuditEventModel(
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_service_account_id=get_current_service_account_id(),
        event_type=event_type[:64],
        subject_type=subject_type[:64],
        subject_id=str(subject_id)[:128],
        safe_metadata=safe,
    )
    session.add(event)
    return event

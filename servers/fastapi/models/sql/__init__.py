"""Canonical SQL model exports.

Imports are intentionally explicit so metadata discovery sees lifecycle models
without creating a parallel declarative registry.
"""

from models.sql.user import User
from modules.identity.persistence.models import (
    AccountLifecycleAuditEvent,
    AccountLoginIdentifier,
    AccountPurposeChallenge,
    PendingRegistration,
)
from modules.notifications.persistence.models import NotificationDelivery

__all__ = [
    "AccountLifecycleAuditEvent",
    "AccountLoginIdentifier",
    "AccountPurposeChallenge",
    "NotificationDelivery",
    "PendingRegistration",
    "User",
]

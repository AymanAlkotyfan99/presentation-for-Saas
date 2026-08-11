"""Explicit trusted operation-to-handler registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import BaseModel

from modules.jobs.domain.models import QueueClass
from modules.workspaces.domain.models import Permission


JobHandler = Callable[[object, BaseModel], Awaitable[dict]]


@dataclass(frozen=True)
class OperationDefinition:
    operation: str
    queue_class: QueueClass
    payload_model: type[BaseModel]
    handler: JobHandler
    max_attempts: int = 3
    required_permissions: tuple[Permission, ...] = ()


class JobRegistry:
    def __init__(self) -> None:
        self._operations: dict[str, OperationDefinition] = {}

    def register(self, definition: OperationDefinition) -> None:
        if definition.operation in self._operations:
            raise ValueError(f"Job operation already registered: {definition.operation}")
        self._operations[definition.operation] = definition

    def get(self, operation: str) -> OperationDefinition | None:
        return self._operations.get(operation)

    def operations(self) -> tuple[str, ...]:
        return tuple(sorted(self._operations))


JOB_REGISTRY = JobRegistry()

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QualitySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class QualityAction(str, Enum):
    AUTO_FIXABLE = "AUTO_FIXABLE"
    REGENERATE_FIELD = "REGENERATE_FIELD"
    REGENERATE_SLIDE = "REGENERATE_SLIDE"
    RESELECT_LAYOUT = "RESELECT_LAYOUT"
    BLOCK_PRESENTATION = "BLOCK_PRESENTATION"


@dataclass(frozen=True)
class QualityIssue:
    rule_id: str
    severity: QualitySeverity
    action: QualityAction
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityResult:
    value: Any
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def blocking_issues(self) -> list[QualityIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity in {QualitySeverity.ERROR, QualitySeverity.FATAL}
            and issue.action != QualityAction.AUTO_FIXABLE
        ]

    @property
    def passed(self) -> bool:
        return not self.blocking_issues


@dataclass
class RepairBudget:
    """A single presentation-level budget; it never invokes a provider itself."""

    max_auto_fixes: int = 200
    max_layout_reselections: int = 50
    max_slide_regenerations: int = 50
    auto_fixes_used: int = 0
    layout_reselections_used: int = 0
    slide_regenerations_used: int = 0

    def use_auto_fix(self) -> bool:
        if self.auto_fixes_used >= self.max_auto_fixes:
            return False
        self.auto_fixes_used += 1
        return True

    def use_layout_reselection(self) -> bool:
        if self.layout_reselections_used >= self.max_layout_reselections:
            return False
        self.layout_reselections_used += 1
        return True

    def reserve_layout_regeneration(self) -> bool:
        """Atomically reserve one layout change and one slide-content retry."""

        if (
            self.layout_reselections_used >= self.max_layout_reselections
            or self.slide_regenerations_used >= self.max_slide_regenerations
        ):
            return False
        self.layout_reselections_used += 1
        self.slide_regenerations_used += 1
        return True

    def reserve_slide_regeneration(self) -> bool:
        if self.slide_regenerations_used >= self.max_slide_regenerations:
            return False
        self.slide_regenerations_used += 1
        return True


class PresentationQualityError(RuntimeError):
    def __init__(self, issues: list[QualityIssue]):
        self.issues = issues
        rule_ids = ", ".join(sorted({issue.rule_id for issue in issues}))
        super().__init__(f"Presentation quality contract failed: {rule_ids}")

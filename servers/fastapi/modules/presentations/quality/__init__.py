"""Presentation-generation quality contracts.

The LLM is a planner.  This package owns the deterministic checks and bindings
that must succeed before generated slide data is persisted or exported.
"""

from .bindings import apply_system_bindings, sanitize_generation_schema
from .contracts import (
    PresentationQualityError,
    QualityAction,
    QualityIssue,
    QualityResult,
    QualitySeverity,
    RepairBudget,
)
from .gate import (
    finalize_generated_slide_content,
    validate_final_presentation,
    validate_final_slide_ui,
)
from .language import infer_presentation_language
from .layout import repair_structure_for_content, reselect_layout_after_quality_failure

__all__ = [
    "PresentationQualityError",
    "QualityAction",
    "QualityIssue",
    "QualityResult",
    "QualitySeverity",
    "RepairBudget",
    "apply_system_bindings",
    "finalize_generated_slide_content",
    "infer_presentation_language",
    "repair_structure_for_content",
    "reselect_layout_after_quality_failure",
    "sanitize_generation_schema",
    "validate_final_presentation",
    "validate_final_slide_ui",
]

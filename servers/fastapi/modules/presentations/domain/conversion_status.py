from models.sql.presentation_document import CanonicalConversionStatus


# Conversion retries are deliberately bounded in both the HTTP and CLI paths.
MAX_CONVERSION_ATTEMPTS = 3


ALLOWED_TRANSITIONS: dict[CanonicalConversionStatus, frozenset[CanonicalConversionStatus]] = {
    # The repository persists the final outcome atomically, so a brand-new or
    # resumed conversion can move directly to a terminal state without exposing
    # a partially written canonical document.
    CanonicalConversionStatus.NOT_STARTED: frozenset(
        {
            CanonicalConversionStatus.PENDING,
            CanonicalConversionStatus.CONVERTING,
            CanonicalConversionStatus.CONVERTED,
            CanonicalConversionStatus.FAILED,
            CanonicalConversionStatus.UNSUPPORTED,
            CanonicalConversionStatus.NEEDS_REVIEW,
        }
    ),
    CanonicalConversionStatus.PENDING: frozenset(
        {
            CanonicalConversionStatus.CONVERTING,
            CanonicalConversionStatus.CONVERTED,
            CanonicalConversionStatus.FAILED,
            CanonicalConversionStatus.UNSUPPORTED,
            CanonicalConversionStatus.NEEDS_REVIEW,
        }
    ),
    CanonicalConversionStatus.CONVERTING: frozenset({CanonicalConversionStatus.CONVERTED, CanonicalConversionStatus.FAILED, CanonicalConversionStatus.UNSUPPORTED, CanonicalConversionStatus.NEEDS_REVIEW}),
    CanonicalConversionStatus.CONVERTED: frozenset(
        {CanonicalConversionStatus.CONVERTING, CanonicalConversionStatus.NEEDS_REVIEW}
    ),
    CanonicalConversionStatus.FAILED: frozenset(
        {
            CanonicalConversionStatus.PENDING,
            CanonicalConversionStatus.CONVERTING,
            CanonicalConversionStatus.CONVERTED,
            CanonicalConversionStatus.UNSUPPORTED,
            CanonicalConversionStatus.NEEDS_REVIEW,
        }
    ),
    CanonicalConversionStatus.UNSUPPORTED: frozenset(
        {
            CanonicalConversionStatus.PENDING,
            CanonicalConversionStatus.CONVERTING,
            CanonicalConversionStatus.CONVERTED,
            CanonicalConversionStatus.FAILED,
            CanonicalConversionStatus.NEEDS_REVIEW,
        }
    ),
    CanonicalConversionStatus.NEEDS_REVIEW: frozenset(
        {
            CanonicalConversionStatus.PENDING,
            CanonicalConversionStatus.CONVERTING,
            CanonicalConversionStatus.CONVERTED,
            CanonicalConversionStatus.FAILED,
            CanonicalConversionStatus.UNSUPPORTED,
        }
    ),
}


def require_conversion_transition(
    current: CanonicalConversionStatus,
    target: CanonicalConversionStatus,
) -> None:
    if current == target:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid canonical conversion transition: {current.value}->{target.value}")

import math


DEFAULT_SENTRY_TRACES_SAMPLE_RATE = 0.1


def parse_sentry_sample_rate(value: str | None) -> float:
    """Parse and clamp a sample rate, falling back to a low-volume default."""
    if value is None:
        return DEFAULT_SENTRY_TRACES_SAMPLE_RATE
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SENTRY_TRACES_SAMPLE_RATE
    if not math.isfinite(parsed):
        return DEFAULT_SENTRY_TRACES_SAMPLE_RATE
    return max(0.0, min(1.0, parsed))


def parse_sentry_send_default_pii(value: str | None) -> bool:
    """PII collection is opt-in and malformed settings fail closed."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}

import sys
from collections.abc import Sequence


SUPPORTED_PYTHON = (3, 11)


def require_supported_python(
    version_info: Sequence[int] | None = None,
) -> None:
    """Fail before application startup when Python is not exactly 3.11."""
    version = tuple(version_info or sys.version_info)
    if version[:2] != SUPPORTED_PYTHON:
        actual = ".".join(str(part) for part in version[:3])
        raise RuntimeError(
            "Presenton FastAPI requires Python 3.11.x; "
            f"the active interpreter is Python {actual}. "
            "Install Python 3.11 and run `uv sync --locked --dev`."
        )

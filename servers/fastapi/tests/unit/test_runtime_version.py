import pytest

from utils.runtime_version import require_supported_python


def test_python_311_is_supported() -> None:
    require_supported_python((3, 11, 9))


@pytest.mark.parametrize("version", [(3, 10, 14), (3, 12, 0)])
def test_unsupported_python_fails_with_actionable_message(version) -> None:
    with pytest.raises(RuntimeError, match=r"requires Python 3\.11\.x"):
        require_supported_python(version)

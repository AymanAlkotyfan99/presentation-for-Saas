import pytest

from services.chat.theme_policy import (
    normalize_hex_color,
    sanitize_theme_id,
    select_theme_for_query,
)
from utils.architecture_flags import (
    LegacyV1ReadDisabledError,
    LegacyV1WriteDisabledError,
    require_legacy_v1_read,
    require_legacy_v1_write,
    architecture_facades_enabled,
)


def test_legacy_flags_default_to_compatibility(monkeypatch):
    monkeypatch.delenv("LEGACY_V1_READS_ENABLED", raising=False)
    monkeypatch.delenv("LEGACY_V1_WRITES_ENABLED", raising=False)
    require_legacy_v1_read("v1-standard")
    require_legacy_v1_write("v1-standard")


def test_legacy_flags_can_disable_reads_and_writes(monkeypatch):
    monkeypatch.setenv("LEGACY_V1_READS_ENABLED", "false")
    monkeypatch.setenv("LEGACY_V1_WRITES_ENABLED", "0")
    with pytest.raises(LegacyV1ReadDisabledError):
        require_legacy_v1_read("v1-standard")
    with pytest.raises(LegacyV1WriteDisabledError):
        require_legacy_v1_write("v1-standard")
    require_legacy_v1_read("v2-standard")
    require_legacy_v1_write("v2-standard")


def test_architecture_facade_can_be_rolled_back(monkeypatch):
    monkeypatch.delenv("ARCHITECTURE_FACADES_ENABLED", raising=False)
    assert architecture_facades_enabled() is True
    monkeypatch.setenv("ARCHITECTURE_FACADES_ENABLED", "false")
    assert architecture_facades_enabled() is False


def test_extracted_theme_policy_preserves_selection_rules():
    themes = [
        {"id": "professional-dark", "name": "Night", "data": {"colors": {"background": "#061538"}}},
        {"id": "professional-blue", "name": "Blue", "data": {"colors": {"background": "#ffffff"}}},
    ]
    assert sanitize_theme_id("  Executive / Blue ") == "executive-blue"
    assert normalize_hex_color("#abc") == "#aabbcc"
    assert normalize_hex_color("not-a-color") is None
    assert select_theme_for_query("dark", themes, None) == themes[0]

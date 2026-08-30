import asyncio

from models.sql.user import User
from services.provider_settings import (
    merge_provider_settings,
    migrate_provider_settings_from_file,
    sanitize_provider_settings,
)
from utils.user_config_store import read_user_config_file, update_user_config_file


class ProviderSettingsSession:
    def __init__(self):
        self.row = None

    async def get(self, _model, _key):
        return self.row

    def add(self, row):
        self.row = row

    async def commit(self):
        return None

    async def refresh(self, _row):
        return None


def test_user_table_has_username_and_no_email_column():
    columns = set(User.__table__.columns.keys())

    assert "username" in columns
    assert "email" not in columns


def test_provider_settings_exclude_all_legacy_auth_fields():
    assert sanitize_provider_settings(
        {
            "LLM": "openai",
            "AUTH_USERNAME": "admin",
            "AUTH_PASSWORD": "plain",
            "AUTH_PASSWORD_HASH": "hash",
            "AUTH_SECRET_KEY": "jwt-secret",
        }
    ) == {"LLM": "openai"}


def test_provider_settings_merge_preserves_fields_owned_by_other_sections():
    existing = {
        "LLM": "openai",
        "OPENAI_MODEL": "gpt-4.1",
        "IMAGE_PROVIDER": "pexels",
        "PEXELS_API_KEY": "image-secret",
        "WEB_GROUNDING": True,
        "WEB_SEARCH_PROVIDER": "auto",
    }

    merged = merge_provider_settings(
        existing,
        {"LLM": "openrouter", "OPENROUTER_MODEL": "provider/model"},
    )

    assert merged["LLM"] == "openrouter"
    assert merged["OPENROUTER_MODEL"] == "provider/model"
    assert merged["IMAGE_PROVIDER"] == "pexels"
    assert merged["PEXELS_API_KEY"] == "image-secret"
    assert merged["WEB_GROUNDING"] is True


def test_startup_migrates_user_config_and_rewrites_compatibility_file(
    monkeypatch, tmp_path
):
    path = tmp_path / "userConfig.json"
    monkeypatch.setenv("USER_CONFIG_PATH", str(path))
    update_user_config_file(
        str(path),
        lambda _: {
            "AUTH_USERNAME": "admin",
            "AUTH_PASSWORD_HASH": "legacy-hash",
            "AUTH_SECRET_KEY": "jwt-secret",
            "LLM": "openai",
            "OPENAI_API_KEY": "provider-key",
        },
    )
    session = ProviderSettingsSession()

    migrated = asyncio.run(migrate_provider_settings_from_file(session))

    assert migrated == {
        "LLM": "openai",
        "OPENAI_API_KEY": "provider-key",
    }
    assert session.row.config == migrated
    assert read_user_config_file(str(path)) == {
        "LLM": "openai",
        "OPENAI_API_KEY": "provider-key",
        "AUTH_USERNAME": "admin",
        "AUTH_PASSWORD_HASH": "legacy-hash",
        "AUTH_SECRET_KEY": "jwt-secret",
    }

"""Dry-run-first import of the singleton legacy provider configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.provider_settings import ProviderSettings
from modules.providers.adapters.registry import PROVIDER_REGISTRY
from modules.providers.application.configuration import create_provider_account
from modules.providers.domain.contracts import RegionPolicyStatus
from modules.providers.persistence.models import ProviderAccountModel
from modules.providers.security.secrets import MasterKeyProvider, resolve_provider_secret, rotate_provider_secret
from modules.workspaces.application.audit import append_audit_event


MODEL_FIELDS = {
    "text": {
        "openai": "OPENAI_MODEL", "deepseek": "DEEPSEEK_MODEL", "google": "GOOGLE_MODEL",
        "vertex": "VERTEX_MODEL", "azure": "AZURE_OPENAI_MODEL", "bedrock": "BEDROCK_MODEL",
        "openrouter": "OPENROUTER_MODEL", "fireworks": "FIREWORKS_MODEL", "together": "TOGETHER_MODEL",
        "cerebras": "CEREBRAS_MODEL", "anthropic": "ANTHROPIC_MODEL", "litellm": "LITELLM_MODEL",
        "lmstudio": "LMSTUDIO_MODEL", "ollama": "OLLAMA_MODEL", "custom": "CUSTOM_MODEL", "codex": "CODEX_MODEL",
    }
}
SECRET_FIELDS = {
    "text.openai": "OPENAI_API_KEY", "text.deepseek": "DEEPSEEK_API_KEY",
    "text.google": "GOOGLE_API_KEY", "text.vertex": "VERTEX_API_KEY",
    "text.azure": "AZURE_OPENAI_API_KEY", "text.bedrock": "BEDROCK_AWS_SECRET_ACCESS_KEY",
    "text.openrouter": "OPENROUTER_API_KEY", "text.fireworks": "FIREWORKS_API_KEY",
    "text.together": "TOGETHER_API_KEY", "text.cerebras": "CEREBRAS_API_KEY",
    "text.anthropic": "ANTHROPIC_API_KEY", "text.litellm": "LITELLM_API_KEY",
    "text.lmstudio": "LMSTUDIO_API_KEY", "text.custom": "CUSTOM_LLM_API_KEY",
    "image.pexels": "PEXELS_API_KEY", "image.pixabay": "PIXABAY_API_KEY",
    "image.gemini_flash": "GOOGLE_API_KEY", "image.nanobanana_pro": "GOOGLE_API_KEY",
    "image.dall-e-3": "OPENAI_API_KEY", "image.gpt-image-1.5": "OPENAI_API_KEY",
    "image.open_webui": "OPEN_WEBUI_IMAGE_API_KEY", "image.openai_compatible": "OPENAI_COMPAT_IMAGE_API_KEY",
    "search.tavily": "TAVILY_API_KEY", "search.exa": "EXA_API_KEY",
    "search.brave": "BRAVE_SEARCH_API_KEY", "search.serper": "SERPER_API_KEY",
}
SECRET_COMPONENT_FIELDS = {
    "text.bedrock": {
        "BEDROCK_AWS_ACCESS_KEY_ID": "access_key_id",
        "BEDROCK_AWS_SECRET_ACCESS_KEY": "secret_access_key",
        "BEDROCK_AWS_SESSION_TOKEN": "session_token",
    },
    "text.codex": {
        "CODEX_ACCESS_TOKEN": "access_token",
        "CODEX_REFRESH_TOKEN": "refresh_token",
        "CODEX_ACCOUNT_ID": "account_id",
        "CODEX_TOKEN_EXPIRES": "expires",
    },
}
SAFE_CONFIG_FIELDS = {
    "text.deepseek": {"DEEPSEEK_BASE_URL": "base_url"},
    "text.vertex": {"VERTEX_BASE_URL": "base_url", "VERTEX_PROJECT": "project", "VERTEX_LOCATION": "location"},
    "text.azure": {"AZURE_OPENAI_BASE_URL": "base_url", "AZURE_OPENAI_ENDPOINT": "endpoint", "AZURE_OPENAI_API_VERSION": "api_version", "AZURE_OPENAI_DEPLOYMENT": "deployment"},
    "text.bedrock": {"BEDROCK_REGION": "region", "BEDROCK_PROFILE_NAME": "profile_name"},
    "text.openrouter": {"OPENROUTER_BASE_URL": "base_url"},
    "text.fireworks": {"FIREWORKS_BASE_URL": "base_url"},
    "text.together": {"TOGETHER_BASE_URL": "base_url"},
    "text.cerebras": {"CEREBRAS_BASE_URL": "base_url"},
    "text.litellm": {"LITELLM_BASE_URL": "base_url"},
    "text.lmstudio": {"LMSTUDIO_BASE_URL": "base_url"},
    "text.ollama": {"OLLAMA_URL": "base_url"},
    "text.custom": {"CUSTOM_LLM_URL": "base_url"},
    "image.comfyui": {"COMFYUI_URL": "base_url", "COMFYUI_WORKFLOW": "workflow"},
    "image.open_webui": {"OPEN_WEBUI_IMAGE_URL": "base_url"},
    "image.openai_compatible": {"OPENAI_COMPAT_IMAGE_BASE_URL": "base_url", "OPENAI_COMPAT_IMAGE_MODEL": "model"},
    "search.searxng": {"SEARXNG_BASE_URL": "base_url"},
}


@dataclass(frozen=True)
class LegacyProviderInventory:
    adapter_id: str
    model: str
    has_secret: bool
    status: str
    account_id: UUID | None = None
    safe_config: dict | None = None


def inventory_legacy_provider_settings(config: dict) -> list[tuple[LegacyProviderInventory, str | None]]:
    selected = (
        ("text", str(config.get("LLM") or "").strip().lower()),
        ("image", str(config.get("IMAGE_PROVIDER") or "").strip().lower()),
        ("search", str(config.get("WEB_SEARCH_PROVIDER") or "").strip().lower()),
    )
    rows: list[tuple[LegacyProviderInventory, str | None]] = []
    selected_adapter_ids: set[str] = set()
    for family, provider in selected:
        if not provider:
            continue
        adapter_id = f"{family}.{provider}"
        selected_adapter_ids.add(adapter_id)
        if PROVIDER_REGISTRY.get(adapter_id) is None:
            rows.append((LegacyProviderInventory(adapter_id, "default", False, "ADAPTER_UNAVAILABLE"), None))
            continue
        if adapter_id in {"search.auto", "search.native"}:
            rows.append((LegacyProviderInventory(adapter_id, "default", False, "REVIEW_REQUIRED"), None))
            continue
        model_field = MODEL_FIELDS.get(family, {}).get(provider)
        model = str(config.get(model_field) or "default") if model_field else "default"
        secret_field = SECRET_FIELDS.get(adapter_id)
        secret = str(config.get(secret_field) or "") if secret_field else ""
        components = {
            target: str(config[source])
            for source, target in SECRET_COMPONENT_FIELDS.get(adapter_id, {}).items()
            if config.get(source) is not None and config.get(source) != ""
        }
        if components:
            secret = json.dumps(components, sort_keys=True, separators=(",", ":"))
        safe_config = {
            target: config[source]
            for source, target in SAFE_CONFIG_FIELDS.get(adapter_id, {}).items()
            if config.get(source) is not None and config.get(source) != ""
        }
        rows.append((LegacyProviderInventory(adapter_id, model, bool(secret), "READY", safe_config=safe_config), secret or None))
    # Plaintext settings for non-selected providers remain a deliberate
    # rollback source.  They are reported, never silently copied or deleted,
    # because the intended workspace/provider binding is ambiguous.
    credential_adapters = set(SECRET_FIELDS) | set(SECRET_COMPONENT_FIELDS)
    for adapter_id in sorted(credential_adapters - selected_adapter_ids):
        direct = SECRET_FIELDS.get(adapter_id)
        present = bool(direct and config.get(direct)) or any(
            config.get(source)
            for source in SECRET_COMPONENT_FIELDS.get(adapter_id, {})
        )
        if present:
            rows.append((LegacyProviderInventory(
                adapter_id, "default", True, "ROLLBACK_ONLY",
            ), None))
    return rows


async def migrate_legacy_provider_settings(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    apply: bool = False,
    keys: MasterKeyProvider | None = None,
) -> list[LegacyProviderInventory]:
    legacy = await session.get(ProviderSettings, 1)
    inventory = inventory_legacy_provider_settings(dict(legacy.config or {}) if legacy else {})
    if not apply:
        return [item for item, _ in inventory]
    results: list[LegacyProviderInventory] = []
    for item, secret in inventory:
        if item.status != "READY":
            results.append(item)
            continue
        name = f"Legacy {item.adapter_id}"
        account = await session.scalar(select(ProviderAccountModel).where(
            ProviderAccountModel.workspace_id == workspace_id,
            ProviderAccountModel.name == name,
        ))
        if account is None:
            account = await create_provider_account(
                session, workspace_id=workspace_id, actor_id=actor_id,
                adapter_id=item.adapter_id, name=name, default_model=item.model,
                safe_config={"legacySettingsId": 1, "compatibilityMapping": True, **(item.safe_config or {})},
                region_policy_status=RegionPolicyStatus.ADMIN_REVIEW,
                capability_models=[item.model],
            )
        elif account.adapter_id != item.adapter_id or account.default_model != item.model:
            results.append(LegacyProviderInventory(
                item.adapter_id, item.model, item.has_secret, "CONFLICT", account.id, item.safe_config,
            ))
            continue
        if secret:
            verified = await resolve_provider_secret(session, account_id=account.id, keys=keys)
            if verified != secret:
                await rotate_provider_secret(
                    session, account_id=account.id, workspace_id=workspace_id,
                    name="api_key", plaintext=secret, keys=keys,
                )
                verified = await resolve_provider_secret(session, account_id=account.id, keys=keys)
            if verified != secret:
                raise RuntimeError("Encrypted provider import verification failed")
            append_audit_event(
                session, workspace_id=workspace_id, actor_id=actor_id,
                event_type="provider.secret.migrated", subject_type="provider_account", subject_id=account.id,
            )
        results.append(LegacyProviderInventory(item.adapter_id, item.model, item.has_secret, "VERIFIED", account.id, item.safe_config))
    await session.commit()
    # ProviderSettings remains untouched as the explicit rollback source.
    return results

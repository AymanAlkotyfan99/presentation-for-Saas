from __future__ import annotations

import os
from functools import lru_cache

from modules.assets.providers.storage.local import LocalStorageProvider
from modules.assets.providers.storage.s3 import S3CompatibleStorageProvider
from utils.get_env import get_app_data_directory_env


def _s3_encryption() -> str | None:
    value = os.getenv("OBJECT_STORAGE_S3_ENCRYPTION", "AES256").strip()
    if value.lower() in {"", "none", "disabled", "false"}:
        return None
    return value


@lru_cache(maxsize=4)
def get_storage_provider(provider_id: str | None = None):
    selected = (provider_id or os.getenv("OBJECT_STORAGE_PROVIDER", "local")).strip().lower()
    if selected == "local":
        root = os.getenv("OBJECT_STORAGE_LOCAL_ROOT") or os.path.join(get_app_data_directory_env(), "object-storage")
        return LocalStorageProvider(root)
    if selected == "s3":
        return S3CompatibleStorageProvider(
            bucket=os.environ["OBJECT_STORAGE_S3_BUCKET"],
            endpoint_url=os.getenv("OBJECT_STORAGE_S3_ENDPOINT"),
            region_name=os.getenv("OBJECT_STORAGE_S3_REGION"),
            access_key_id=os.getenv("OBJECT_STORAGE_S3_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("OBJECT_STORAGE_S3_SECRET_ACCESS_KEY"),
            use_ssl=os.getenv("OBJECT_STORAGE_S3_USE_SSL", "true").lower() == "true",
            encryption=_s3_encryption(),
            addressing_style=os.getenv("OBJECT_STORAGE_S3_ADDRESSING_STYLE", "auto").strip().lower(),
        )
    raise ValueError(f"Unknown storage provider: {selected}")

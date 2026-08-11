from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    size: int
    checksum_sha256: str | None
    content_type: str | None
    etag: str | None = None


@dataclass(frozen=True)
class MultipartUpload:
    upload_id: str
    key: str


@dataclass(frozen=True)
class PresignedRequest:
    url: str
    method: str
    expires_at: datetime
    headers: dict[str, str]


class StorageProvider(Protocol):
    provider_id: str

    async def health(self) -> bool: ...
    async def put_bytes(self, key: str, data: bytes, *, content_type: str, checksum_sha256: str) -> ObjectMetadata: ...
    async def begin_upload(self, key: str, *, content_type: str) -> MultipartUpload: ...
    async def upload_part(self, upload: MultipartUpload, part_number: int, data: bytes) -> str: ...
    async def complete_upload(self, upload: MultipartUpload, parts: list[tuple[int, str]]) -> ObjectMetadata: ...
    async def abort_upload(self, upload: MultipartUpload) -> None: ...
    async def head(self, key: str) -> ObjectMetadata: ...
    async def open(self, key: str) -> BinaryIO: ...
    async def delete(self, key: str) -> None: ...
    async def copy(self, source_key: str, destination_key: str) -> ObjectMetadata: ...
    async def presign_upload(self, key: str, *, content_type: str, expires_seconds: int) -> PresignedRequest: ...
    async def presign_download(self, key: str, *, expires_seconds: int) -> PresignedRequest: ...

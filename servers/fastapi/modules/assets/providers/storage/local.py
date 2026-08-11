"""Traversal- and symlink-safe local development storage adapter."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import shutil
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from modules.assets.providers.storage.base import MultipartUpload, ObjectMetadata, PresignedRequest
from utils.datetime_utils import get_current_utc_datetime


_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class LocalStorageProvider:
    provider_id = "local"

    def __init__(self, root: str, *, api_prefix: str = "/api/v1/assets/local") -> None:
        self.root = os.path.realpath(os.path.abspath(root))
        self.api_prefix = api_prefix.rstrip("/")
        os.makedirs(self.root, exist_ok=True)
        if os.path.islink(self.root):
            raise ValueError("Local object storage root may not be a symlink")

    def _resolve(self, key: str, *, allow_missing: bool = True) -> str:
        if not isinstance(key, str) or not key or "\\" in key or key.startswith("/"):
            raise ValueError("Invalid storage key")
        parts = key.split("/")
        if any(not _SEGMENT.fullmatch(part) or part in {".", ".."} for part in parts):
            raise ValueError("Invalid storage key")
        candidate = os.path.abspath(os.path.join(self.root, *parts))
        if os.path.commonpath([self.root, candidate]) != self.root:
            raise ValueError("Storage key escapes its root")
        cursor = self.root
        for part in parts[:-1] if allow_missing else parts:
            cursor = os.path.join(cursor, part)
            if os.path.lexists(cursor) and os.path.islink(cursor):
                raise ValueError("Storage key traverses a symlink")
        if not allow_missing and (not os.path.isfile(candidate) or os.path.islink(candidate)):
            raise FileNotFoundError(key)
        return candidate

    @staticmethod
    def _metadata(key: str, path: str, content_type: str | None = None) -> ObjectMetadata:
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        return ObjectMetadata(key, os.path.getsize(path), checksum, content_type, checksum)

    async def health(self) -> bool:
        return os.path.isdir(self.root) and os.access(self.root, os.R_OK | os.W_OK)

    async def put_bytes(self, key: str, data: bytes, *, content_type: str, checksum_sha256: str) -> ObjectMetadata:
        if hashlib.sha256(data).hexdigest() != checksum_sha256:
            raise ValueError("Object checksum mismatch")
        path = self._resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if any(os.path.islink(parent) for parent in Path(path).parents if str(parent).startswith(self.root) and str(parent) != self.root):
            raise ValueError("Storage path contains a symlink")
        temporary = f"{path}.upload-{uuid4().hex}"
        try:
            with open(temporary, "xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return self._metadata(key, path, content_type)

    async def begin_upload(self, key: str, *, content_type: str) -> MultipartUpload:
        self._resolve(key)
        upload_id = uuid4().hex
        staging = self._resolve(f"multipart/{upload_id}/metadata")
        os.makedirs(os.path.dirname(staging), exist_ok=False)
        with open(staging, "x", encoding="utf-8") as stream:
            stream.write(f"{key}\n{content_type}")
        return MultipartUpload(upload_id, key)

    def _upload_dir(self, upload: MultipartUpload) -> str:
        directory = self._resolve(f"multipart/{upload.upload_id}/metadata", allow_missing=False)
        with open(directory, "r", encoding="utf-8") as stream:
            recorded_key = stream.readline().rstrip("\n")
        if recorded_key != upload.key:
            raise ValueError("Multipart upload key mismatch")
        return os.path.dirname(directory)

    async def upload_part(self, upload: MultipartUpload, part_number: int, data: bytes) -> str:
        if not 1 <= part_number <= 10000 or not data:
            raise ValueError("Invalid multipart part")
        directory = self._upload_dir(upload)
        digest = hashlib.sha256(data).hexdigest()
        path = os.path.join(directory, f"part-{part_number:05d}")
        with open(path, "xb") as stream:
            stream.write(data)
        return digest

    async def complete_upload(self, upload: MultipartUpload, parts: list[tuple[int, str]]) -> ObjectMetadata:
        directory = self._upload_dir(upload)
        if not parts or [number for number, _ in parts] != sorted({number for number, _ in parts}):
            raise ValueError("Multipart parts are incomplete or unordered")
        destination = self._resolve(upload.key)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        temporary = f"{destination}.upload-{upload.upload_id}"
        try:
            with open(temporary, "xb") as output:
                for number, expected in parts:
                    part_path = os.path.join(directory, f"part-{number:05d}")
                    with open(part_path, "rb") as part:
                        data = part.read()
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError("Multipart part checksum mismatch")
                    output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
            with open(os.path.join(directory, "metadata"), "r", encoding="utf-8") as stream:
                stream.readline()
                content_type = stream.readline().rstrip("\n") or None
            return self._metadata(upload.key, destination, content_type)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
            shutil.rmtree(directory, ignore_errors=True)

    async def abort_upload(self, upload: MultipartUpload) -> None:
        try:
            directory = self._upload_dir(upload)
        except FileNotFoundError:
            return
        shutil.rmtree(directory, ignore_errors=True)

    async def head(self, key: str) -> ObjectMetadata:
        return self._metadata(key, self._resolve(key, allow_missing=False))

    async def open(self, key: str):
        return open(self._resolve(key, allow_missing=False), "rb")

    async def delete(self, key: str) -> None:
        path = self._resolve(key, allow_missing=False)
        os.remove(path)

    async def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        source = self._resolve(source_key, allow_missing=False)
        destination = self._resolve(destination_key)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.exists(destination):
            raise FileExistsError(destination_key)
        shutil.copyfile(source, destination)
        return self._metadata(destination_key, destination)

    async def presign_upload(self, key: str, *, content_type: str, expires_seconds: int) -> PresignedRequest:
        self._resolve(key)
        expires = get_current_utc_datetime() + timedelta(seconds=max(1, min(expires_seconds, 900)))
        return PresignedRequest(f"{self.api_prefix}/upload/{key}", "PUT", expires, {"Content-Type": content_type})

    async def presign_download(self, key: str, *, expires_seconds: int) -> PresignedRequest:
        self._resolve(key, allow_missing=False)
        expires = get_current_utc_datetime() + timedelta(seconds=max(1, min(expires_seconds, 900)))
        return PresignedRequest(f"{self.api_prefix}/download/{key}", "GET", expires, {})

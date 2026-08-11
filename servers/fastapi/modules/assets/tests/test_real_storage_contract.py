"""Storage contract coverage against disposable local disk and real MinIO."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from modules.assets.providers.storage.local import LocalStorageProvider
from modules.assets.providers.storage.s3 import S3CompatibleStorageProvider


def _run(coro):
    if sys.platform != "win32":
        return asyncio.run(coro)
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _minio_provider() -> S3CompatibleStorageProvider:
    endpoint = os.getenv("OBJECT_STORAGE_S3_ENDPOINT", "")
    if not endpoint.startswith(("http://localhost", "http://127.0.0.1")):
        pytest.skip("OBJECT_STORAGE_S3_ENDPOINT does not identify disposable local MinIO")
    return S3CompatibleStorageProvider(
        bucket=os.environ["OBJECT_STORAGE_S3_BUCKET"],
        endpoint_url=endpoint,
        region_name=os.getenv("OBJECT_STORAGE_S3_REGION", "us-east-1"),
        access_key_id=os.environ["OBJECT_STORAGE_S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["OBJECT_STORAGE_S3_SECRET_ACCESS_KEY"],
        use_ssl=False,
        encryption=(
            None
            if os.getenv("OBJECT_STORAGE_S3_ENCRYPTION", "AES256").lower()
            in {"", "none", "disabled", "false"}
            else os.getenv("OBJECT_STORAGE_S3_ENCRYPTION", "AES256")
        ),
        addressing_style="path",
    )


async def _contract(provider, prefix: str) -> None:
    source_key = f"{prefix}/source.bin"
    copy_key = f"{prefix}/copy.bin"
    data = b"Bayanly storage contract\x00\x01"
    checksum = hashlib.sha256(data).hexdigest()
    assert await provider.health()
    metadata = await provider.put_bytes(
        source_key,
        data,
        content_type="application/octet-stream",
        checksum_sha256=checksum,
    )
    assert metadata.key == source_key
    assert metadata.size == len(data)
    assert metadata.checksum_sha256 == checksum
    assert (await provider.open(source_key)).read() == data
    copied = await provider.copy(source_key, copy_key)
    assert copied.size == len(data)
    assert copied.checksum_sha256 == checksum
    assert (await provider.open(copy_key)).read() == data
    await provider.delete(copy_key)
    await provider.delete(source_key)


def test_local_and_real_minio_storage_contract(tmp_path: Path):
    async def scenario():
        await _contract(LocalStorageProvider(tmp_path / "objects"), f"local/{uuid4()}")
        await _contract(_minio_provider(), f"contract/{uuid4()}")

    _run(scenario())


def test_real_minio_multipart_resume_abort_and_presigned_security():
    async def scenario():
        provider = _minio_provider()
        prefix = f"multipart/{uuid4()}"
        complete_key = f"{prefix}/complete.bin"
        aborted_key = f"{prefix}/aborted.bin"
        presigned_key = f"{prefix}/presigned.bin"
        first = b"a" * (5 * 1024 * 1024)
        second = b"b" * (1024 * 1024 + 17)
        upload = await provider.begin_upload(
            complete_key,
            content_type="application/octet-stream",
        )
        first_etag = await provider.upload_part(upload, 1, first)
        # A later call using the durable upload ID is the supported resume path.
        second_etag = await provider.upload_part(upload, 2, second)
        completed = await provider.complete_upload(
            upload,
            [(1, first_etag), (2, second_etag)],
        )
        assert completed.key == complete_key
        assert completed.size == len(first) + len(second)
        assert hashlib.sha256((await provider.open(complete_key)).read()).hexdigest() == hashlib.sha256(first + second).hexdigest()

        interrupted = await provider.begin_upload(
            aborted_key,
            content_type="application/octet-stream",
        )
        await provider.upload_part(interrupted, 1, first)
        await provider.abort_upload(interrupted)
        with pytest.raises(ClientError):
            await provider.head(aborted_key)

        body = b"presigned private object"
        upload_request = await provider.presign_upload(
            presigned_key,
            content_type="application/octet-stream",
            expires_seconds=30,
        )

        def put_presigned():
            request = urllib.request.Request(
                upload_request.url,
                data=body,
                method="PUT",
                headers=upload_request.headers,
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status

        assert await asyncio.to_thread(put_presigned) == 200
        assert (await provider.open(presigned_key)).read() == body
        download_request = await provider.presign_download(
            presigned_key,
            expires_seconds=1,
        )

        def get_url(url: str):
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status, response.read()

        assert await asyncio.to_thread(get_url, download_request.url) == (200, body)
        tampered = download_request.url[:-1] + ("0" if download_request.url[-1] != "0" else "1")
        with pytest.raises(urllib.error.HTTPError) as tampered_error:
            await asyncio.to_thread(get_url, tampered)
        assert tampered_error.value.code == 403
        await asyncio.sleep(2.05)
        with pytest.raises(urllib.error.HTTPError) as expired_error:
            await asyncio.to_thread(get_url, download_request.url)
        assert expired_error.value.code == 403
        unauthenticated = f"{os.environ['OBJECT_STORAGE_S3_ENDPOINT']}/{provider.bucket}/{presigned_key}"
        with pytest.raises(urllib.error.HTTPError) as private_error:
            await asyncio.to_thread(get_url, unauthenticated)
        assert private_error.value.code == 403

        await provider.delete(complete_key)
        await provider.delete(presigned_key)

    _run(scenario())

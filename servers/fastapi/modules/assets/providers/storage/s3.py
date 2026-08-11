"""Private standard S3-compatible object storage adapter."""

from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import timedelta

from modules.assets.providers.storage.base import MultipartUpload, ObjectMetadata, PresignedRequest
from utils.datetime_utils import get_current_utc_datetime


class S3CompatibleStorageProvider:
    provider_id = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        use_ssl: bool = True,
        encryption: str | None = "AES256",
        addressing_style: str = "auto",
    ) -> None:
        import boto3
        from botocore.config import Config

        if not bucket:
            raise ValueError("S3 storage requires a private bucket")
        if not use_ssl and not (endpoint_url or "").startswith(("http://localhost", "http://127.0.0.1")):
            raise ValueError("S3 storage requires TLS outside localhost")
        if addressing_style not in {"auto", "path", "virtual"}:
            raise ValueError("S3 addressing style must be auto, path, or virtual")
        self.bucket = bucket
        self.encryption = encryption
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            use_ssl=use_ssl,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 1, "mode": "standard"},
                s3={"addressing_style": addressing_style},
            ),
        )

    def _encryption(self) -> dict:
        return {"ServerSideEncryption": self.encryption} if self.encryption else {}

    async def health(self) -> bool:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.bucket)
            return True
        except Exception:
            return False

    async def put_bytes(self, key: str, data: bytes, *, content_type: str, checksum_sha256: str) -> ObjectMetadata:
        if hashlib.sha256(data).hexdigest() != checksum_sha256:
            raise ValueError("Object checksum mismatch")
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": checksum_sha256},
            **self._encryption(),
        )
        return await self.head(key)

    async def begin_upload(self, key: str, *, content_type: str) -> MultipartUpload:
        response = await asyncio.to_thread(
            self.client.create_multipart_upload,
            Bucket=self.bucket,
            Key=key,
            ContentType=content_type,
            **self._encryption(),
        )
        return MultipartUpload(response["UploadId"], key)

    async def upload_part(self, upload: MultipartUpload, part_number: int, data: bytes) -> str:
        response = await asyncio.to_thread(
            self.client.upload_part,
            Bucket=self.bucket,
            Key=upload.key,
            UploadId=upload.upload_id,
            PartNumber=part_number,
            Body=data,
        )
        return str(response["ETag"])

    async def complete_upload(self, upload: MultipartUpload, parts: list[tuple[int, str]]) -> ObjectMetadata:
        await asyncio.to_thread(
            self.client.complete_multipart_upload,
            Bucket=self.bucket,
            Key=upload.key,
            UploadId=upload.upload_id,
            MultipartUpload={"Parts": [{"PartNumber": number, "ETag": etag} for number, etag in parts]},
        )
        return await self.head(upload.key)

    async def abort_upload(self, upload: MultipartUpload) -> None:
        await asyncio.to_thread(self.client.abort_multipart_upload, Bucket=self.bucket, Key=upload.key, UploadId=upload.upload_id)

    async def head(self, key: str) -> ObjectMetadata:
        response = await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
        checksum = (response.get("Metadata") or {}).get("sha256")
        return ObjectMetadata(key, int(response["ContentLength"]), checksum, response.get("ContentType"), response.get("ETag"))

    async def open(self, key: str):
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        data = await asyncio.to_thread(response["Body"].read)
        return io.BytesIO(data)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        await asyncio.to_thread(
            self.client.copy_object,
            Bucket=self.bucket,
            Key=destination_key,
            CopySource={"Bucket": self.bucket, "Key": source_key},
            MetadataDirective="COPY",
            **self._encryption(),
        )
        return await self.head(destination_key)

    async def presign_upload(self, key: str, *, content_type: str, expires_seconds: int) -> PresignedRequest:
        expires_seconds = max(1, min(expires_seconds, 900))
        params = {"Bucket": self.bucket, "Key": key, "ContentType": content_type, **self._encryption()}
        url = await asyncio.to_thread(self.client.generate_presigned_url, "put_object", Params=params, ExpiresIn=expires_seconds, HttpMethod="PUT")
        headers = {"Content-Type": content_type}
        if self.encryption:
            headers["x-amz-server-side-encryption"] = self.encryption
        return PresignedRequest(
            url,
            "PUT",
            get_current_utc_datetime() + timedelta(seconds=expires_seconds),
            headers,
        )

    async def presign_download(self, key: str, *, expires_seconds: int) -> PresignedRequest:
        expires_seconds = max(1, min(expires_seconds, 900))
        url = await asyncio.to_thread(self.client.generate_presigned_url, "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_seconds, HttpMethod="GET")
        return PresignedRequest(url, "GET", get_current_utc_datetime() + timedelta(seconds=expires_seconds), {})

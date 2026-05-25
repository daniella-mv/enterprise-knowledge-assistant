"""Object storage adapter (S3-compatible).

Wraps boto3 so callers can put/get/delete/sign objects without dealing
with endpoint, signature version, or addressing style directly. Works
against AWS S3 (s3_endpoint_url unset), MinIO, or LocalStack by
swapping a single config value.

The boto3 client is synchronous. Async callers should wrap calls with
asyncio.to_thread() so the event loop isn't blocked.
"""

from __future__ import annotations

from functools import cache
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageError(AppError):
    code = "storage_error"
    status_code = 502


@cache
def _client():
    """Cached boto3 S3 client. Created once per process (clients are thread-safe)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(
            signature_version="s3v4",
            # MinIO and most S3-compatible stores require path-style addressing
            # (https://endpoint/bucket/key). Real AWS S3 supports both.
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def ensure_bucket(bucket: str | None = None) -> None:
    """Create the bucket if it doesn't already exist. Idempotent.

    Called once at API startup. Safe to invoke repeatedly — does nothing
    if the bucket is already present.
    """
    bucket = bucket or settings.s3_bucket
    client = _client()
    try:
        client.head_bucket(Bucket=bucket)
        logger.info("bucket_exists", bucket=bucket)
        return
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        # Bucket missing -> create. Anything else -> bubble up.
        if code not in ("404", "NoSuchBucket", "NotFound"):
            raise StorageError(f"head_bucket failed for {bucket}: {e}") from e

    try:
        client.create_bucket(Bucket=bucket)
        logger.info("bucket_created", bucket=bucket)
    except ClientError as e:
        # Race: another process created it between our head + create.
        if e.response.get("Error", {}).get("Code") == "BucketAlreadyOwnedByYou":
            logger.info("bucket_already_owned", bucket=bucket)
            return
        raise StorageError(f"create_bucket failed for {bucket}: {e}") from e


def put_object(
    key: str,
    data: bytes | BinaryIO,
    *,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload bytes (or a file-like object) under `key`."""
    body = data if isinstance(data, bytes) else data.read()
    try:
        _client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    except ClientError as e:
        raise StorageError(f"put_object failed for {key}: {e}") from e


def get_object(key: str) -> bytes:
    """Download an object's bytes."""
    try:
        resp = _client().get_object(Bucket=settings.s3_bucket, Key=key)
        return resp["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise StorageError(f"object not found: {key}", code="not_found") from e
        raise StorageError(f"get_object failed for {key}: {e}") from e


def delete_object(key: str) -> None:
    try:
        _client().delete_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError as e:
        raise StorageError(f"delete_object failed for {key}: {e}") from e


def object_exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def generate_presigned_url(
    key: str,
    *,
    expires_in: int = 900,
    method: str = "get_object",
) -> str:
    """Time-limited URL the browser can use without auth.

    method is a boto3 client method name: typically `get_object` (download)
    or `put_object` (direct browser upload).
    """
    try:
        return _client().generate_presigned_url(
            ClientMethod=method,
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise StorageError(f"presigned url failed for {key}: {e}") from e

"""Cloudflare R2 storage (S3-compatible API) behind a public bucket URL.

Objects get unguessable uuid4 keys and are served from R2_PUBLIC_BASE_URL. URLs never
expire: Buffer fetches the image again at publish time, which may be weeks away.
"""

import uuid
from functools import lru_cache

import boto3

from app.config import get_settings

EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}


@lru_cache
def _s3():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
    )


def public_url(key: str) -> str:
    return f"{get_settings().r2_public_base_url.rstrip('/')}/{key}"


def upload(data: bytes, content_type: str) -> tuple[str, str]:
    """Store `data` and return (object_key, public_url)."""
    ext = EXTENSIONS.get(content_type)
    if ext is None:
        raise ValueError(f"unsupported content type: {content_type}")
    key = f"{uuid.uuid4()}.{ext}"
    _s3().put_object(Bucket=get_settings().r2_bucket, Key=key, Body=data, ContentType=content_type)
    return key, public_url(key)


def delete(key: str) -> None:
    _s3().delete_object(Bucket=get_settings().r2_bucket, Key=key)

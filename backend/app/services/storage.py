"""
Cyrus — Storage Service

Abstraction layer over MinIO (self-hosted) or Supabase Storage (cloud).
The rest of the app never imports boto3 or minio directly — always uses this.
Swapping storage backends requires changing only this file.
"""

import io
from app.config import get_settings

settings = get_settings()


async def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload bytes to object storage and return the public URL.

    Args:
        key: Storage path, e.g. "submissions/exam_id/student_slug/page_001.jpg"
        data: Raw file bytes
        content_type: MIME type

    Returns:
        Public URL to access the file
    """
    from minio import Minio
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    scheme = "https" if settings.minio_secure else "http"
    return f"{scheme}://{settings.minio_endpoint}/{settings.minio_bucket}/{key}"


async def download_file(key: str) -> bytes:
    """Download a file from object storage by its key."""
    from minio import Minio
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    response = client.get_object(settings.minio_bucket, key)
    return response.read()


async def ensure_bucket_exists() -> None:
    """Create the bucket if it doesn't exist. Called on startup."""
    from minio import Minio
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def key_from_url(url: str) -> str:
    """Extract the storage key from a full URL."""
    # e.g. http://localhost:9000/cyrus-files/submissions/... → submissions/...
    parts = url.split(f"/{settings.minio_bucket}/", 1)
    return parts[1] if len(parts) > 1 else url

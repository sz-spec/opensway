"""Storage abstraction: local filesystem or MinIO/S3."""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "./outputs"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000/outputs")


def _ensure_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_bytes(data: bytes, filename: str) -> str:
    """Save raw bytes and return a public URL."""
    if STORAGE_BACKEND == "local":
        return _save_local(data, filename)
    elif STORAGE_BACKEND in ("minio", "s3"):
        return _save_s3(data, filename)
    raise ValueError(f"Unknown storage backend: {STORAGE_BACKEND}")


def save_file(src_path: str, filename: str) -> str:
    """Copy a file to storage and return a public URL."""
    with open(src_path, "rb") as f:
        return save_bytes(f.read(), filename)


def _save_local(data: bytes, filename: str) -> str:
    _ensure_dir()
    dest = OUTPUT_DIR / filename
    dest.write_bytes(data)
    return f"{PUBLIC_BASE_URL}/{filename}"


def _save_s3(data: bytes, filename: str) -> str:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
    )
    bucket = os.environ.get("MINIO_BUCKET", "opensway")
    s3.put_object(Bucket=bucket, Key=filename, Body=data)
    base = os.environ.get("PUBLIC_BASE_URL", f"http://localhost:9000/{bucket}")
    return f"{base}/{filename}"


def generate_upload_slot(filename: str) -> dict:
    """Return upload metadata for POST /v1/uploads."""
    file_id = str(uuid.uuid4())
    ext = Path(filename).suffix
    stored_name = f"uploads/{file_id}{ext}"
    runway_uri = f"opensway://uploads/{file_id}{ext}"

    if STORAGE_BACKEND == "local":
        upload_url = f"{PUBLIC_BASE_URL.replace('/outputs', '')}/v1/uploads/{file_id}{ext}"
        return {
            "id": file_id,
            "uploadUrl": upload_url,
            "fields": {},
            "runwayUri": runway_uri,
        }

    # For MinIO/S3: generate presigned POST
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
    )
    bucket = os.environ.get("MINIO_BUCKET", "opensway")
    resp = s3.generate_presigned_post(bucket, stored_name, ExpiresIn=3600)
    return {
        "id": file_id,
        "uploadUrl": resp["url"],
        "fields": resp["fields"],
        "runwayUri": runway_uri,
    }

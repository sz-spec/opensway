"""POST /v1/uploads — file upload slot generation."""
from fastapi import APIRouter, Depends
from api.auth import get_current_key
from api.models.schemas import UploadRequest, UploadResponse
from storage.minio_client import generate_upload_slot

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
def create_upload(
    body: UploadRequest,
    api_key=Depends(get_current_key),
):
    slot = generate_upload_slot(body.filename)
    return UploadResponse(**slot)

"""Admin endpoints for key management (not Runway-compatible, internal use)."""
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import ApiKey

router = APIRouter(prefix="/v1/admin", tags=["admin"])

ADMIN_SECRET = None  # Set ADMIN_SECRET env var to protect these endpoints


def _check_admin(secret: str = ""):
    import os
    expected = os.environ.get("ADMIN_SECRET", "")
    if expected and secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


class CreateKeyRequest(BaseModel):
    name: str = "default"
    credit_balance: int = 10000
    admin_secret: str = ""


class CreateKeyResponse(BaseModel):
    key: str
    id: str
    name: str
    credit_balance: int


@router.post("/keys", response_model=CreateKeyResponse)
def create_key(body: CreateKeyRequest, db: Session = Depends(get_db)):
    _check_admin(body.admin_secret)
    raw = "key_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    api_key = ApiKey(
        key_hash=key_hash,
        name=body.name,
        credit_balance=body.credit_balance,
        tier={
            "maxMonthlyCreditSpend": 100000,
            "models": {},
        },
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return CreateKeyResponse(
        key=raw,
        id=str(api_key.id),
        name=body.name,
        credit_balance=api_key.credit_balance,
    )


@router.get("/keys")
def list_keys(db: Session = Depends(get_db)):
    keys = db.query(ApiKey).all()
    return [{"id": str(k.id), "name": k.name, "credit_balance": k.credit_balance,
             "is_active": k.is_active, "created_at": str(k.created_at)} for k in keys]

import hashlib
import secrets
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import ApiKey

bearer_scheme = HTTPBearer()
bearer_scheme_optional = HTTPBearer(auto_error=False)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> str:
    return "key_" + secrets.token_hex(32)


def get_current_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> ApiKey:
    raw_key = credentials.credentials
    key_hash = hash_key(raw_key)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == "active",
    ).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def get_optional_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[ApiKey]:
    if not credentials:
        return None
    raw_key = credentials.credentials
    key_hash = hash_key(raw_key)
    return db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == "active",
    ).first()


def require_credits(min_credits: int = 1):
    def checker(api_key: ApiKey = Depends(get_current_key)):
        if api_key.credit_balance < min_credits:
            raise HTTPException(
                status_code=402,
                detail="You do not have enough credits to run this task."
            )
        return api_key
    return checker

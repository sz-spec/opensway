"""GET /v1/organization — account info + credit balance"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from api.auth import get_current_key

router = APIRouter(prefix="/v1/organization", tags=["organization"])


@router.get("")
def get_organization(
    db: Session = Depends(get_db),
    api_key=Depends(get_current_key),
):
    return {
        "creditBalance": api_key.credit_balance,
        "tier": api_key.tier or {
            "maxMonthlyCreditSpend": 10000,
            "models": {}
        },
    }

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.market_regime import market_regime

router = APIRouter(prefix="/market-regime", tags=["Market Regime"])


@router.get("")
def get_market_regime(db: Session = Depends(get_db)):
    return market_regime(db)

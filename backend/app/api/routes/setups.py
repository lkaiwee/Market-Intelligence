from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.setup_scanner import scan_universe

router = APIRouter(prefix="/setups", tags=["Technical setups"])


@router.get("")
def setups(setup: Literal["ALL", "BREAKOUT", "PULLBACK", "SQUEEZE", "REVERSAL"] = "ALL",
           matches_only: bool = True, db: Session = Depends(get_db)):
    return scan_universe(db, setup, matches_only)

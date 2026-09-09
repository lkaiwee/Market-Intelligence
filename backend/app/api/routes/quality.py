import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.earnings_quality import quality_report, refresh_statement_cache, validate_ticker

router = APIRouter(prefix="/quality", tags=["Earnings quality"])


@router.get("/{ticker}")
def get_quality(ticker: str, db: Session = Depends(get_db)):
    try:
        return quality_report(db, ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{ticker}/refresh")
async def refresh_quality(ticker: str, db: Session = Depends(get_db)):
    try:
        ticker = validate_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        await refresh_statement_cache(db, ticker)
        return quality_report(db, ticker)
    except asyncio.TimeoutError as exc:
        db.rollback()
        raise HTTPException(504, "Statement provider timed out. The previous cache is still available; retry later.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, "Could not refresh annual statements from Yahoo. The previous cache is still available; retry later or choose another ticker.") from exc

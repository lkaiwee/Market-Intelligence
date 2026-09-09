from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.backtesting import BacktestRequest, run_backtest

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


@router.post("")
def backtest(request: BacktestRequest, db: Session = Depends(get_db)):
    try:
        return run_backtest(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

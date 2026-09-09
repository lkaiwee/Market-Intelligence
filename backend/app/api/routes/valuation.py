from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.valuation_engine import ValuationInputs, calculate_valuation, valuation_context

router = APIRouter(prefix="/valuation", tags=["Valuation"])


@router.get("/{ticker}")
def get_valuation(ticker: str, db: Session = Depends(get_db)):
    try:
        return calculate_valuation(valuation_context(db, ticker), ValuationInputs())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{ticker}")
def model_valuation(ticker: str, inputs: ValuationInputs, db: Session = Depends(get_db)):
    try:
        return calculate_valuation(valuation_context(db, ticker), inputs)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

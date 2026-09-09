from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.portfolio_risk import analyze_risk, size_position

router = APIRouter(prefix="/risk", tags=["Portfolio Risk"])
Positive = Annotated[float, Field(ge=0.000001, le=1e15)]


class RiskRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    cash: float | None = Field(default=None, ge=0, le=1e15)
    account_equity: Positive | None = None
    stops: dict[str, Positive] = Field(default_factory=dict, max_length=200)
    use_atr: bool = True
    atr_multiplier: float = Field(default=2, ge=0.1, le=10)

    @field_validator("stops")
    @classmethod
    def normalize_stops(cls, value):
        return {ticker.strip().upper(): stop for ticker, stop in value.items()}


class SizeRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    side: Literal["long", "short"] = "long"
    entry: Positive
    stop: Positive
    account_equity: Positive
    risk_pct: float = Field(gt=0, le=100)
    max_allocation_pct: float = Field(gt=0, le=100)
    available_cash: float | None = Field(default=None, ge=0, le=1e15)
    fractional: bool = False
    fee_budget: float = Field(default=0, ge=0, le=1e12)


@router.post("/analyze")
def portfolio_risk(payload: RiskRequest, db: Session = Depends(get_db)):
    try:
        return analyze_risk(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/size")
def position_size(payload: SizeRequest):
    try:
        return size_position(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.portfolio_stress import analyze_stress

router = APIRouter(prefix="/stress", tags=["Portfolio Stress Testing"])
Shock = Annotated[float, Field(ge=-100, le=300)]


class StressRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    lookback: int = Field(default=252, ge=60, le=504)
    confidence: float = Field(default=0.95, ge=0.90, le=0.99)
    market_shock_pct: Shock = -10
    mode: Literal["uniform", "beta"] = "uniform"
    shocks: dict[str, Shock] = Field(default_factory=dict, max_length=200)
    cash: float | None = Field(default=None, ge=0, le=1e15)

    @field_validator("shocks")
    @classmethod
    def normalize_shocks(cls, value):
        return {ticker.strip().upper(): shock for ticker, shock in value.items()}


@router.post("/analyze")
def portfolio_stress(payload: StressRequest, db: Session = Depends(get_db)):
    try:
        return analyze_stress(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

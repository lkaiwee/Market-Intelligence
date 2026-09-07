from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_universe import CustomUniverseStock
from app.providers.yahoo_fundamentals import YahooFundamentalsError, YahooFundamentalsProvider
from app.services.blue_chip_universe import BLUE_CHIP_UNIVERSE
from app.services.universe_registry import custom_universe, merged_universe

router = APIRouter(prefix="/universe", tags=["Stock Universe"])


class UniverseStockCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    screening_enabled: bool = True
    earnings_enabled: bool = True
    earnings_impact_score: int = Field(default=7, ge=1, le=10)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class UniverseStockUpdate(BaseModel):
    screening_enabled: bool | None = None
    earnings_enabled: bool | None = None
    earnings_impact_score: int | None = Field(default=None, ge=1, le=10)


@router.get("/stocks")
def list_universe_stocks(
    include_core: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    registry = merged_universe(db) if include_core else custom_universe(db)
    rows = list(registry.values())
    rows.sort(key=lambda item: (not item["is_core"], item["ticker"]))
    return {"count": len(rows), "stocks": rows}


@router.post("/stocks")
async def add_universe_stock(
    payload: UniverseStockCreate,
    db: Session = Depends(get_db),
):
    ticker = payload.ticker

    if ticker in BLUE_CHIP_UNIVERSE:
        raise HTTPException(
            status_code=409,
            detail=f"{ticker} is already in the built-in blue-chip universe.",
        )

    if db.get(CustomUniverseStock, ticker) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"{ticker} already exists in the custom universe.",
        )

    try:
        info = await YahooFundamentalsProvider().get_company_fundamentals(ticker)
    except YahooFundamentalsError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to validate {ticker} with Yahoo Finance: {exc}",
        ) from exc

    stock = CustomUniverseStock(
        ticker=ticker,
        company_name=info.get("longName") or info.get("shortName") or ticker,
        sector=info.get("sector"),
        industry=info.get("industry"),
        screening_enabled=payload.screening_enabled,
        earnings_enabled=payload.earnings_enabled,
        earnings_impact_score=payload.earnings_impact_score,
        added_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(stock)
    db.commit()
    db.refresh(stock)

    return {
        "ticker": stock.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "industry": stock.industry,
        "screening_enabled": stock.screening_enabled,
        "earnings_enabled": stock.earnings_enabled,
        "earnings_impact_score": stock.earnings_impact_score,
        "is_core": False,
        "message": f"{stock.ticker} added to the custom universe.",
    }


@router.put("/stocks/{ticker}")
def update_universe_stock(
    ticker: str,
    payload: UniverseStockUpdate,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    if ticker in BLUE_CHIP_UNIVERSE:
        raise HTTPException(
            status_code=400,
            detail="Built-in blue-chip stocks cannot be edited here.",
        )

    stock = db.get(CustomUniverseStock, ticker)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker} not found.")

    if payload.screening_enabled is not None:
        stock.screening_enabled = payload.screening_enabled
    if payload.earnings_enabled is not None:
        stock.earnings_enabled = payload.earnings_enabled
    if payload.earnings_impact_score is not None:
        stock.earnings_impact_score = payload.earnings_impact_score

    stock.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(stock)

    return {
        "ticker": stock.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "industry": stock.industry,
        "screening_enabled": stock.screening_enabled,
        "earnings_enabled": stock.earnings_enabled,
        "earnings_impact_score": stock.earnings_impact_score,
        "is_core": False,
    }


@router.delete("/stocks/{ticker}")
def delete_universe_stock(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    if ticker in BLUE_CHIP_UNIVERSE:
        raise HTTPException(
            status_code=400,
            detail="Built-in blue-chip stocks cannot be removed.",
        )

    stock = db.get(CustomUniverseStock, ticker)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker} not found.")

    db.delete(stock)
    db.commit()

    return {
        "ticker": ticker,
        "deleted": True,
        "message": "Universe registration removed. Stored historical data was preserved.",
    }

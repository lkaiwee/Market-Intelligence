from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Stock
from app.models_portfolio import PortfolioPosition
from app.providers.yahoo_finance import YahooFinanceError, YahooFinanceProvider
from app.providers.yahoo_fundamentals import YahooFundamentalsProvider
from app.services.market_data import refresh_ticker
from app.services.portfolio import portfolio_summary, portfolio_tickers

router = APIRouter(prefix="/portfolio", tags=["Portfolio Tracker"])


class PortfolioPositionCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    entry_price: Decimal = Field(gt=0)
    shares: Decimal = Field(gt=0)
    opened_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class PortfolioPositionUpdate(BaseModel):
    entry_price: Decimal | None = Field(default=None, gt=0)
    shares: Decimal | None = Field(default=None, gt=0)
    opened_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.get("")
def get_portfolio(db: Session = Depends(get_db)):
    return portfolio_summary(db)


@router.post("/positions")
async def add_position(
    payload: PortfolioPositionCreate,
    db: Session = Depends(get_db),
):
    ticker = payload.ticker

    if db.get(PortfolioPosition, ticker) is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{ticker} is already in the portfolio. Edit the existing position "
                "to change average entry price or share count."
            ),
        )

    # Refresh first. This both validates that Yahoo has price history and ensures
    # the technical-level engine has enough bars to work with immediately.
    try:
        await refresh_ticker(
            db=db,
            provider=YahooFinanceProvider(),
            ticker=ticker,
        )
    except YahooFinanceError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to validate {ticker} with Yahoo Finance: {exc}",
        ) from exc

    stock = db.get(Stock, ticker)
    if stock is None:
        raise HTTPException(status_code=500, detail=f"Failed to create stock record for {ticker}.")

    # Company metadata is useful but should not prevent portfolio tracking if
    # Yahoo's fundamentals endpoint is temporarily unavailable.
    try:
        info = await YahooFundamentalsProvider().get_company_fundamentals(ticker)
        stock.company_name = info.get("longName") or info.get("shortName") or stock.company_name
        stock.sector = info.get("sector") or stock.sector
        stock.industry = info.get("industry") or stock.industry
    except Exception:
        pass

    position = PortfolioPosition(
        ticker=ticker,
        entry_price=payload.entry_price,
        shares=payload.shares,
        opened_on=payload.opened_on,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(position)
    db.commit()

    return portfolio_summary(db)


@router.put("/positions/{ticker}")
def update_position(
    ticker: str,
    payload: PortfolioPositionUpdate,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()
    position = db.get(PortfolioPosition, ticker)

    if position is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not in the portfolio.")

    if payload.entry_price is not None:
        position.entry_price = payload.entry_price
    if payload.shares is not None:
        position.shares = payload.shares

    # opened_on and notes are intentionally replaceable with null.
    position.opened_on = payload.opened_on
    position.notes = payload.notes
    position.updated_at = datetime.now(timezone.utc)

    db.commit()
    return portfolio_summary(db)


@router.delete("/positions/{ticker}")
def delete_position(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()
    position = db.get(PortfolioPosition, ticker)

    if position is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not in the portfolio.")

    db.delete(position)
    db.commit()

    return {
        "ticker": ticker,
        "deleted": True,
        "message": (
            "Portfolio position removed. Stored market history and screener data were preserved."
        ),
    }


@router.post("/refresh")
async def refresh_portfolio_prices(db: Session = Depends(get_db)):
    tickers = portfolio_tickers(db)
    provider = YahooFinanceProvider()

    refreshed = []
    failures = []

    for ticker in tickers:
        try:
            result = await refresh_ticker(db=db, provider=provider, ticker=ticker)
            refreshed.append(
                {
                    "ticker": ticker,
                    "newest_date": result.newest_date,
                    "bars": result.received,
                }
            )
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})

    return {
        "refreshed": len(refreshed),
        "failed": len(failures),
        "results": refreshed,
        "failures": failures,
        "portfolio": portfolio_summary(db),
    }

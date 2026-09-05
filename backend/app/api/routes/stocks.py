from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyPrice
from app.providers.yahoo_finance import YahooFinanceError, YahooFinanceProvider
from app.schemas import DailyPriceOut, RefreshResult, TechnicalAnalysisOut
from app.services.market_data import refresh_ticker
from app.services.technical_analysis import MIN_ANALYSIS_BARS, build_technical_analysis

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.post("/{ticker}/refresh", response_model=RefreshResult)
async def refresh_stock(
    ticker: str,
    db: Session = Depends(get_db),
):
    try:
        return await refresh_ticker(
            db=db,
            provider=YahooFinanceProvider(),
            ticker=ticker,
        )
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh {ticker.upper()}: {exc}",
        ) from exc


@router.get("/{ticker}/prices", response_model=list[DailyPriceOut])
def get_prices(
    ticker: str,
    limit: int = Query(default=30, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    rows = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.trade_date.desc())
        .limit(limit)
    ).all()

    return list(reversed(rows))


@router.get("/{ticker}/analysis", response_model=TechnicalAnalysisOut)
def get_analysis(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    rows = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.trade_date.asc())
    ).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No stored price data for {ticker}. Run "
                f"POST /api/stocks/{ticker}/refresh first."
            ),
        )

    if len(rows) < MIN_ANALYSIS_BARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {len(rows)} bars are stored for {ticker}; "
                f"at least {MIN_ANALYSIS_BARS} are needed."
            ),
        )

    try:
        return build_technical_analysis(ticker, rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

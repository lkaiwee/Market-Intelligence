from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyPrice, Stock
from app.schemas import TechnicalAnalysisOut
from app.services.blue_chip_universe import universe_rows
from app.services.screener_refresh import refresh_blue_chip_screener
from app.services.technical_analysis import MIN_ANALYSIS_BARS, build_technical_analysis

router = APIRouter(prefix="/screener", tags=["Screener"])


@router.get("", response_model=list[TechnicalAnalysisOut])
def technical_screener(
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    tickers = db.scalars(
        select(Stock.ticker).order_by(Stock.ticker.asc())
    ).all()

    results = []

    for ticker in tickers:
        rows = db.scalars(
            select(DailyPrice)
            .where(DailyPrice.ticker == ticker)
            .order_by(DailyPrice.trade_date.asc())
        ).all()

        if len(rows) < MIN_ANALYSIS_BARS:
            continue

        analysis = build_technical_analysis(ticker, rows)

        if analysis["technical_score"] >= min_score:
            results.append(analysis)

    results.sort(
        key=lambda item: (item["technical_score"], item["ticker"]),
        reverse=True,
    )

    return results[:limit]


@router.get("/universe")
def blue_chip_screener_universe():
    return {
        "count": len(universe_rows()),
        "stocks": universe_rows(),
    }


@router.post("/refresh")
async def refresh_screener(
    force_fundamentals: bool = Query(
        default=False,
        description=(
            "Refresh fundamentals even when the stored snapshot is less than 7 days old."
        ),
    ),
    db: Session = Depends(get_db),
):
    return await refresh_blue_chip_screener(
        db=db,
        force_fundamentals=force_fundamentals,
        fundamentals_max_age_days=7,
    )

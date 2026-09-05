from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyPrice, FundamentalSnapshot, Stock
from app.schemas import InvestmentAnalysisOut
from app.services.investment_analysis import build_investment_analysis
from app.services.technical_analysis import MIN_ANALYSIS_BARS

router = APIRouter(tags=["Investment Analysis"])


@router.get(
    "/stocks/{ticker}/investment-analysis",
    response_model=InvestmentAnalysisOut,
)
def get_investment_analysis(
    ticker: str,
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    stock = db.get(Stock, ticker)
    snapshot = db.get(FundamentalSnapshot, ticker)

    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not stored.")

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fundamentals for {ticker}. Run "
                f"POST /api/stocks/{ticker}/fundamentals/refresh first."
            ),
        )

    prices = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.trade_date.asc())
    ).all()

    if len(prices) < MIN_ANALYSIS_BARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {len(prices)} price bars are stored for {ticker}; "
                f"at least {MIN_ANALYSIS_BARS} are required."
            ),
        )

    return build_investment_analysis(stock, snapshot, prices)


@router.get(
    "/investment-screener",
    response_model=list[InvestmentAnalysisOut],
)
def investment_screener(
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stocks = db.scalars(
        select(Stock).order_by(Stock.ticker.asc())
    ).all()

    results: list[dict] = []

    for stock in stocks:
        snapshot = db.get(FundamentalSnapshot, stock.ticker)
        if snapshot is None:
            continue

        prices = db.scalars(
            select(DailyPrice)
            .where(DailyPrice.ticker == stock.ticker)
            .order_by(DailyPrice.trade_date.asc())
        ).all()

        if len(prices) < MIN_ANALYSIS_BARS:
            continue

        analysis = build_investment_analysis(stock, snapshot, prices)

        if analysis["opportunity_score"] >= min_score:
            results.append(analysis)

    results.sort(
        key=lambda item: (item["opportunity_score"], item["ticker"]),
        reverse=True,
    )

    return results[:limit]

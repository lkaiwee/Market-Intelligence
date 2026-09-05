from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import FundamentalSnapshot, Stock
from app.providers.yahoo_fundamentals import YahooFundamentalsProvider
from app.services.blue_chip_universe import BLUE_CHIP_UNIVERSE


def _decimal(value):
    if value in (None, "", "None", "null", "-"):
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _equity_estimate(info: dict):
    market_cap = _decimal(info.get("marketCap"))
    price_to_book = _decimal(info.get("priceToBook"))

    if (
        market_cap is not None
        and price_to_book is not None
        and price_to_book > 0
    ):
        return market_cap / price_to_book

    total_debt = _decimal(info.get("totalDebt"))
    debt_to_equity = _decimal(info.get("debtToEquity"))

    # Yahoo commonly reports this field as a percentage (e.g. 50 = 0.50 D/E).
    if (
        total_debt is not None
        and debt_to_equity is not None
        and debt_to_equity > 0
    ):
        ratio = debt_to_equity / Decimal("100")
        if ratio > 0:
            return total_debt / ratio

    return None


async def refresh_yahoo_fundamentals(
    db: Session,
    provider: YahooFundamentalsProvider,
    ticker: str,
) -> FundamentalSnapshot:
    ticker = ticker.upper().strip()

    info = await provider.get_company_fundamentals(ticker)

    stock = db.get(Stock, ticker)

    if stock is None:
        stock = Stock(ticker=ticker)
        db.add(stock)
        db.flush()

    configured = BLUE_CHIP_UNIVERSE.get(ticker)

    stock.company_name = (
        info.get("longName")
        or info.get("shortName")
        or (configured[0] if configured else None)
        or stock.company_name
    )
    stock.sector = (
        info.get("sector")
        or (configured[1] if configured else None)
        or stock.sector
    )
    stock.industry = info.get("industry") or stock.industry

    operating_cf = _decimal(info.get("operatingCashflow"))
    free_cf = _decimal(info.get("freeCashflow"))

    capex = None
    if operating_cf is not None and free_cf is not None:
        capex = operating_cf - free_cf

    snapshot = db.get(FundamentalSnapshot, ticker)

    if snapshot is None:
        snapshot = FundamentalSnapshot(ticker=ticker)
        db.add(snapshot)

    snapshot.market_cap = _decimal(info.get("marketCap"))
    snapshot.revenue_ttm = _decimal(info.get("totalRevenue"))

    snapshot.revenue_growth_yoy = _decimal(info.get("revenueGrowth"))
    snapshot.earnings_growth_yoy = _decimal(info.get("earningsGrowth"))

    snapshot.profit_margin = _decimal(info.get("profitMargins"))
    snapshot.operating_margin = _decimal(info.get("operatingMargins"))
    snapshot.roe = _decimal(info.get("returnOnEquity"))

    snapshot.trailing_pe = _decimal(info.get("trailingPE"))
    snapshot.forward_pe = _decimal(info.get("forwardPE"))
    snapshot.peg_ratio = _decimal(info.get("pegRatio"))
    snapshot.price_to_book = _decimal(info.get("priceToBook"))

    snapshot.operating_cashflow_ttm = operating_cf
    snapshot.capex_ttm = capex
    snapshot.free_cash_flow_ttm = free_cf

    snapshot.total_debt = _decimal(info.get("totalDebt"))
    snapshot.cash_and_equivalents = _decimal(info.get("totalCash"))
    snapshot.shareholder_equity = _equity_estimate(info)

    snapshot.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(snapshot)

    return snapshot

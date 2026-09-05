from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import FundamentalSnapshot, Stock
from app.providers.alpha_vantage import AlphaVantageProvider


def _decimal(value) -> Decimal | None:
    if value in (None, "", "None", "null", "-"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _float(value) -> float | None:
    d = _decimal(value)
    return float(d) if d is not None else None


def _sum_latest_quarters(reports: list[dict], field: str, count: int = 4) -> Decimal | None:
    values: list[Decimal] = []
    for report in reports[:count]:
        value = _decimal(report.get(field))
        if value is not None:
            values.append(value)

    if not values:
        return None

    return sum(values, Decimal("0"))


def _latest_decimal(reports: list[dict], fields: list[str]) -> Decimal | None:
    if not reports:
        return None

    report = reports[0]
    for field in fields:
        value = _decimal(report.get(field))
        if value is not None:
            return value
    return None


async def refresh_fundamentals(
    db: Session,
    provider: AlphaVantageProvider,
    ticker: str,
) -> FundamentalSnapshot:
    ticker = ticker.upper().strip()

    stock = db.get(Stock, ticker)
    if stock is None:
        stock = Stock(ticker=ticker)
        db.add(stock)
        db.flush()

    overview = await provider.get_company_overview(ticker)
    cash_flow = await provider.get_cash_flow(ticker)
    balance = await provider.get_balance_sheet(ticker)

    stock.company_name = overview.get("Name") or stock.company_name
    stock.sector = overview.get("Sector") or stock.sector
    stock.industry = overview.get("Industry") or stock.industry

    quarterly_cf = cash_flow.get("quarterlyReports") or []
    annual_cf = cash_flow.get("annualReports") or []

    operating_cf = _sum_latest_quarters(quarterly_cf, "operatingCashflow")
    capex = _sum_latest_quarters(quarterly_cf, "capitalExpenditures")

    if operating_cf is None and annual_cf:
        operating_cf = _decimal(annual_cf[0].get("operatingCashflow"))
    if capex is None and annual_cf:
        capex = _decimal(annual_cf[0].get("capitalExpenditures"))

    # Capex is usually reported as a positive cash outflow in AV normalized statements.
    free_cash_flow = None
    if operating_cf is not None and capex is not None:
        free_cash_flow = operating_cf - abs(capex)

    quarterly_bs = balance.get("quarterlyReports") or []
    annual_bs = balance.get("annualReports") or []
    bs_reports = quarterly_bs or annual_bs

    total_debt = _latest_decimal(
        bs_reports,
        [
            "shortLongTermDebtTotal",
            "totalDebt",
            "longTermDebt",
        ],
    )

    cash = _latest_decimal(
        bs_reports,
        [
            "cashAndCashEquivalentsAtCarryingValue",
            "cashAndShortTermInvestments",
            "cashAndCashEquivalents",
        ],
    )

    equity = _latest_decimal(
        bs_reports,
        [
            "totalShareholderEquity",
            "totalStockholdersEquity",
        ],
    )

    snapshot = db.get(FundamentalSnapshot, ticker)
    if snapshot is None:
        snapshot = FundamentalSnapshot(ticker=ticker)
        db.add(snapshot)

    snapshot.market_cap = _decimal(overview.get("MarketCapitalization"))
    snapshot.revenue_ttm = _decimal(overview.get("RevenueTTM"))

    snapshot.revenue_growth_yoy = _decimal(overview.get("QuarterlyRevenueGrowthYOY"))
    snapshot.earnings_growth_yoy = _decimal(overview.get("QuarterlyEarningsGrowthYOY"))

    snapshot.profit_margin = _decimal(overview.get("ProfitMargin"))
    snapshot.operating_margin = _decimal(overview.get("OperatingMarginTTM"))
    snapshot.roe = _decimal(overview.get("ReturnOnEquityTTM"))

    snapshot.trailing_pe = _decimal(overview.get("PERatio"))
    snapshot.forward_pe = _decimal(overview.get("ForwardPE"))
    snapshot.peg_ratio = _decimal(overview.get("PEGRatio"))
    snapshot.price_to_book = _decimal(overview.get("PriceToBookRatio"))

    snapshot.operating_cashflow_ttm = operating_cf
    snapshot.capex_ttm = capex
    snapshot.free_cash_flow_ttm = free_cash_flow

    snapshot.total_debt = total_debt
    snapshot.cash_and_equivalents = cash
    snapshot.shareholder_equity = equity

    snapshot.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(snapshot)
    return snapshot


def _score_growth(value: float | None) -> int:
    if value is None:
        return 0
    if value >= 0.20:
        return 15
    if value >= 0.10:
        return 12
    if value >= 0.05:
        return 8
    if value >= 0:
        return 4
    return 0


def _score_margin(value: float | None) -> int:
    if value is None:
        return 0
    if value >= 0.25:
        return 15
    if value >= 0.15:
        return 12
    if value >= 0.08:
        return 8
    if value > 0:
        return 4
    return 0


def _score_roe(value: float | None) -> int:
    if value is None:
        return 0
    if value >= 0.25:
        return 10
    if value >= 0.15:
        return 8
    if value >= 0.08:
        return 5
    if value > 0:
        return 2
    return 0


def _fundamental_score(
    revenue_growth: float | None,
    earnings_growth: float | None,
    operating_margin: float | None,
    roe: float | None,
    fcf: float | None,
    fcf_margin: float | None,
    debt_to_equity: float | None,
    net_cash: float | None,
) -> int:
    score = 0

    score += _score_growth(revenue_growth)      # 15
    score += _score_growth(earnings_growth)    # 15
    score += _score_margin(operating_margin)   # 15
    score += _score_roe(roe)                   # 10

    # FCF quality: 25
    if fcf is not None:
        if fcf > 0:
            score += 15
        else:
            score += 0

    if fcf_margin is not None:
        if fcf_margin >= 0.20:
            score += 10
        elif fcf_margin >= 0.10:
            score += 8
        elif fcf_margin >= 0.05:
            score += 5
        elif fcf_margin > 0:
            score += 2

    # Balance sheet: 20
    if debt_to_equity is not None:
        if debt_to_equity <= 0.5:
            score += 12
        elif debt_to_equity <= 1.0:
            score += 9
        elif debt_to_equity <= 2.0:
            score += 5
        elif debt_to_equity <= 3.0:
            score += 2

    if net_cash is not None:
        if net_cash >= 0:
            score += 8
        else:
            score += 3

    return max(0, min(100, score))


def _valuation_score(
    forward_pe: float | None,
    peg_ratio: float | None,
    price_to_book: float | None,
    fcf_yield: float | None,
) -> int:
    score = 0
    available_weight = 0

    # Each metric is first scored independently, then normalized to 100 so that
    # a missing field does not automatically destroy the valuation score.
    if forward_pe is not None and forward_pe > 0:
        available_weight += 30
        if forward_pe <= 15:
            score += 30
        elif forward_pe <= 22:
            score += 24
        elif forward_pe <= 30:
            score += 16
        elif forward_pe <= 40:
            score += 8

    if peg_ratio is not None and peg_ratio > 0:
        available_weight += 25
        if peg_ratio <= 1:
            score += 25
        elif peg_ratio <= 1.5:
            score += 20
        elif peg_ratio <= 2:
            score += 14
        elif peg_ratio <= 3:
            score += 7

    if price_to_book is not None and price_to_book > 0:
        available_weight += 15
        if price_to_book <= 3:
            score += 15
        elif price_to_book <= 6:
            score += 10
        elif price_to_book <= 10:
            score += 5

    if fcf_yield is not None:
        available_weight += 30
        if fcf_yield >= 0.06:
            score += 30
        elif fcf_yield >= 0.04:
            score += 24
        elif fcf_yield >= 0.025:
            score += 16
        elif fcf_yield > 0:
            score += 8

    if available_weight == 0:
        return 0

    return max(0, min(100, round((score / available_weight) * 100)))


def _leadership_score(market_cap: float | None) -> int:
    if market_cap is None:
        return 0

    if market_cap >= 500_000_000_000:
        return 100
    if market_cap >= 200_000_000_000:
        return 90
    if market_cap >= 100_000_000_000:
        return 80
    if market_cap >= 50_000_000_000:
        return 70
    if market_cap >= 10_000_000_000:
        return 55
    return 35


def serialize_fundamentals(
    stock: Stock,
    snapshot: FundamentalSnapshot,
) -> dict:
    market_cap = _float(snapshot.market_cap)
    revenue_ttm = _float(snapshot.revenue_ttm)

    revenue_growth = _float(snapshot.revenue_growth_yoy)
    earnings_growth = _float(snapshot.earnings_growth_yoy)

    profit_margin = _float(snapshot.profit_margin)
    operating_margin = _float(snapshot.operating_margin)
    roe = _float(snapshot.roe)

    trailing_pe = _float(snapshot.trailing_pe)
    forward_pe = _float(snapshot.forward_pe)
    peg_ratio = _float(snapshot.peg_ratio)
    price_to_book = _float(snapshot.price_to_book)

    operating_cf = _float(snapshot.operating_cashflow_ttm)
    capex = _float(snapshot.capex_ttm)
    fcf = _float(snapshot.free_cash_flow_ttm)

    total_debt = _float(snapshot.total_debt)
    cash = _float(snapshot.cash_and_equivalents)
    equity = _float(snapshot.shareholder_equity)

    fcf_margin = None
    if fcf is not None and revenue_ttm and revenue_ttm != 0:
        fcf_margin = fcf / revenue_ttm

    fcf_yield = None
    if fcf is not None and market_cap and market_cap > 0:
        fcf_yield = fcf / market_cap

    debt_to_equity = None
    if total_debt is not None and equity and equity > 0:
        debt_to_equity = total_debt / equity

    net_cash = None
    if cash is not None and total_debt is not None:
        net_cash = cash - total_debt

    fundamental_score = _fundamental_score(
        revenue_growth=revenue_growth,
        earnings_growth=earnings_growth,
        operating_margin=operating_margin,
        roe=roe,
        fcf=fcf,
        fcf_margin=fcf_margin,
        debt_to_equity=debt_to_equity,
        net_cash=net_cash,
    )

    valuation_score = _valuation_score(
        forward_pe=forward_pe,
        peg_ratio=peg_ratio,
        price_to_book=price_to_book,
        fcf_yield=fcf_yield,
    )

    leadership_score = _leadership_score(market_cap)

    warnings: list[str] = []

    if market_cap is None:
        warnings.append("Market capitalization is unavailable; leadership score is 0.")

    if fcf is None:
        warnings.append("Free cash flow could not be calculated from the returned cash-flow reports.")

    warnings.append(
        "Leadership score currently uses market capitalization as a proxy. "
        "Peer/market-share ranking will be added later."
    )

    warnings.append(
        "Absolute valuation thresholds vary by industry. Future versions will compare "
        "valuation against sector and company history."
    )

    return {
        "ticker": stock.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "industry": stock.industry,

        "market_cap": market_cap,
        "revenue_ttm": revenue_ttm,
        "revenue_growth_yoy": revenue_growth,
        "earnings_growth_yoy": earnings_growth,

        "profit_margin": profit_margin,
        "operating_margin": operating_margin,
        "roe": roe,

        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "peg_ratio": peg_ratio,
        "price_to_book": price_to_book,

        "operating_cashflow_ttm": operating_cf,
        "capex_ttm": capex,
        "free_cash_flow_ttm": fcf,
        "free_cash_flow_margin": fcf_margin,
        "free_cash_flow_yield": fcf_yield,

        "total_debt": total_debt,
        "cash_and_equivalents": cash,
        "shareholder_equity": equity,
        "debt_to_equity": debt_to_equity,
        "net_cash": net_cash,

        "fundamental_score": fundamental_score,
        "valuation_score": valuation_score,
        "leadership_score": leadership_score,

        "updated_at": snapshot.updated_at,
        "warnings": warnings,
    }

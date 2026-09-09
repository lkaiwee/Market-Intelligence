"""Period-aligned annual statement analysis with explicit missing-data coverage."""
from __future__ import annotations

import asyncio
import math
import re
from datetime import date, datetime, timezone

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models_quality import FinancialStatementCache
from app.services.blue_chip_universe import yahoo_symbol


FIELDS = {
    "income": {
        "revenue": ("TotalRevenue",),
        "net_income": ("NetIncome",),
        "operating_income": ("OperatingIncome",),
        "interest_expense": ("InterestExpense",),
        "diluted_shares": ("DilutedAverageShares",),
    },
    "cashflow": {
        "operating_cashflow": ("OperatingCashFlow",),
        "capex": ("CapitalExpenditure",),
        "stock_compensation": ("StockBasedCompensation",),
        "net_borrowing": ("NetIssuancePaymentsOfDebt",),
    },
    "balance": {
        "assets": ("TotalAssets",),
        "current_assets": ("CurrentAssets",),
        "current_liabilities": ("CurrentLiabilities",),
        "debt": ("TotalDebt",),
        "cash": ("CashAndCashEquivalents",),
        "equity": ("StockholdersEquity",),
    },
}


def validate_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,15}", ticker):
        raise ValueError("Use a valid ticker of at most 16 characters.")
    return ticker


def number(value) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_statements(income: pd.DataFrame, cashflow: pd.DataFrame,
                         balance: pd.DataFrame) -> list[dict]:
    """Join exact fiscal dates, never carry a statement across reporting periods."""
    periods: dict[str, dict] = {}
    for kind, frame in (("income", income), ("cashflow", cashflow), ("balance", balance)):
        if frame is None or frame.empty:
            continue
        # Both pretty and raw Yahoo field names normalize to the same keys.
        lookup = {str(key).replace(" ", ""): key for key in frame.index}
        for column in frame.columns:
            period = pd.Timestamp(column).date().isoformat()
            values = {}
            for field, aliases in FIELDS[kind].items():
                values[field] = next((number(frame.loc[lookup[a], column]) for a in aliases
                                   if a in lookup and number(frame.loc[lookup[a], column]) is not None), None)
            if not any(value is not None for value in values.values()):
                continue
            row = periods.setdefault(period, {"period_end": period, "frequency": "annual"})
            row[kind + "_available"] = True
            row.update(values)
    return sorted(periods.values(), key=lambda p: p["period_end"], reverse=True)


def _ratio(numerator, denominator, *, positive_denominator=True):
    n, d = number(numerator), number(denominator)
    if n is None or d is None or d == 0 or (positive_denominator and d < 0):
        return None
    return n / d


def analyze_period(period: dict, previous: dict | None) -> dict:
    p = {**period}
    for fields in FIELDS.values():
        for field in fields:
            p.setdefault(field, None)
    # A preceding annual balance must be about one fiscal year earlier.
    aligned_previous = None
    if previous:
        gap = (date.fromisoformat(p["period_end"]) - date.fromisoformat(previous["period_end"])).days
        if 300 <= gap <= 430:
            aligned_previous = previous
    prior = aligned_previous or {}
    assets, prior_assets = number(p.get("assets")), number(prior.get("assets"))
    avg_assets = (assets + prior_assets) / 2 if assets is not None and prior_assets is not None else None
    cfo, capex, income = number(p.get("operating_cashflow")), number(p.get("capex")), number(p.get("net_income"))
    fcf = cfo - abs(capex) if cfo is not None and capex is not None else None
    accrual = _ratio(income - cfo, avg_assets) if income is not None and cfo is not None else None
    revenue_growth = _ratio(p.get("revenue"), prior.get("revenue"))
    dilution = _ratio(p.get("diluted_shares"), prior.get("diluted_shares"))
    return {
        **p,
        "free_cash_flow": fcf,
        "average_assets": avg_assets,
        "cfo_to_net_income": _ratio(cfo, income),
        "accruals_to_average_assets": accrual,
        "cash_conversion_margin": _ratio(cfo, p.get("revenue")),
        "fcf_margin": _ratio(fcf, p.get("revenue")),
        "net_margin": _ratio(income, p.get("revenue")),
        "debt_to_equity": _ratio(p.get("debt"), p.get("equity")),
        "current_ratio": _ratio(p.get("current_assets"), p.get("current_liabilities")),
        "interest_coverage": _ratio(p.get("operating_income"), abs(p["interest_expense"]) if p.get("interest_expense") is not None else None),
        "stock_compensation_to_revenue": _ratio(p.get("stock_compensation"), p.get("revenue")),
        "revenue_growth_yoy": revenue_growth - 1 if revenue_growth is not None else None,
        "diluted_share_growth_yoy": dilution - 1 if dilution is not None else None,
    }


def analyze_statements(payload: dict) -> dict:
    raw = sorted(payload.get("periods", []), key=lambda p: p["period_end"], reverse=True)
    periods = [analyze_period(p, raw[i + 1] if i + 1 < len(raw) else None) for i, p in enumerate(raw)]
    latest = next((p for p in periods if p.get("income_available") and p.get("cashflow_available")), None)
    rules = (
        ("cfo_to_net_income", "Operating cash flow covers positive net income", lambda x: x >= 1),
        ("accruals_to_average_assets", "Accruals / average assets ≤ 5%", lambda x: x <= .05),
        ("fcf_margin", "Positive free cash flow margin", lambda x: x > 0),
        ("current_ratio", "Current ratio ≥ 1", lambda x: x >= 1),
        ("debt_to_equity", "Debt / positive equity ≤ 1", lambda x: x <= 1),
        ("diluted_share_growth_yoy", "Annual diluted-share growth ≤ 2%", lambda x: x <= .02 + 1e-12),
    )
    checks = []
    for key, label, condition in rules:
        value = latest.get(key) if latest else None
        checks.append({"metric": key, "label": label, "value": value,
                       "result": "unavailable" if value is None else ("met" if condition(value) else "review")})
    available = [c for c in checks if c["result"] != "unavailable"]
    met = sum(c["result"] == "met" for c in available)
    warnings = [
        "Annual fiscal periods only; no mix of annual and quarterly numbers. Amounts are reported currency units, not millions.",
        "These cash-flow and balance-sheet checks describe reported figures; they are not an audit or an allegation of misconduct.",
        "Sector-neutral thresholds are less informative for banks, insurers and other financial firms.",
        "CFO / net income is unavailable when net income is zero or negative; negative equity and zero denominators are not treated as zero ratios.",
    ]
    if not latest:
        warnings.append("No annual income and cash-flow statements share a fiscal date. Refresh the source or choose another ticker.")
    if latest and raw and latest["period_end"] != raw[0]["period_end"]:
        warnings.append("The newest statement set is incomplete. The checklist uses the latest aligned income and cash-flow period.")
    return {"periods": periods, "latest_period": latest["period_end"] if latest else None,
            "checks": checks, "checks_met": met, "checks_available": len(available),
            "checks_total": len(checks),
            "score": round(100 * met / len(available)) if len(available) >= 4 else None,
            "score_note": "Equal-weight share of available checks met; shown only with at least four of six checks. Missing checks are excluded.",
            "warnings": warnings}


def _fetch_statements(ticker: str) -> dict:
    obj = yf.Ticker(yahoo_symbol(ticker))
    income = obj.get_income_stmt(freq="yearly")
    cashflow = obj.get_cashflow(freq="yearly")
    balance = obj.get_balance_sheet(freq="yearly")
    periods = normalize_statements(income, cashflow, balance)
    if not periods or not any(p.get("income_available") and p.get("cashflow_available") for p in periods):
        raise ValueError("Yahoo returned no aligned annual income and cash-flow statements. The previous cache was preserved.")
    # Metadata failure does not discard usable statements; currency stays unknown.
    try:
        info = obj.get_info() or {}
    except Exception:
        info = {}
    return {"periods": periods, "financial_currency": info.get("financialCurrency"),
            "quote_currency": info.get("currency"), "shares_outstanding": number(info.get("sharesOutstanding")),
            "company_name": info.get("longName") or info.get("shortName"),
            "source": "Yahoo Finance annual statements via yfinance",
            "source_url": f"https://finance.yahoo.com/quote/{yahoo_symbol(ticker)}/financials/"}


async def refresh_statement_cache(db: Session, ticker: str) -> FinancialStatementCache:
    ticker = validate_ticker(ticker)
    payload = await asyncio.wait_for(asyncio.to_thread(_fetch_statements, ticker), timeout=90)
    cache = db.get(FinancialStatementCache, ticker)
    if cache is None:
        cache = FinancialStatementCache(ticker=ticker)
        db.add(cache)
    cache.payload = payload
    cache.fetched_at = datetime.now(timezone.utc)
    db.commit()
    return cache


def quality_report(db: Session, ticker: str) -> dict:
    ticker = validate_ticker(ticker)
    cache = db.get(FinancialStatementCache, ticker)
    if cache is None:
        return {"ticker": ticker, "cached": False, "message": "Refresh statements to load real annual financial reports."}
    return {"ticker": ticker, "cached": True, "fetched_at": cache.fetched_at,
            **{k: v for k, v in cache.payload.items() if k != "periods"},
            **analyze_statements(cache.payload)}

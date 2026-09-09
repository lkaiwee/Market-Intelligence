"""Transparent equity DCF and earnings-multiple scenarios, not price forecasts."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice, FundamentalSnapshot
from app.models_quality import FinancialStatementCache
from app.services.earnings_quality import analyze_statements, number, validate_ticker


class ValuationInputs(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    growth_pct: float = Field(default=8, ge=-50, le=100)
    discount_pct: float = Field(default=10, ge=1, le=60)
    terminal_growth_pct: float = Field(default=2.5, ge=-5, le=6)
    years: int = Field(default=5, ge=1, le=15)
    margin_of_safety_pct: float = Field(default=20, ge=0, le=80)
    earnings_multiple: float = Field(default=20, ge=1, le=100)
    earnings_growth_pct: float = Field(default=5, ge=-80, le=100)
    base_cash_flow_override: float | None = Field(default=None, ge=-1e15, le=1e15)
    shares_override: float | None = Field(default=None, gt=0, le=1e14)
    eps_override: float | None = Field(default=None, ge=-1e7, le=1e7)
    cash_flow_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_terminal_spread(self):
        if self.discount_pct <= self.terminal_growth_pct:
            raise ValueError("Cost of equity must exceed terminal growth.")
        return self


def equity_dcf(base_cash_flow: float, shares: float, growth: float,
               discount: float, terminal_growth: float, years: int) -> dict:
    if base_cash_flow <= 0 or shares <= 0:
        raise ValueError("A positive cash-flow base and positive share count are required for this stable-growth DCF.")
    if discount <= terminal_growth or discount <= 0 or growth <= -1 or terminal_growth <= -1 or years < 1:
        raise ValueError("Invalid DCF rates or projection horizon.")
    projections = []
    for year in range(1, years + 1):
        flow = base_cash_flow * (1 + growth) ** year
        projections.append({"year": year, "cash_flow": flow, "present_value": flow / (1 + discount) ** year})
    terminal_value = projections[-1]["cash_flow"] * (1 + terminal_growth) / (discount - terminal_growth)
    terminal_pv = terminal_value / (1 + discount) ** years
    equity_value = sum(row["present_value"] for row in projections) + terminal_pv
    return {"fair_value_per_share": equity_value / shares, "equity_value": equity_value,
            "terminal_present_value": terminal_pv, "terminal_value_share_pct": 100 * terminal_pv / equity_value,
            "projections": projections}


def valuation_context(db: Session, ticker: str) -> dict:
    ticker = validate_ticker(ticker)
    price = db.scalar(select(DailyPrice).where(DailyPrice.ticker == ticker,
                      DailyPrice.trade_date <= latest_completed_session().trade_date)
                      .order_by(DailyPrice.trade_date.desc()).limit(1))
    snapshot = db.get(FundamentalSnapshot, ticker)
    cache = db.get(FinancialStatementCache, ticker)
    payload = cache.payload if cache else {}
    quote_currency = payload.get("quote_currency")
    financial_currency = payload.get("financial_currency")
    current_price = number(price.close) if price else None
    warnings = []
    shares = number(payload.get("shares_outstanding"))
    share_source = "Yahoo current shares outstanding" if shares and shares > 0 else None
    if shares is not None and shares <= 0:
        shares = None
    if shares is None and snapshot and current_price and snapshot.market_cap and snapshot.market_cap > 0:
        shares = float(snapshot.market_cap) / current_price
        share_source = "Approximation: stored market cap / latest stored close"
        warnings.append("Approximate shares combine market cap and close from possibly different dates; override with a verified share count.")
    report = analyze_statements(payload) if cache else None
    latest = next((p for p in report["periods"] if p["period_end"] == report["latest_period"]), None) if report else None
    base_cash_flow = None
    base_source = None
    if latest and financial_currency and quote_currency and financial_currency == quote_currency:
        base_cash_flow = latest.get("free_cash_flow")
        base_source = "Annual CFO minus absolute capital expenditure; zero net borrowing assumption"
    elif latest:
        warnings.append("Statement and quote currencies differ or are unknown. Cash-flow DCF needs an explicitly converted override in the quote currency.")
    else:
        warnings.append("Refresh annual statements to populate the cash-flow base and source currencies. An explicit cash-flow override can also be used.")
    eps = current_price / float(snapshot.trailing_pe) if snapshot and current_price and snapshot.trailing_pe and snapshot.trailing_pe > 0 else None
    if eps is not None:
        warnings.append("EPS is implied by latest close / stored trailing P/E; their observation dates can differ. Use a verified EPS override for a precise model.")
    if latest and (date.today() - date.fromisoformat(latest["period_end"])).days > 550:
        warnings.append("The latest annual statement is more than 18 months old. Refresh and review the model base.")
    return {
        "ticker": ticker, "current_price": current_price,
        "price_date": price.trade_date if price else None,
        "quote_currency": quote_currency, "financial_currency": financial_currency,
        "fundamentals_updated_at": snapshot.updated_at if snapshot else None,
        "statements_fetched_at": cache.fetched_at if cache else None,
        "fiscal_period_end": latest["period_end"] if latest else None,
        "base_cash_flow": base_cash_flow, "base_cash_flow_source": base_source,
        "shares": shares, "shares_source": share_source, "implied_trailing_eps": eps,
        "source": "Stored Yahoo Finance prices, fundamentals and annual statements",
        "source_url": f"https://finance.yahoo.com/quote/{ticker}/financials/", "warnings": warnings,
    }


def calculate_valuation(context: dict, inputs: ValuationInputs) -> dict:
    flow = inputs.base_cash_flow_override if inputs.base_cash_flow_override is not None else context.get("base_cash_flow")
    shares = inputs.shares_override if inputs.shares_override is not None else context.get("shares")
    eps = inputs.eps_override if inputs.eps_override is not None else context.get("implied_trailing_eps")
    quote_currency = context.get("quote_currency")
    warnings = list(context.get("warnings", []))
    if inputs.base_cash_flow_override is not None:
        if quote_currency and inputs.cash_flow_currency != quote_currency:
            raise ValueError(f"Cash-flow override must be in quote currency {quote_currency}; FX conversion is not automatic.")
        if not quote_currency:
            quote_currency = inputs.cash_flow_currency
            warnings.append(f"Quote currency is unverified. This override assumes the stock price and cash flow are both in {quote_currency}; verify before interpreting per-share values.")
    growth, discount, terminal = inputs.growth_pct / 100, inputs.discount_pct / 100, inputs.terminal_growth_pct / 100
    dcf = None
    unavailable = None
    scenarios = []
    sensitivity = []
    if flow is None or shares is None:
        unavailable = "DCF needs a cash-flow base in the quote currency and a share count. Refresh statements or supply explicit overrides."
    elif flow <= 0:
        unavailable = "Stable-growth DCF is unavailable for zero or negative starting cash flow. A turnaround requires a separately justified positive normalized cash-flow override."
    else:
        dcf = equity_dcf(flow, shares, growth, discount, terminal, inputs.years)
        fair = dcf["fair_value_per_share"]
        price = context.get("current_price")
        dcf["buy_below_with_margin_of_safety"] = fair * (1 - inputs.margin_of_safety_pct / 100)
        dcf["upside_pct"] = (fair / price - 1) * 100 if price and price > 0 else None
        for label, growth_delta, discount_delta in (("Bear", -.05, .02), ("Base", 0, 0), ("Bull", .05, -.02)):
            scenario_discount = max(discount + discount_delta, terminal + .005, .005)
            value = equity_dcf(flow, shares, growth + growth_delta, scenario_discount, terminal, inputs.years)
            scenarios.append({"name": label, "growth_pct": (growth + growth_delta) * 100,
                              "discount_pct": scenario_discount * 100, "fair_value": value["fair_value_per_share"]})
        for discount_delta in (-.02, -.01, 0, .01, .02):
            r = discount + discount_delta
            for terminal_delta in (-.01, -.005, 0, .005, .01):
                g = terminal + terminal_delta
                value = equity_dcf(flow, shares, growth, r, g, inputs.years)["fair_value_per_share"] if r > max(g, 0) else None
                sensitivity.append({"discount_pct": r * 100, "terminal_growth_pct": g * 100, "fair_value": value})
        if dcf["terminal_value_share_pct"] > 75:
            warnings.append("More than 75% of DCF value comes from the terminal value; small long-run assumption changes can dominate this estimate.")
    multiple = None
    if eps is not None and eps > 0:
        forward_eps = eps * (1 + inputs.earnings_growth_pct / 100)
        multiple = {"base_eps": eps, "next_year_eps": forward_eps,
                    "multiple": inputs.earnings_multiple,
                    "fair_value": forward_eps * inputs.earnings_multiple,
                    "method": "One-year EPS assumption × selected P/E (a scenario price, not a discounted present value)"}
    return {"context": context, "inputs": inputs.model_dump(), "quote_currency": quote_currency,
            "used_cash_flow": flow, "used_shares": shares, "dcf": dcf,
            "dcf_unavailable_reason": unavailable, "scenarios": scenarios, "sensitivity": sensitivity,
            "earnings_multiple": multiple,
            "earnings_unavailable_reason": None if multiple else "A positive EPS estimate is required; missing or non-positive earnings do not produce a P/E valuation.",
            "methodology": "Equity DCF: CFO − capex is a levered cash-flow proxy. The model assumes zero net borrowing and discounts at the cost of equity. Debt is not subtracted and cash is not added again. Growth, terminal growth and discount rates are user scenarios, not forecasts.",
            "methodology_source": "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/background/valintro.htm",
            "warnings": warnings}

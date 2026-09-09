"""Portfolio exposure and explicit, bounded position-sizing calculations."""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice, Stock
from app.models_portfolio import PortfolioPosition


def holding_data(db: Session, as_of: date | None = None, history_limit: int = 520) -> list[dict]:
    as_of = as_of or latest_completed_session().trade_date
    holdings = []
    for position in db.scalars(select(PortfolioPosition).order_by(PortfolioPosition.ticker)).all():
        stock = db.get(Stock, position.ticker)
        prices = list(reversed(db.scalars(
            select(DailyPrice).where(DailyPrice.ticker == position.ticker, DailyPrice.trade_date <= as_of)
            .order_by(DailyPrice.trade_date.desc()).limit(history_limit)
        ).all()))
        prices = [p for p in prices if math.isfinite(float(p.close)) and p.close > 0]
        current = float(prices[-1].close) if prices else None
        holdings.append({
            "ticker": position.ticker, "sector": (stock.sector if stock else None) or "Unknown",
            "shares": float(position.shares), "entry_price": float(position.entry_price),
            "cost_basis": float(position.shares * position.entry_price),
            "latest_date": prices[-1].trade_date if prices else None,
            "current_price": current,
            "market_value": current * float(position.shares) if current is not None else None,
            "prices": prices,
        })
    return holdings


def average_true_range(prices: list[DailyPrice], period: int = 14) -> float | None:
    """Simple average of the last 14 true ranges, with 15 closes required."""
    if len(prices) < period + 1:
        return None
    ranges = []
    for previous, current in zip(prices[-period-1:-1], prices[-period:]):
        high, low, close = float(current.high), float(current.low), float(previous.close)
        if not all(math.isfinite(x) for x in (high, low, close)) or high < low:
            return None
        ranges.append(max(high - low, abs(high - close), abs(low - close)))
    return sum(ranges) / period


def analyze_risk(db: Session, *, cash: float | None = None, account_equity: float | None = None,
                 stops: dict[str, float] | None = None, use_atr: bool = True,
                 atr_multiplier: float = 2.0, as_of: date | None = None) -> dict:
    target = as_of or latest_completed_session().trade_date
    holdings = holding_data(db, target)
    stops = stops or {}
    unknown_stops = set(stops) - {h["ticker"] for h in holdings}
    if unknown_stops:
        raise ValueError("Stop tickers are not portfolio holdings: " + ", ".join(sorted(unknown_stops)))
    total = sum(h["market_value"] or 0 for h in holdings)
    missing = [h["ticker"] for h in holdings if h["market_value"] is None]
    equity_source = "user supplied" if account_equity is not None else None
    equity = account_equity
    if equity is None and cash is not None and not missing:
        equity = total + cash
        equity_source = "priced holdings plus entered cash"
    sector_values: dict[str, float] = {}
    warnings = []
    if missing:
        warnings.append("Missing prices for " + ", ".join(missing) + "; concentration weights cover priced holdings only.")
    stale = [h["ticker"] for h in holdings if h["latest_date"] and h["latest_date"] < target]
    if stale:
        warnings.append("Prices predate the latest completed session for " + ", ".join(stale) + ". Refresh prices before relying on the estimates.")
    if equity is None:
        warnings.append("Enter account equity or cash to calculate risk as a share of your account. No account balance has been assumed.")
    elif equity < total + (cash or 0):
        warnings.append("Entered account equity is below priced holdings plus entered cash; exposure may exceed 100%.")
    risks = []
    for h in holdings:
        prices = h.pop("prices")
        current, value = h["current_price"], h["market_value"]
        atr = average_true_range(prices)
        stop = stops.get(h["ticker"])
        source = "entered stop" if stop is not None else None
        if stop is None and use_atr and current is not None and atr is not None and atr > 0:
            stop = max(0.0, current - atr_multiplier * atr)
            source = f"estimate: close minus {atr_multiplier:g} × ATR14 (simple average)"
        breached = current is not None and stop is not None and stop >= current
        risk = (current - stop) * h["shares"] if current is not None and stop is not None and not breached else None
        if risk is not None:
            risks.append(risk)
        if breached:
            warnings.append(f"{h['ticker']}: entered stop is at or above the latest close; treat it as already reached, not unused downside protection.")
        h.update({
            "weight_pct": value / total * 100 if value is not None and total else None,
            "account_weight_pct": value / equity * 100 if value is not None and equity else None,
            "atr14": atr, "stop_price": stop, "stop_source": source,
            "stop_reached": breached, "planned_downside": risk,
            "account_risk_pct": risk / equity * 100 if risk is not None and equity else None,
        })
        if value is not None:
            sector_values[h["sector"]] = sector_values.get(h["sector"], 0) + value
    sectors = [{"sector": sector, "market_value": value, "weight_pct": value / total * 100 if total else None}
               for sector, value in sorted(sector_values.items(), key=lambda pair: pair[1], reverse=True)]
    weights = [h["weight_pct"] for h in holdings if h["weight_pct"] is not None]
    covered_risk = sum(risks)
    complete_risk = len(risks) == len(holdings)
    return {
        "as_of": target, "holdings": holdings, "sectors": sectors, "position_count": len(holdings),
        "total_cost_basis": sum(h["cost_basis"] for h in holdings), "priced_market_value": total,
        "cash": cash, "account_equity": equity, "equity_source": equity_source,
        "unpriced_tickers": missing, "stale_tickers": stale,
        "largest_position_pct": max(weights) if weights else None,
        "top_three_pct": sum(sorted(weights, reverse=True)[:3]) if weights else None,
        "concentration_hhi": sum((w / 100) ** 2 for w in weights) if weights else None,
        "covered_planned_downside": covered_risk, "risk_coverage_count": len(risks),
        "total_planned_downside": covered_risk if complete_risk else None,
        "account_risk_pct": covered_risk / equity * 100 if complete_risk and equity else None,
        "warnings": warnings,
        "methodology": "Current long holdings. Weights use priced market value; account weights use explicit equity. Planned downside measures current close to entered stop or the labelled ATR estimate. A stop does not cap gap or execution losses. USD inputs; no broker orders are placed.",
    }


def size_position(*, side: str, entry: float, stop: float, account_equity: float,
                  risk_pct: float, max_allocation_pct: float, available_cash: float | None = None,
                  fractional: bool = False, fee_budget: float = 0.0) -> dict:
    values = (entry, stop, account_equity, risk_pct, max_allocation_pct, fee_budget)
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("All sizing inputs must be finite numbers.")
    if side not in {"long", "short"} or min(entry, stop, account_equity, risk_pct, max_allocation_pct) <= 0:
        raise ValueError("Choose long or short and enter positive prices, equity and limits.")
    if risk_pct > 100 or max_allocation_pct > 100 or fee_budget < 0:
        raise ValueError("Percentage limits must be at most 100 and fees cannot be negative.")
    if min(entry, stop) < 0.000001 or account_equity > 1e15:
        raise ValueError("Entry and stop must be at least 0.000001; account equity must not exceed 1e15.")
    if side == "long" and stop >= entry or side == "short" and stop <= entry:
        raise ValueError("A long stop must be below entry; a short stop must be above entry.")
    if available_cash is not None and (not math.isfinite(available_cash) or available_cash < 0):
        raise ValueError("Available cash/capital must be a finite nonnegative amount.")
    entry_d, stop_d, equity_d = map(lambda v: Decimal(str(v)), (entry, stop, account_equity))
    fees = Decimal(str(fee_budget))
    budget = equity_d * Decimal(str(risk_pct)) / 100
    distance = abs(entry_d - stop_d)
    caps = {"risk budget": max(Decimal(0), budget - fees) / distance,
            "allocation cap": equity_d * Decimal(str(max_allocation_pct)) / 100 / entry_d}
    if available_cash is not None:
        caps["available cash/capital"] = max(Decimal(0), Decimal(str(available_cash)) - fees) / entry_d
    raw = min(caps.values())
    step = Decimal("0.000001") if fractional else Decimal("1")
    quantity = raw.quantize(step, rounding=ROUND_DOWN)
    notional = quantity * entry_d
    planned_loss = quantity * distance + (fees if quantity > 0 else 0)
    return {"side": side, "quantity": float(quantity), "entry": entry, "stop": stop,
            "risk_per_share": float(distance), "risk_budget": float(budget),
            "planned_loss_including_fees": float(planned_loss), "fee_budget": fee_budget,
            "notional": float(notional), "allocation_pct": float(notional / equity_d * 100),
            "account_risk_pct": float(planned_loss / equity_d * 100),
            "limiting_constraints": [name for name, cap in caps.items() if cap == raw],
            "cash_limit_applied": available_cash is not None, "fractional": fractional,
            "notes": ["Risk = shares × entry-to-stop distance + entered round-trip fees. Quantity is rounded down.",
                      "Stop execution and borrow availability are not guaranteed. Short positions can lose more than their notional; the capital cap is a planning input, not a broker margin calculation."]}

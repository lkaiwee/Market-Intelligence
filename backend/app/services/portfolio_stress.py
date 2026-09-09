"""Historical price-return risk and explicit shocks for current holdings."""
from __future__ import annotations

import math
from datetime import date, timedelta

import exchange_calendars as xcals
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice
from app.services.portfolio_risk import holding_data

MIN_SAMPLES = 60


def return_frame(series: dict[str, dict[date, float]], as_of: date, lookback: int) -> pd.DataFrame:
    """Reindex actual exchange sessions so a missing close never becomes a multi-day 'daily' return."""
    if not series or not any(series.values()):
        return pd.DataFrame()
    start = max(min(day for values in series.values() for day in values), as_of - timedelta(days=lookback * 3))
    calendar = xcals.get_calendar("XNYS", start=start.isoformat(), end=(as_of + timedelta(days=1)).isoformat())
    sessions = calendar.sessions_in_range(start, as_of)
    index = pd.DatetimeIndex([stamp.date() for stamp in sessions])
    prices = pd.DataFrame({ticker: pd.Series(values, dtype=float) for ticker, values in series.items()})
    prices.index = pd.DatetimeIndex(prices.index)
    prices = prices.reindex(index).where(lambda values: values > 0)
    return prices.pct_change(fill_method=None).replace([float("inf"), -float("inf")], float("nan")).tail(lookback)


def pair_statistics(returns: pd.DataFrame, left: str, right: str, min_samples: int = MIN_SAMPLES) -> dict:
    if left not in returns or right not in returns:
        return {"correlation": None, "beta": None, "samples": 0}
    pair = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    n = len(pair)
    if n < min_samples or pair["right"].var(ddof=1) <= 1e-16 or pair["left"].var(ddof=1) <= 1e-16:
        return {"correlation": None, "beta": None, "samples": n}
    return {"correlation": float(pair["left"].corr(pair["right"])),
            "beta": float(pair["left"].cov(pair["right"]) / pair["right"].var(ddof=1)), "samples": n}


def historical_risk(returns: pd.Series, capital: float, confidence: float) -> dict | None:
    returns = returns.dropna()
    if len(returns) < MIN_SAMPLES or capital <= 0:
        return None
    quantile = float(returns.quantile(1 - confidence))
    tail = returns[returns <= quantile]
    var = max(0.0, -quantile)
    es = max(0.0, -float(tail.mean()))
    return {
        "samples": len(returns), "start_date": returns.index[0].date(), "end_date": returns.index[-1].date(),
        "daily_volatility_pct": float(returns.std(ddof=1) * 100),
        "annualized_volatility_pct": float(returns.std(ddof=1) * math.sqrt(252) * 100),
        "confidence": confidence, "one_day_var_pct": var * 100, "one_day_var_amount": var * capital,
        "one_day_expected_shortfall_pct": es * 100, "one_day_expected_shortfall_amount": es * capital,
        "tail_observations": len(tail), "worst_day": returns.idxmin().date(),
        "worst_day_return_pct": float(returns.min() * 100),
        "worst_day_pnl": float(returns.min() * capital),
    }


def analyze_stress(db: Session, *, lookback: int = 252, confidence: float = 0.95,
                   market_shock_pct: float = -10, mode: str = "uniform",
                   shocks: dict[str, float] | None = None, cash: float | None = None,
                   as_of: date | None = None) -> dict:
    target = as_of or latest_completed_session().trade_date
    holdings = holding_data(db, target, history_limit=lookback + 40)
    tickers = [h["ticker"] for h in holdings]
    shocks = shocks or {}
    unknown = set(shocks) - set(tickers)
    if unknown:
        raise ValueError("Shock tickers are not portfolio holdings: " + ", ".join(sorted(unknown)))
    series = {h["ticker"]: {p.trade_date: float(p.close) for p in h["prices"]} for h in holdings}
    if "SPY" not in series:
        benchmark = db.scalars(select(DailyPrice).where(DailyPrice.ticker == "SPY", DailyPrice.trade_date <= target)
                               .order_by(DailyPrice.trade_date.desc()).limit(lookback + 40)).all()
        series["SPY"] = {p.trade_date: float(p.close) for p in benchmark}
    returns = return_frame(series, target, lookback)
    priced = [h for h in holdings if h["market_value"] is not None]
    total_value = sum(h["market_value"] for h in priced)
    enough = [h for h in priced if h["ticker"] in returns and returns[h["ticker"]].count() >= MIN_SAMPLES]
    included = [h["ticker"] for h in enough]
    excluded = [h["ticker"] for h in holdings if h["ticker"] not in included]
    covered_value = sum(h["market_value"] for h in enough)
    capital = covered_value + (cash or 0)
    metrics = None
    common_samples = 0
    if included and capital > 0:
        aligned = returns[included].dropna(how="any")
        common_samples = len(aligned)
        weights = pd.Series({h["ticker"]: h["market_value"] / capital for h in enough})
        metrics = historical_risk(aligned.mul(weights).sum(axis=1), capital, confidence)
    correlations = []
    for left in tickers:
        for right in tickers:
            stat = pair_statistics(returns, left, right)
            correlations.append({"left": left, "right": right, "correlation": stat["correlation"], "samples": stat["samples"]})
    results = []
    scenario_missing = []
    covered_pnl = 0.0
    for h in holdings:
        beta = pair_statistics(returns, h["ticker"], "SPY")
        shock, source = shocks.get(h["ticker"]), "entered holding shock"
        if shock is None:
            if mode == "uniform":
                shock, source = market_shock_pct, "uniform holding shock"
            elif beta["beta"] is not None:
                shock, source = market_shock_pct * beta["beta"], "historical SPY beta × market shock"
            else:
                source = "SPY beta unavailable"
        # An unlevered long equity's price cannot fall below zero.
        applied = max(-100.0, shock) if shock is not None else None
        pnl = h["market_value"] * applied / 100 if h["market_value"] is not None and applied is not None else None
        if pnl is None:
            scenario_missing.append(h["ticker"])
        else:
            covered_pnl += pnl
        results.append({"ticker": h["ticker"], "market_value": h["market_value"], "latest_date": h["latest_date"],
                        "beta_to_spy": beta["beta"], "beta_samples": beta["samples"],
                        "raw_shock_pct": shock, "applied_shock_pct": applied, "source": source,
                        "pnl": pnl, "stressed_value": h["market_value"] + pnl if pnl is not None else None})
    warnings = []
    if excluded:
        warnings.append("Historical estimates exclude holdings with missing prices or fewer than 60 daily returns: " + ", ".join(excluded) + ".")
    if metrics is None and holdings:
        warnings.append(f"At least {MIN_SAMPLES} common daily return observations are required; {common_samples} are available.")
    stale = [h["ticker"] for h in holdings if h["latest_date"] and h["latest_date"] < target]
    if stale:
        warnings.append("Latest prices are stale for " + ", ".join(stale) + ". Refresh the portfolio.")
    if scenario_missing:
        warnings.append("Scenario total is unavailable because prices or beta are missing for " + ", ".join(scenario_missing) + ". Enter individual shocks or use uniform mode.")
    if metrics and metrics["tail_observations"] < 10:
        warnings.append(f"Expected shortfall uses only {metrics['tail_observations']} tail observations; this is a small historical sample.")
    return {
        "as_of": target, "lookback_sessions": lookback, "minimum_samples": MIN_SAMPLES,
        "position_count": len(holdings), "priced_market_value": total_value,
        "covered_market_value": covered_value, "covered_priced_value_pct": covered_value / total_value * 100 if total_value else None,
        "included_tickers": included, "excluded_tickers": excluded, "unpriced_tickers": [h["ticker"] for h in holdings if h["market_value"] is None],
        "cash": cash, "risk_capital": capital, "common_samples": common_samples,
        "metrics": metrics, "correlation_tickers": tickers, "correlations": correlations,
        "scenario": {"mode": mode, "market_shock_pct": market_shock_pct, "holdings": results,
                     "covered_pnl": covered_pnl, "total_pnl": covered_pnl if not scenario_missing else None,
                     "total_return_pct": covered_pnl / (total_value + (cash or 0)) * 100 if not scenario_missing and total_value + (cash or 0) else None,
                     "missing_tickers": scenario_missing},
        "warnings": warnings,
        "methodology": "Historical simulation of today's holdings at fixed current weights, plus entered cash if any; not actual portfolio performance. Daily simple close returns use complete exchange sessions without forward filling. Correlations and SPY betas use pairwise common dates; portfolio risk uses dates common to all included holdings. VaR is the nonnegative loss at the selected historical quantile; expected shortfall averages the tail. Volatility uses 252 sessions/year. Price returns exclude dividends; corporate actions and changing relationships can distort estimates. Scenarios are hypothetical, not forecasts.",
    }

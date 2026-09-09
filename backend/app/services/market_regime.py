"""Transparent, descriptive regime rules using completed daily price bars."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from math import isfinite, log, sqrt
from statistics import mean, stdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice
from app.services.universe_registry import screening_universe


def price_components(rows: list[tuple[date, float]], expected: date) -> dict:
    rows = sorted((day, float(close)) for day, close in rows if day <= expected)
    result = {"date": rows[-1][0].isoformat() if rows else None, "bars": len(rows), "close": None,
              "sma50": None, "sma200": None, "realized_volatility20_pct": None,
              "above_sma50": None, "above_sma200": None, "available": False, "reason": None}
    if not rows:
        result["reason"] = "No stored price history."
        return result
    closes = [close for _, close in rows]
    if any(not isfinite(value) or value <= 0 for value in closes[-200:]):
        result["reason"] = "Invalid close in the required history."
        return result
    result["close"] = closes[-1]
    if len(closes) >= 50:
        result["sma50"] = mean(closes[-50:])
        result["above_sma50"] = closes[-1] > result["sma50"]
    if len(closes) >= 200:
        result["sma200"] = mean(closes[-200:])
        result["above_sma200"] = closes[-1] > result["sma200"]
    if len(closes) >= 21:
        returns = [log(closes[index] / closes[index - 1]) for index in range(len(closes) - 20, len(closes))]
        result["realized_volatility20_pct"] = stdev(returns) * sqrt(252) * 100
    if rows[-1][0] != expected:
        result["reason"] = f"Stale history: latest completed session is {expected.isoformat()}."
    elif len(rows) < 200:
        result["reason"] = "At least 200 completed daily bars are required."
    else:
        result["available"] = True
    return result


def classify_regime(spy: dict, breadth: dict) -> tuple[str, list[str]]:
    missing = []
    if not spy["available"]:
        missing.append(f"SPY: {spy['reason']}")
    if not breadth["available"]:
        missing.append("Breadth needs at least 10 fresh stocks and 60% coverage of the screening universe, each with 200 daily bars.")
    if missing:
        return "unknown", missing
    vol = spy["realized_volatility20_pct"]
    above50 = breadth["above_sma50_pct"]
    if vol >= 35:
        return "risk-off", ["SPY 20-day annualized realized volatility is at least 35%."]
    if not spy["above_sma200"] and spy["close"] < spy["sma200"] and above50 < 40:
        return "risk-off", ["SPY is below its 200-day average and fewer than 40% of eligible stocks are above their 50-day averages."]
    if spy["above_sma200"] and spy["sma50"] > spy["sma200"] and above50 >= 60 and vol < 25:
        return "risk-on", ["SPY and its 50-day average are above its 200-day average, breadth is at least 60%, and realized volatility is below 25%."]
    return "neutral", ["The trend, breadth and volatility components do not jointly satisfy a risk-on or risk-off rule."]


def market_regime(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    session = latest_completed_session(now)
    expected = session.trade_date
    universe = screening_universe(db)
    symbols = sorted(set(universe) | {"SPY"})
    stored = db.execute(
        select(DailyPrice.ticker, DailyPrice.trade_date, DailyPrice.close)
        .where(DailyPrice.ticker.in_(symbols), DailyPrice.trade_date <= expected,
               DailyPrice.trade_date >= expected - timedelta(days=550))
        .order_by(DailyPrice.ticker, DailyPrice.trade_date)
    ).all()
    histories = defaultdict(list)
    for ticker, day, close in stored:
        histories[ticker].append((day, close))
    spy = price_components(histories["SPY"], expected)
    constituents = [{"ticker": ticker, "company_name": universe[ticker]["company_name"],
                     **price_components(histories[ticker], expected)} for ticker in sorted(universe)]
    eligible = [row for row in constituents if row["available"]]
    count = len(eligible)
    coverage = count / len(universe) * 100 if universe else 0.0
    breadth = {
        "universe_count": len(universe), "eligible_count": count,
        "excluded_count": len(universe) - count, "coverage_pct": coverage,
        "above_sma50_count": sum(row["above_sma50"] for row in eligible),
        "above_sma200_count": sum(row["above_sma200"] for row in eligible),
        "above_sma50_pct": sum(row["above_sma50"] for row in eligible) / count * 100 if count else None,
        "above_sma200_pct": sum(row["above_sma200"] for row in eligible) / count * 100 if count else None,
        "available": count >= 10 and coverage >= 60,
    }
    regime, reasons = classify_regime(spy, breadth)
    return {
        "as_of": expected.isoformat(), "calculated_at": now.isoformat(), "regime": regime,
        "reasons": reasons, "spy": spy, "breadth": breadth, "constituents": constituents,
        "methodology": {
            "price_source": "Stored Yahoo Finance unadjusted closes; cash dividends are excluded. Only completed U.S. sessions are considered.",
            "volatility": "Sample standard deviation of 20 daily logarithmic SPY price returns × √252 × 100; this is realized volatility, not VIX.",
            "breadth": "Equal-weight share above each moving average in the configured screening universe, not the full S&P 500. Stocks need 200 bars and a close on the expected session.",
            "risk_on": "SPY close > SMA200; SMA50 > SMA200; breadth above SMA50 ≥ 60%; realized volatility < 25%.",
            "risk_off": "Realized volatility ≥ 35%, or SPY close < SMA200 and breadth above SMA50 < 40%.",
            "neutral": "Fresh, sufficient data with neither risk-on nor risk-off conditions.",
            "unknown": "SPY has insufficient/stale data, or eligible breadth has fewer than 10 stocks or less than 60% universe coverage.",
            "interpretation": "These are app-defined descriptive thresholds, not a fitted prediction or a trade instruction. Trend indicators lag market changes.",
            "reference_url": "https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/overview",
        },
    }

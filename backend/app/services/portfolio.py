from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Stock
from app.models_portfolio import PortfolioPosition
from app.services.technical_analysis import MIN_ANALYSIS_BARS, build_technical_analysis


def _round(value, digits: int = 2):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return round(float(value), digits)


def portfolio_tickers(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(PortfolioPosition.ticker)
            .order_by(PortfolioPosition.ticker.asc())
        ).all()
    )


def _price_rows(db: Session, ticker: str) -> list[DailyPrice]:
    return list(
        db.scalars(
            select(DailyPrice)
            .where(DailyPrice.ticker == ticker)
            .order_by(DailyPrice.trade_date.asc())
        ).all()
    )


def _level_status(current: float, level: float | None, volume_ratio: float | None, atr: float | None) -> str:
    if level is None or current <= 0:
        return "UNAVAILABLE"

    if current >= level:
        confirmation_buffer = (atr or 0.0) * 0.25
        if current >= level + confirmation_buffer and (volume_ratio or 0.0) >= 1.2:
            return "CONFIRMED"
        return "ABOVE_LEVEL"

    distance_pct = ((level / current) - 1) * 100
    if distance_pct <= 2.0:
        return "NEAR_BREAKOUT"
    return "BELOW"


def build_position_analysis(
    position: PortfolioPosition,
    stock: Stock,
    prices: list[DailyPrice],
) -> dict:
    entry_price = float(position.entry_price)
    shares = float(position.shares)

    if not prices:
        return {
            "ticker": position.ticker,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "industry": stock.industry,
            "entry_price": round(entry_price, 2),
            "shares": round(shares, 6),
            "opened_on": position.opened_on,
            "notes": position.notes,
            "latest_date": None,
            "current_price": None,
            "cost_basis": round(entry_price * shares, 2),
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_pct": None,
            "target_price": None,
            "target_upside_pct": None,
            "stretch_target": None,
            "stop_loss": None,
            "stop_distance_pct": None,
            "nearest_support": None,
            "support_source": None,
            "breakout_20d": None,
            "breakout_50d": None,
            "breakout_52w": None,
            "primary_breakout": None,
            "breakout_status": "UNAVAILABLE",
            "reward_risk_ratio": None,
            "trend": "UNKNOWN",
            "technical_score": None,
            "rsi14": None,
            "atr14": None,
            "warnings": ["No stored price data is available for this position."],
        }

    prices = sorted(prices, key=lambda row: row.trade_date)
    current = float(prices[-1].close)
    market_value = current * shares
    cost_basis = entry_price * shares
    pnl = market_value - cost_basis
    pnl_pct = ((current / entry_price) - 1) * 100 if entry_price else None

    result = {
        "ticker": position.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "industry": stock.industry,
        "entry_price": round(entry_price, 2),
        "shares": round(shares, 6),
        "opened_on": position.opened_on,
        "notes": position.notes,
        "latest_date": prices[-1].trade_date,
        "current_price": round(current, 2),
        "cost_basis": round(cost_basis, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_pct": _round(pnl_pct),
        "target_price": None,
        "target_upside_pct": None,
        "stretch_target": None,
        "stop_loss": None,
        "stop_distance_pct": None,
        "nearest_support": None,
        "support_source": None,
        "breakout_20d": None,
        "breakout_50d": None,
        "breakout_52w": None,
        "primary_breakout": None,
        "breakout_status": "UNAVAILABLE",
        "reward_risk_ratio": None,
        "trend": "UNKNOWN",
        "technical_score": None,
        "rsi14": None,
        "atr14": None,
        "warnings": [],
    }

    if len(prices) < MIN_ANALYSIS_BARS:
        result["warnings"].append(
            f"Only {len(prices)} daily bars are stored; at least {MIN_ANALYSIS_BARS} "
            "are required for target, stop-loss and breakout calculations."
        )
        return result

    technical = build_technical_analysis(position.ticker, prices)

    df = pd.DataFrame(
        {
            "high": [float(row.high) for row in prices],
            "low": [float(row.low) for row in prices],
            "close": [float(row.close) for row in prices],
        }
    )

    # Exclude today's/current bar so the breakout levels represent levels that
    # were known before the latest close.
    prior = df.iloc[:-1] if len(df) > 1 else df

    breakout_20d = float(prior.tail(20)["high"].max()) if len(prior) >= 1 else None
    breakout_50d = float(prior.tail(50)["high"].max()) if len(prior) >= 1 else None
    breakout_52w = (
        float(prior.tail(252)["high"].max())
        if len(prior) >= 252
        else None
    )

    low_20d = float(prior.tail(20)["low"].min()) if len(prior) >= 1 else None
    low_50d = float(prior.tail(50)["low"].min()) if len(prior) >= 1 else None

    atr = technical.get("atr14")
    atr = float(atr) if atr is not None else None

    support_candidates = []
    for label, value in [
        ("SMA20", technical.get("sma20")),
        ("SMA50", technical.get("sma50")),
        ("20D_LOW", low_20d),
        ("50D_LOW", low_50d),
    ]:
        if value is None:
            continue
        value = float(value)
        if value < current:
            support_candidates.append((label, value))

    nearest_support = max(support_candidates, key=lambda item: item[1]) if support_candidates else None
    nearest_support_value = nearest_support[1] if nearest_support else None

    if atr and atr > 0:
        atr_floor = current - (1.5 * atr)
        if nearest_support_value is not None:
            structural_stop = nearest_support_value - (0.5 * atr)
            stop_loss = min(structural_stop, atr_floor)
        else:
            stop_loss = current - (2.0 * atr)
    elif nearest_support_value is not None:
        stop_loss = nearest_support_value * 0.98
    else:
        stop_loss = current * 0.92

    stop_loss = max(0.01, float(stop_loss))
    forward_risk = max(current - stop_loss, current * 0.005)

    # The tracker deliberately uses a transparent 2R rule for the main target.
    # Chart resistance is shown separately as breakout levels instead of being
    # hidden inside a subjective target formula.
    target_price = current + (2.0 * forward_risk)
    stretch_target = current + (3.0 * forward_risk)

    target_upside_pct = ((target_price / current) - 1) * 100 if current else None
    stop_distance_pct = ((stop_loss / current) - 1) * 100 if current else None
    reward_risk_ratio = (
        (target_price - current) / (current - stop_loss)
        if current > stop_loss
        else None
    )

    primary_breakout = breakout_20d

    result.update(
        {
            "target_price": _round(target_price),
            "target_upside_pct": _round(target_upside_pct),
            "stretch_target": _round(stretch_target),
            "stop_loss": _round(stop_loss),
            "stop_distance_pct": _round(stop_distance_pct),
            "nearest_support": _round(nearest_support_value),
            "support_source": nearest_support[0] if nearest_support else None,
            "breakout_20d": _round(breakout_20d),
            "breakout_50d": _round(breakout_50d),
            "breakout_52w": _round(breakout_52w),
            "primary_breakout": _round(primary_breakout),
            "breakout_status": _level_status(
                current,
                primary_breakout,
                technical.get("volume_ratio"),
                atr,
            ),
            "reward_risk_ratio": _round(reward_risk_ratio),
            "trend": technical.get("trend", "UNKNOWN"),
            "technical_score": technical.get("technical_score"),
            "rsi14": technical.get("rsi14"),
            "atr14": technical.get("atr14"),
            "warnings": list(technical.get("warnings", [])),
        }
    )

    result["warnings"].append(
        "Target is a rules-based 2R target from the latest close. The stop is "
        "derived from nearby technical support and ATR. Breakout levels use prior "
        "20-day, 50-day and approximately 52-week highs. These are planning levels, "
        "not guaranteed prices or personalized financial advice."
    )

    return result


def portfolio_summary(db: Session) -> dict:
    positions = list(
        db.scalars(
            select(PortfolioPosition)
            .order_by(PortfolioPosition.ticker.asc())
        ).all()
    )

    analyses = []
    total_cost = 0.0
    priced_cost = 0.0
    total_market_value = 0.0
    unpriced_positions = 0

    for position in positions:
        stock = db.get(Stock, position.ticker)
        if stock is None:
            continue

        analysis = build_position_analysis(
            position,
            stock,
            _price_rows(db, position.ticker),
        )
        analyses.append(analysis)

        total_cost += analysis["cost_basis"] or 0.0
        if analysis["market_value"] is not None:
            priced_cost += analysis["cost_basis"] or 0.0
            total_market_value += analysis["market_value"]
        else:
            unpriced_positions += 1

    total_pnl = total_market_value - priced_cost
    total_pnl_pct = (
        (total_market_value / priced_cost - 1) * 100
        if priced_cost > 0
        else None
    )

    return {
        "position_count": len(analyses),
        "total_cost_basis": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pnl": round(total_pnl, 2),
        "total_unrealized_pnl_pct": _round(total_pnl_pct),
        "unpriced_positions": unpriced_positions,
        "calculated_at": datetime.now(timezone.utc),
        "positions": analyses,
    }

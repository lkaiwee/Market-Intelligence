from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.market_sessions import latest_completed_session
from app.models import DailyPrice
from app.services.technical_analysis import _atr_wilder, _rsi_wilder
from app.services.universe_registry import screening_universe


def price_frame(rows) -> pd.DataFrame:
    frame = pd.DataFrame([{
        "date": row.trade_date, "open": float(row.open), "high": float(row.high),
        "low": float(row.low), "close": float(row.close), "volume": float(row.volume),
    } for row in rows])
    if frame.empty:
        return frame
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    valid = np.isfinite(frame[["open", "high", "low", "close", "volume"]]).all(axis=1)
    valid &= (frame[["open", "high", "low", "close"]] > 0).all(axis=1)
    valid &= frame["volume"] >= 0
    valid &= (frame["low"] <= frame[["open", "close"]].min(axis=1))
    valid &= (frame["high"] >= frame[["open", "close"]].max(axis=1))
    return frame.loc[valid].set_index("date")


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    close = data["close"]
    data["sma20"] = close.rolling(20).mean()
    data["sma50"] = close.rolling(50).mean()
    data["sma200"] = close.rolling(200).mean()
    data["ema20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    data["ema9"] = close.ewm(span=9, adjust=False, min_periods=9).mean()
    rsi = _rsi_wilder(close)
    data["rsi"] = rsi.mask(close.diff().abs().rolling(14).sum() == 0, 50)
    data["atr"] = _atr_wilder(data["high"], data["low"], close)
    data["prior_high20"] = data["high"].shift(1).rolling(20).max()
    data["prior_low20"] = data["low"].shift(1).rolling(20).min()
    data["volume_ratio"] = data["volume"] / data["volume"].shift(1).rolling(20).mean().replace(0, np.nan)
    data["bandwidth"] = 4 * close.rolling(20).std(ddof=0) / data["sma20"]
    return data


def scan_ticker(ticker, rows, expected_date, benchmark: pd.DataFrame | None = None):
    frame = price_frame([row for row in rows if row.trade_date <= expected_date])
    if len(frame) < 60:
        return {"ticker": ticker, "status": "INSUFFICIENT_DATA", "bars": len(frame), "setups": []}
    if frame.index[-1] != expected_date:
        return {"ticker": ticker, "status": "STALE", "latest_date": frame.index[-1], "setups": []}
    data = indicators(frame)
    last, prev = data.iloc[-1], data.iloc[-2]
    current, atr = float(last["close"]), float(last["atr"])
    trend = bool(current > last["sma50"] and pd.notna(last["sma200"]) and last["sma50"] > last["sma200"])
    width_history = data["bandwidth"].iloc[:-1].dropna().tail(120)
    compression = len(width_history) >= 60 and last["bandwidth"] <= width_history.quantile(.2)
    checks = [
        ("BREAKOUT", "20-session breakout", [current > last["prior_high20"], last["volume_ratio"] >= 1.5, current > last["sma50"]],
         "Close above prior 20-session high; volume ≥1.5× prior 20-session mean; above SMA50."),
        ("PULLBACK", "Trend pullback", [trend, abs(current - last["ema20"]) <= atr, 40 <= last["rsi"] <= 60],
         "Price > SMA50 > SMA200; within one ATR of EMA20; RSI 40–60."),
        ("SQUEEZE", "Volatility compression", [compression, current > last["sma50"], last["volume_ratio"] < 1],
         "20-session Bollinger width in bottom 20% of prior 120 widths (minimum 60); above SMA50; below-average volume."),
        ("REVERSAL", "Oversold recovery", [prev["rsi"] < 30 <= last["rsi"], current > last["ema9"], current > prev["close"]],
         "RSI crosses back above 30; close above EMA9 and previous close."),
    ]
    setups = [{"id": key, "name": name, "matched": all(bool(x) for x in conditions),
               "score": round(sum(bool(x) for x in conditions) / len(conditions) * 100),
               "criteria": criteria} for key, name, conditions, criteria in checks]
    relative = None
    if benchmark is not None and not benchmark.empty:
        aligned = pd.concat([frame["close"].rename("stock"), benchmark["close"].rename("spy")], axis=1).dropna()
        if len(aligned) >= 64 and aligned.index[-1] == expected_date:
            relative = round(((aligned.iloc[-1]["stock"] / aligned.iloc[-64]["stock"] - 1)
                              - (aligned.iloc[-1]["spy"] / aligned.iloc[-64]["spy"] - 1)) * 100, 2)
    stop = max(.01, current - 2 * atr)
    def number(value):
        return round(float(value), 4) if pd.notna(value) and np.isfinite(value) else None
    return {"ticker": ticker, "status": "CURRENT", "latest_date": frame.index[-1], "bars": len(frame),
            "price": number(current), "atr": number(atr), "rsi": number(last["rsi"]),
            "volume_ratio": number(last["volume_ratio"]), "relative_strength_63d_pp": relative,
            "entry_reference": number(current), "stop_reference": number(stop),
            "target_2r": number(current + 2 * (current - stop)), "setups": setups,
            "matched_count": sum(item["matched"] for item in setups),
            "score": max(item["score"] for item in setups)}


def scan_universe(db, setup="ALL", matches_only=True):
    expected = latest_completed_session().trade_date
    universe = screening_universe(db)
    tickers = list(universe)[:300]
    rows = db.scalars(select(DailyPrice).where(
        DailyPrice.ticker.in_(list(dict.fromkeys(tickers + ["SPY"]))),
        DailyPrice.trade_date <= expected,
        DailyPrice.trade_date >= expected - timedelta(days=1100),
    ).order_by(DailyPrice.ticker, DailyPrice.trade_date)).all()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.ticker].append(row)
    benchmark = price_frame(grouped["SPY"])
    results, unavailable = [], []
    for ticker in tickers:
        item = scan_ticker(ticker, grouped[ticker], expected, benchmark)
        item.update(company_name=universe[ticker].get("company_name"), sector=universe[ticker].get("sector"))
        if item["status"] != "CURRENT":
            unavailable.append(item)
            continue
        selected = [entry for entry in item["setups"] if setup == "ALL" or entry["id"] == setup]
        item["setups"] = selected
        item["score"] = max(entry["score"] for entry in selected)
        if not matches_only or any(entry["matched"] for entry in selected):
            results.append(item)
    results.sort(key=lambda item: (-item["score"], -(item["relative_strength_63d_pp"] or 0), item["ticker"]))
    return {"as_of": expected, "universe_size": len(universe), "scanned": len(tickers),
            "current_series": len(tickers) - len(unavailable), "results": results, "unavailable": unavailable,
            "notes": ["Signals use completed daily OHLCV. Ranking is rule coverage, not a probability of profit.",
                      "Entry uses the latest close as a planning reference; stop is 2 ATR below it and target is 2R above it.",
                      "RS is stock minus SPY price return over 63 common sessions; dividends are excluded."]
                     + (["Scan limited to the first 300 registered tickers."] if len(universe) > 300 else [])}

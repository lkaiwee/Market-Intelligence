from __future__ import annotations

from typing import Iterable
import pandas as pd

from app.models import DailyPrice

MIN_ANALYSIS_BARS = 35


def _round(value, digits: int = 2):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.where(avg_loss != 0, 100)


def _atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _pullback_score(pullback_pct: float) -> int:
    depth = abs(pullback_pct)

    if 5 <= depth <= 15:
        return 25
    if 2 <= depth < 5:
        return 18
    if 15 < depth <= 20:
        return 18
    if depth < 2:
        return 10
    if 20 < depth <= 30:
        return 8
    return 3


def build_technical_analysis(ticker: str, prices: Iterable[DailyPrice]) -> dict:
    rows = list(prices)

    if len(rows) < MIN_ANALYSIS_BARS:
        raise ValueError(
            f"At least {MIN_ANALYSIS_BARS} daily bars are required for analysis; "
            f"only {len(rows)} are stored."
        )

    rows.sort(key=lambda p: p.trade_date)

    df = pd.DataFrame(
        {
            "date": [p.trade_date for p in rows],
            "open": [float(p.open) for p in rows],
            "high": [float(p.high) for p in rows],
            "low": [float(p.low) for p in rows],
            "close": [float(p.close) for p in rows],
            "volume": [float(p.volume) for p in rows],
        }
    )

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    df["sma20"] = close.rolling(20).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()

    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()

    df["rsi14"] = _rsi_wilder(close, 14)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    df["atr14"] = _atr_wilder(high, low, close, 14)
    df["avg_volume20"] = volume.rolling(20).mean()

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(latest["close"])
    avg_volume20 = _round(latest["avg_volume20"])
    volume_ratio = None
    if avg_volume20 and avg_volume20 > 0:
        volume_ratio = float(latest["volume"]) / avg_volume20

    atr14 = _round(latest["atr14"])
    atr_pct = (atr14 / price) * 100 if atr14 is not None and price else None

    history_bars = len(df)
    high_available = float(df["high"].max())
    pullback_available_pct = ((price / high_available) - 1) * 100

    high_52w = None
    pullback_52w_pct = None
    if history_bars >= 252:
        recent_252 = df.tail(252)
        high_52w = float(recent_252["high"].max())
        pullback_52w_pct = ((price / high_52w) - 1) * 100

    sma20 = _round(latest["sma20"])
    sma50 = _round(latest["sma50"])
    sma200 = _round(latest["sma200"])
    ema9 = _round(latest["ema9"])
    ema20 = _round(latest["ema20"])
    rsi14 = _round(latest["rsi14"])
    macd = _round(latest["macd"], 4)
    macd_signal = _round(latest["macd_signal"], 4)
    macd_histogram = _round(latest["macd_histogram"], 4)

    trend_alignment = 0
    if sma50 is not None and price > sma50:
        trend_alignment += 10

    if sma200 is not None:
        if price > sma200:
            trend_alignment += 10
    else:
        trend_alignment += 5

    if ema9 is not None and ema20 is not None and ema9 > ema20:
        trend_alignment += 5

    momentum = 0
    if rsi14 is not None:
        if 35 <= rsi14 <= 55:
            momentum += 15
        elif 30 <= rsi14 <= 65:
            momentum += 10
        elif 25 <= rsi14 <= 70:
            momentum += 5

    if macd is not None and macd_signal is not None and macd > macd_signal:
        momentum += 10

    reference_pullback = (
        pullback_52w_pct if pullback_52w_pct is not None else pullback_available_pct
    )
    pullback_setup = _pullback_score(reference_pullback)

    volume_volatility = 0
    if volume_ratio is not None:
        if 0.7 <= volume_ratio <= 1.5:
            volume_volatility += 10
        elif 0.5 <= volume_ratio <= 2.0:
            volume_volatility += 7
        else:
            volume_volatility += 4

    if atr_pct is not None:
        if atr_pct <= 4:
            volume_volatility += 5
        elif atr_pct <= 7:
            volume_volatility += 3
        else:
            volume_volatility += 1

    price_confirmation = 0
    if ema9 is not None and price > ema9:
        price_confirmation += 5
    if price > float(previous["close"]):
        price_confirmation += 5

    technical_score = int(
        trend_alignment
        + momentum
        + pullback_setup
        + volume_volatility
        + price_confirmation
    )
    technical_score = max(0, min(100, technical_score))

    if technical_score >= 85:
        signal = "STRONG_SETUP"
    elif technical_score >= 75:
        signal = "ATTRACTIVE"
    elif technical_score >= 60:
        signal = "WATCH"
    else:
        signal = "NEUTRAL"

    if (
        sma50 is not None
        and ema9 is not None
        and ema20 is not None
        and price > sma50
        and ema9 > ema20
        and (sma200 is None or price > sma200)
    ):
        trend = "BULLISH"
    elif (
        sma50 is not None
        and ema9 is not None
        and ema20 is not None
        and price < sma50
        and ema9 < ema20
        and (sma200 is None or price < sma200)
    ):
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    warnings = []
    if history_bars < 200:
        warnings.append("SMA200 is unavailable because fewer than 200 daily bars are stored.")
    if history_bars < 252:
        warnings.append(
            "True 52-week high/pullback is unavailable because fewer than 252 daily bars "
            "are stored. The score uses the available-period high instead."
        )
    warnings.append(
        "technical_score is a rules-based technical ranking, not a buy/sell recommendation. "
        "Fundamental quality and valuation are not included yet."
    )

    return {
        "ticker": ticker.upper(),
        "latest_date": rows[-1].trade_date,
        "history_bars": history_bars,
        "price": round(price, 2),
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "ema9": ema9,
        "ema20": ema20,
        "rsi14": rsi14,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "atr14": atr14,
        "atr_pct": _round(atr_pct),
        "avg_volume20": avg_volume20,
        "volume_ratio": _round(volume_ratio),
        "high_available": round(high_available, 2),
        "pullback_available_pct": round(pullback_available_pct, 2),
        "high_52w": _round(high_52w),
        "pullback_52w_pct": _round(pullback_52w_pct),
        "trend": trend,
        "technical_score": technical_score,
        "signal": signal,
        "score_breakdown": {
            "trend_alignment": trend_alignment,
            "momentum": momentum,
            "pullback_setup": pullback_setup,
            "volume_volatility": volume_volatility,
            "price_confirmation": price_confirmation,
        },
        "warnings": warnings,
    }

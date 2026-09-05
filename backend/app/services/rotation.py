from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice


BENCHMARK = {
    "ticker": "SPY",
    "name": "S&P 500",
    "group": "benchmark",
}

SECTORS = [
    {"ticker": "XLK", "name": "Technology", "group": "sector"},
    {"ticker": "XLC", "name": "Communication Services", "group": "sector"},
    {"ticker": "XLY", "name": "Consumer Discretionary", "group": "sector"},
    {"ticker": "XLF", "name": "Financials", "group": "sector"},
    {"ticker": "XLI", "name": "Industrials", "group": "sector"},
    {"ticker": "XLE", "name": "Energy", "group": "sector"},
    {"ticker": "XLV", "name": "Health Care", "group": "sector"},
    {"ticker": "XLU", "name": "Utilities", "group": "sector"},
    {"ticker": "XLP", "name": "Consumer Staples", "group": "sector"},
    {"ticker": "XLRE", "name": "Real Estate", "group": "sector"},
    {"ticker": "XLB", "name": "Materials", "group": "sector"},
]

THEMES = [
    {"ticker": "SOXX", "name": "Semiconductors", "group": "theme"},
    {"ticker": "IGV", "name": "Software", "group": "theme"},
    {"ticker": "CIBR", "name": "Cybersecurity", "group": "theme"},
    {"ticker": "IWM", "name": "Small Caps", "group": "theme"},
    {"ticker": "QQQ", "name": "Nasdaq 100", "group": "theme"},
]

MIN_ROTATION_BARS = 21


def rotation_universe(include_themes: bool = False) -> list[dict]:
    items = [BENCHMARK, *SECTORS]
    if include_themes:
        items.extend(THEMES)
    return items


def _load_close_series(db: Session, ticker: str) -> pd.Series:
    rows = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.trade_date.asc())
    ).all()

    if len(rows) < MIN_ROTATION_BARS:
        raise ValueError(
            f"{ticker} has only {len(rows)} stored daily bars; "
            f"{MIN_ROTATION_BARS} are required."
        )

    return pd.Series(
        data=[float(r.close) for r in rows],
        index=pd.to_datetime([r.trade_date for r in rows]),
        name=ticker,
        dtype="float64",
    )


def _return(series: pd.Series, sessions: int) -> float:
    if len(series) <= sessions:
        raise ValueError("Insufficient series length.")

    current = float(series.iloc[-1])
    previous = float(series.iloc[-1 - sessions])

    return ((current / previous) - 1.0) * 100.0


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _rotation_score(
    relative_1d: float,
    relative_5d: float,
    relative_20d: float,
    absolute_20d: float,
    momentum_20d: float,
) -> int:
    # Start neutral and reward sustained relative leadership.
    score = 50.0

    score += _bounded(relative_1d * 2.0, -6, 6)
    score += _bounded(relative_5d * 2.2, -12, 12)
    score += _bounded(relative_20d * 1.6, -16, 16)

    # Absolute trend confirmation.
    score += _bounded(absolute_20d * 0.6, -8, 8)

    # Momentum proxy compares the latest close with the 20-day mean.
    score += _bounded(momentum_20d * 0.8, -8, 8)

    return int(round(_bounded(score, 0, 100)))


def _flow(score: int) -> str:
    if score >= 75:
        return "STRONG_INFLOW"
    if score >= 60:
        return "INFLOW"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "OUTFLOW"
    return "STRONG_OUTFLOW"


def _risk_on_regime(rows: list[dict]) -> tuple[str, int]:
    by_ticker = {row["ticker"]: row for row in rows}

    growth = [
        ticker for ticker in ("XLK", "XLC", "XLY")
        if ticker in by_ticker
    ]

    cyclical = [
        ticker for ticker in ("XLF", "XLI", "XLB")
        if ticker in by_ticker
    ]

    defensive = [
        ticker for ticker in ("XLU", "XLP", "XLV")
        if ticker in by_ticker
    ]

    def avg_score(tickers: list[str]) -> float:
        if not tickers:
            return 50.0
        return sum(by_ticker[t]["rotation_score"] for t in tickers) / len(tickers)

    growth_score = avg_score(growth)
    cyclical_score = avg_score(cyclical)
    defensive_score = avg_score(defensive)

    raw = (
        50
        + (growth_score - defensive_score) * 0.55
        + (cyclical_score - defensive_score) * 0.25
    )

    risk_on_score = int(round(_bounded(raw, 0, 100)))

    if risk_on_score >= 60:
        return "RISK_ON", risk_on_score
    if risk_on_score <= 40:
        return "RISK_OFF", risk_on_score
    return "NEUTRAL", risk_on_score


def build_rotation_report(
    db: Session,
    include_themes: bool = False,
) -> dict:
    universe = rotation_universe(include_themes=include_themes)

    benchmark_series = _load_close_series(db, BENCHMARK["ticker"])

    benchmark_1d = _return(benchmark_series, 1)
    benchmark_5d = _return(benchmark_series, 5)
    benchmark_20d = _return(benchmark_series, 20)

    rows: list[dict] = []
    warnings: list[str] = []

    for item in universe:
        ticker = item["ticker"]

        if ticker == BENCHMARK["ticker"]:
            continue

        try:
            series = _load_close_series(db, ticker)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        # Align the ETF and SPY by common trading dates.
        aligned = pd.concat(
            [series.rename("asset"), benchmark_series.rename("benchmark")],
            axis=1,
            join="inner",
        ).dropna()

        if len(aligned) < MIN_ROTATION_BARS:
            warnings.append(
                f"{ticker} and SPY have only {len(aligned)} aligned daily bars."
            )
            continue

        asset = aligned["asset"]
        bench = aligned["benchmark"]

        r1 = _return(asset, 1)
        r5 = _return(asset, 5)
        r20 = _return(asset, 20)

        b1 = _return(bench, 1)
        b5 = _return(bench, 5)
        b20 = _return(bench, 20)

        relative_1d = r1 - b1
        relative_5d = r5 - b5
        relative_20d = r20 - b20

        mean20 = float(asset.tail(20).mean())
        latest_price = float(asset.iloc[-1])
        momentum_20d = ((latest_price / mean20) - 1.0) * 100.0

        score = _rotation_score(
            relative_1d=relative_1d,
            relative_5d=relative_5d,
            relative_20d=relative_20d,
            absolute_20d=r20,
            momentum_20d=momentum_20d,
        )

        rows.append(
            {
                "rank": 0,
                "ticker": ticker,
                "name": item["name"],
                "group": item["group"],
                "latest_date": asset.index[-1].date(),
                "price": round(latest_price, 2),

                "return_1d": round(r1, 2),
                "return_5d": round(r5, 2),
                "return_20d": round(r20, 2),

                "relative_1d": round(relative_1d, 2),
                "relative_5d": round(relative_5d, 2),
                "relative_20d": round(relative_20d, 2),

                "momentum_20d": round(momentum_20d, 2),
                "rotation_score": score,
                "flow": _flow(score),
            }
        )

    if not rows:
        raise ValueError(
            "No rotation ETFs have sufficient stored data. "
            "Run POST /api/rotation/refresh first."
        )

    rows.sort(
        key=lambda row: (row["rotation_score"], row["ticker"]),
        reverse=True,
    )

    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    sector_rows = [row for row in rows if row["group"] == "sector"]
    regime, risk_on_score = _risk_on_regime(sector_rows)

    strongest = [row["ticker"] for row in rows[:3]]
    weakest = [row["ticker"] for row in rows[-3:]]

    latest_date = max(row["latest_date"] for row in rows)

    warnings.append(
        "Rotation scores measure recent price leadership and relative strength; "
        "they are not direct ETF fund-flow data."
    )

    return {
        "latest_date": latest_date,
        "benchmark": BENCHMARK["ticker"],
        "market_regime": regime,
        "risk_on_score": risk_on_score,
        "strongest": strongest,
        "weakest": weakest,
        "rows": rows,
        "warnings": warnings,
    }

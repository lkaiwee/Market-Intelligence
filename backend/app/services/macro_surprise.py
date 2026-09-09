"""Surprises from attributable user-recorded releases; no synthetic forecasts."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from statistics import stdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_macro_surprise import MacroRelease

MIN_HISTORY = 5
MAX_HISTORY = 36


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def release_record(row: MacroRelease, prior: list[MacroRelease], now: datetime) -> dict:
    released = utc(row.release_at) <= utc(now)
    difference = row.actual - row.consensus if released and row.actual is not None and row.consensus is not None else None
    history = [
        item for item in prior
        if utc(item.release_at) < utc(row.release_at)
        and item.indicator == row.indicator and item.unit == row.unit
        and item.actual is not None and item.consensus is not None
    ][-MAX_HISTORY:]
    historical_surprises = [float(item.actual - item.consensus) for item in history]
    dispersion = stdev(historical_surprises) if len(history) >= MIN_HISTORY else None
    standardized = float(difference) / dispersion if difference is not None and dispersion is not None and dispersion > 1e-12 else None
    return {
        "id": row.id, "indicator": row.indicator, "release_at": utc(row.release_at).isoformat(),
        "period": row.period, "unit": row.unit, "actual": number(row.actual),
        "consensus": number(row.consensus), "previous": number(row.previous),
        "actual_source": row.actual_source, "consensus_source": row.consensus_source,
        "notes": row.notes, "updated_at": utc(row.updated_at).isoformat(),
        "status": "scheduled" if not released else "awaiting_actual" if row.actual is None else "missing_consensus" if row.consensus is None else "complete",
        "surprise": number(difference),
        "surprise_pct": float(difference / abs(row.consensus) * 100) if difference is not None and row.consensus != 0 else None,
        "direction": None if difference is None else "above" if difference > 0 else "below" if difference < 0 else "inline",
        "standardized_surprise": standardized,
        "history_count": len(history), "historical_stddev": dispersion,
    }


def macro_surprise_dashboard(db: Session, now: datetime | None = None) -> dict:
    now = utc(now or datetime.now(timezone.utc))
    rows = list(db.scalars(select(MacroRelease).order_by(MacroRelease.release_at.asc(), MacroRelease.id.asc())))
    prior_by_series: dict[tuple[str, str], list[MacroRelease]] = defaultdict(list)
    records = []
    for row in rows:
        key = (row.indicator, row.unit)
        records.append(release_record(row, prior_by_series[key], now))
        if utc(row.release_at) <= now:
            prior_by_series[key].append(row)
    return {
        "as_of": now.isoformat(), "count": len(records), "releases": list(reversed(records)),
        "methodology": {
            "source_mode": "User-recorded actuals and consensus. No automatic consensus feed is configured.",
            "difference": "Actual minus consensus, in the recorded unit; percentage readings produce percentage-point differences. Above/below does not imply bullish/bearish.",
            "percent": "100 × (actual − consensus) / |consensus|; unavailable when consensus is zero.",
            "standardization": "Surprise divided by sample standard deviation of up to 36 strictly earlier surprises for the same indicator and unit. Requires at least 5 prior releases with nonzero dispersion; the history mean is not subtracted.",
            "history_note": "Records are editable and are not a point-in-time vintage archive. Standardization uses stored prior values, so later corrections can change it.",
            "reference_url": "https://www.federalreserve.gov/econres/notes/feds-notes/macroeconomic-news-and-stock-prices-over-the-fomc-cycle-20201014.html",
        },
    }

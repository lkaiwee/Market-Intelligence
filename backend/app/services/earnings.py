from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import yfinance as yf
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EarningsEvent
from app.services.blue_chip_universe import yahoo_symbol
from app.services.universe_registry import earnings_universe_registry


RELATED_TICKERS = {
    "NVDA": ["AMD", "AVGO", "MU", "LRCX", "AMAT", "TSM", "SMH", "SOXX"],
    "AVGO": ["NVDA", "AMD", "MU", "LRCX", "AMAT", "SMH", "SOXX"],
    "MU": ["NVDA", "AMD", "AVGO", "LRCX", "AMAT", "WDC", "SNDK", "SOXX"],
    "LRCX": ["AMAT", "MU", "NVDA", "TSM", "SOXX"],
    "AMAT": ["LRCX", "MU", "NVDA", "TSM", "SOXX"],
    "TSM": ["NVDA", "AMD", "AVGO", "AAPL", "QCOM", "SOXX"],
    "MSFT": ["GOOGL", "AMZN", "ORCL", "CRM", "NVDA", "QQQ"],
    "GOOGL": ["MSFT", "META", "AMZN", "QQQ"],
    "GOOG": ["MSFT", "META", "AMZN", "QQQ"],
    "AMZN": ["MSFT", "GOOGL", "ORCL", "NVDA", "QQQ"],
    "ORCL": ["MSFT", "AMZN", "GOOGL", "CRM", "NVDA"],
    "META": ["GOOGL", "NVDA", "QQQ"],
    "JPM": ["BAC", "WFC", "GS", "MS", "XLF"],
    "BAC": ["JPM", "WFC", "GS", "XLF"],
    "WMT": ["COST", "TGT", "XLP"],
    "COST": ["WMT", "TGT", "XLP"],
    "XOM": ["CVX", "XLE"],
    "CVX": ["XOM", "XLE"],
}

IMPACT_NOTES = {
    10: "Major market-moving earnings event with broad index and/or industry implications.",
    9: "High-impact industry-leader earnings event with meaningful sector read-through.",
    8: "Important earnings event with notable peer and sector implications.",
    7: "Earnings event with primarily company and sector-specific implications.",
}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None", "null", "-", "nan"):
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _impact_level(score: int) -> str:
    if score >= 10:
        return "VERY_HIGH"
    if score >= 9:
        return "HIGH"
    if score >= 8:
        return "ELEVATED"
    return "NORMAL"


def _to_date(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        dates = [_to_date(item) for item in value]
        dates = [item for item in dates if item is not None]
        return min(dates) if dates else None

    if isinstance(value, pd.DatetimeIndex):
        if len(value) == 0:
            return None
        return min(pd.Timestamp(item).date() for item in value)

    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return pd.Timestamp(parsed).date()
    except Exception:
        return None


def _calendar_value(calendar: dict, *keys: str):
    for key in keys:
        if key in calendar and calendar[key] not in (None, ""):
            return calendar[key]
    return None


def _event_from_calendar(
    ticker: str,
    start: date,
    end: date,
) -> dict | None:
    obj = yf.Ticker(yahoo_symbol(ticker))
    calendar = obj.get_calendar()

    if not isinstance(calendar, dict) or not calendar:
        return None

    earnings_date = _to_date(
        _calendar_value(
            calendar,
            "Earnings Date",
            "EarningsDate",
            "earningsDate",
            "Earnings Dates",
        )
    )

    if earnings_date is None or earnings_date < start or earnings_date > end:
        return None

    eps_estimate = _decimal(
        _calendar_value(
            calendar,
            "Earnings Average",
            "Earnings Estimate",
            "EPS Estimate",
            "EarningsAverage",
        )
    )

    return {
        "report_date": earnings_date,
        "eps_estimate": eps_estimate,
    }


def _event_from_earnings_dates(
    ticker: str,
    start: date,
    end: date,
) -> dict | None:
    obj = yf.Ticker(yahoo_symbol(ticker))
    frame = obj.get_earnings_dates(limit=8)

    if frame is None or frame.empty:
        return None

    candidates = []

    for index_value, row in frame.iterrows():
        report_date = _to_date(index_value)

        if report_date is None or report_date < start or report_date > end:
            continue

        reported_eps = None
        for col in ["Reported EPS", "ReportedEPS", "epsActual"]:
            if col in row.index:
                reported_eps = row[col]
                break

        try:
            is_unreported = reported_eps is None or pd.isna(reported_eps)
        except Exception:
            is_unreported = False

        estimate = None
        for col in ["EPS Estimate", "EPSEstimate", "epsEstimate"]:
            if col in row.index:
                estimate = _decimal(row[col])
                if estimate is not None:
                    break

        candidates.append(
            {
                "report_date": report_date,
                "eps_estimate": estimate,
                "unreported": is_unreported,
            }
        )

    if not candidates:
        return None

    unreported = [item for item in candidates if item["unreported"]]
    selected = min(
        unreported or candidates,
        key=lambda item: item["report_date"],
    )

    return {
        "report_date": selected["report_date"],
        "eps_estimate": selected["eps_estimate"],
    }


def _fetch_ticker_event(
    ticker: str,
    start: date,
    end: date,
) -> tuple[str, dict | None, str | None]:
    errors = []

    try:
        event = _event_from_calendar(ticker, start, end)
        if event is not None:
            return ticker, event, None
    except Exception as exc:
        errors.append(f"calendar: {exc}")

    try:
        event = _event_from_earnings_dates(ticker, start, end)
        if event is not None:
            return ticker, event, None
    except Exception as exc:
        errors.append(f"earnings_dates: {exc}")

    return ticker, None, " | ".join(errors) if errors else None


async def _fetch_all_events(
    tickers: list[str],
    start: date,
    end: date,
) -> list[tuple[str, dict | None, str | None]]:
    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=6) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _fetch_ticker_event,
                ticker,
                start,
                end,
            )
            for ticker in tickers
        ]
        return await asyncio.gather(*tasks)


async def refresh_earnings_calendar(
    db: Session,
    provider=None,
    horizon: str = "3month",
) -> dict:
    horizon_days = {
        "3month": 92,
        "6month": 184,
        "12month": 366,
    }

    if horizon not in horizon_days:
        raise ValueError("horizon must be 3month, 6month, or 12month")

    start = date.today()
    end = start + timedelta(days=horizon_days[horizon])

    registry = earnings_universe_registry(db)
    tickers = list(registry.keys())

    results = await _fetch_all_events(tickers, start, end)
    now = datetime.now(timezone.utc)

    parsed_events = []
    matched = []
    failures = []

    for ticker, event, error in results:
        if error:
            failures.append(f"{ticker}: {error}")

        if event is None:
            continue

        item = registry[ticker]
        impact_score = int(item["earnings_impact_score"])

        parsed_events.append(
            EarningsEvent(
                ticker=ticker,
                company_name=item.get("company_name") or ticker,
                sector=item.get("sector") or "Unknown",
                report_date=event["report_date"],
                fiscal_date_ending=None,
                eps_estimate=event["eps_estimate"],
                currency="USD",
                impact_score=impact_score,
                impact_level=_impact_level(impact_score),
                impact_note=IMPACT_NOTES.get(
                    impact_score,
                    "Upcoming earnings event.",
                ),
                related_tickers=",".join(RELATED_TICKERS.get(ticker, [])),
                refreshed_at=now,
            )
        )
        matched.append(ticker)

    if parsed_events:
        db.execute(delete(EarningsEvent))
        for event in parsed_events:
            db.add(event)
        db.commit()

    diagnostic = (
        f"Checked {len(tickers)} earnings-enabled stocks. "
        f"Found {len(parsed_events)} upcoming earnings events."
    )

    if failures:
        diagnostic += f" {len(failures)} Yahoo ticker lookups reported errors."

    if not parsed_events:
        diagnostic += " Existing stored earnings were preserved."

    return {
        "horizon": horizon,
        "received_market_events": len(tickers),
        "stored_blue_chip_events": len(parsed_events),
        "refreshed_at": now,
        "unique_market_symbols": len(tickers),
        "matched_blue_chip_symbols": sorted(matched),
        "returned_symbol_sample": tickers[:25],
        "diagnostic": diagnostic,
    }


def earnings_universe(db: Session) -> list[dict]:
    registry = earnings_universe_registry(db)
    rows = []

    for ticker, item in registry.items():
        rows.append(
            {
                "ticker": ticker,
                "company_name": item.get("company_name") or ticker,
                "sector": item.get("sector") or "Unknown",
                "impact_score": item["earnings_impact_score"],
            }
        )

    rows.sort(key=lambda row: (-row["impact_score"], row["ticker"]))
    return rows


def serialize_event(event: EarningsEvent) -> dict:
    related = [
        ticker
        for ticker in (event.related_tickers or "").split(",")
        if ticker
    ]

    return {
        "ticker": event.ticker,
        "company_name": event.company_name,
        "sector": event.sector,
        "report_date": event.report_date,
        "fiscal_date_ending": event.fiscal_date_ending,
        "eps_estimate": float(event.eps_estimate) if event.eps_estimate is not None else None,
        "currency": event.currency,
        "impact_score": event.impact_score,
        "impact_level": event.impact_level,
        "impact_note": event.impact_note,
        "related_tickers": related,
    }


def _monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_earnings(
    db: Session,
    week_offset: int = 0,
    min_impact: int = 0,
) -> dict:
    today = date.today()
    week_start = _monday_for(today) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    events = db.scalars(
        select(EarningsEvent)
        .where(
            EarningsEvent.report_date >= week_start,
            EarningsEvent.report_date <= week_end,
            EarningsEvent.impact_score >= min_impact,
        )
        .order_by(
            EarningsEvent.report_date.asc(),
            EarningsEvent.impact_score.desc(),
            EarningsEvent.ticker.asc(),
        )
    ).all()

    serialized = [serialize_event(event) for event in events]

    return {
        "week_start": week_start,
        "week_end": week_end,
        "total_events": len(serialized),
        "high_impact_events": sum(
            1 for event in serialized if event["impact_score"] >= 9
        ),
        "events": serialized,
    }


def upcoming_earnings(
    db: Session,
    days: int = 14,
    min_impact: int = 0,
) -> dict:
    start_date = date.today()
    end_date = start_date + timedelta(days=days)

    events = db.scalars(
        select(EarningsEvent)
        .where(
            EarningsEvent.report_date >= start_date,
            EarningsEvent.report_date <= end_date,
            EarningsEvent.impact_score >= min_impact,
        )
        .order_by(
            EarningsEvent.report_date.asc(),
            EarningsEvent.impact_score.desc(),
            EarningsEvent.ticker.asc(),
        )
    ).all()

    serialized = [serialize_event(event) for event in events]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_events": len(serialized),
        "events": serialized,
    }

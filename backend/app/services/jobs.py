from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import JobRun, MarketRefreshState
from app.providers.yahoo_finance import YahooFinanceError, YahooFinanceProvider
from app.security import sanitize_secret
from app.services.alerts import generate_all_alerts, generate_earnings_alerts
from app.services.earnings import refresh_earnings_calendar
from app.services.market_data import refresh_ticker
from app.services.rotation import rotation_universe
from app.services.screener_refresh import refresh_blue_chip_screener


def _start_job(db, name: str) -> JobRun:
    run = JobRun(
        job_name=name,
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_job(db, run: JobRun, status: str, detail: str):
    settings = get_settings()

    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.detail = sanitize_secret(
        detail,
        settings.alpha_vantage_api_key,
    )
    db.commit()
    db.refresh(run)


def _local_today():
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _already_attempted_today(db, ticker: str) -> bool:
    state = db.get(MarketRefreshState, ticker)

    if state is None:
        return False

    return state.last_attempt_date == _local_today()


def _record_attempt(
    db,
    *,
    ticker: str,
    status: str,
    newest_market_date=None,
    detail: str | None = None,
):
    settings = get_settings()

    state = db.get(MarketRefreshState, ticker)

    if state is None:
        state = MarketRefreshState(
            ticker=ticker,
            last_attempt_date=_local_today(),
            status=status,
        )
        db.add(state)

    state.last_attempt_date = _local_today()
    state.status = status
    state.newest_market_date = newest_market_date
    state.detail = sanitize_secret(
        detail,
        settings.alpha_vantage_api_key,
    )
    state.updated_at = datetime.now(timezone.utc)

    db.commit()


async def run_daily_market_job(force: bool = False) -> dict:
    settings = get_settings()
    db = SessionLocal()
    run = _start_job(db, "daily_market")

    refreshed = 0
    skipped = 0
    failed = 0
    failures = []

    try:
        provider = YahooFinanceProvider()

        symbols = [
            item["ticker"]
            for item in rotation_universe(include_themes=False)
        ]
        symbols.extend(settings.daily_watchlist_symbols)
        symbols = list(dict.fromkeys(symbols))

        for ticker in symbols:
            if not force and _already_attempted_today(db, ticker):
                skipped += 1
                continue

            try:
                result = await refresh_ticker(
                    db=db,
                    provider=provider,
                    ticker=ticker,
                )

                refreshed += 1

                _record_attempt(
                    db,
                    ticker=ticker,
                    status="SUCCESS",
                    newest_market_date=result.newest_date,
                    detail=(
                        f"Yahoo Finance received {result.received} daily bars."
                    ),
                )

            except YahooFinanceError as exc:
                failed += 1
                safe = str(exc)
                failures.append(f"{ticker}: {safe}")

                _record_attempt(
                    db,
                    ticker=ticker,
                    status="FAILED",
                    detail=safe,
                )

            except Exception as exc:
                failed += 1
                safe = str(exc)
                failures.append(f"{ticker}: {safe}")

                _record_attempt(
                    db,
                    ticker=ticker,
                    status="FAILED",
                    detail=safe,
                )

        alerts = generate_all_alerts(
            db=db,
            tickers=settings.daily_watchlist_symbols,
            min_score=settings.daily_alert_min_score,
        )

        detail = (
            f"Yahoo Finance: refreshed {refreshed} symbols; "
            f"skipped {skipped} already attempted today; "
            f"{failed} failed; generated/updated {len(alerts)} alerts."
        )

        if failures:
            detail += " Failures: " + " | ".join(failures[:5])

        if failed == 0:
            status = "SUCCESS"
        elif refreshed > 0 or skipped > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"

        _finish_job(db, run, status, detail)

        return {
            "job_name": "daily_market",
            "status": status,
            "detail": detail,
        }

    except Exception as exc:
        detail = f"Daily Yahoo Finance market job failed: {exc}"
        _finish_job(db, run, "FAILED", detail)

        return {
            "job_name": "daily_market",
            "status": "FAILED",
            "detail": detail,
        }

    finally:
        db.close()


async def run_daily_screener_job(force_fundamentals: bool = False) -> dict:
    settings = get_settings()
    db = SessionLocal()
    run = _start_job(db, "daily_screener")

    try:
        result = await refresh_blue_chip_screener(
            db=db,
            force_fundamentals=force_fundamentals,
            fundamentals_max_age_days=settings.screener_fundamentals_max_age_days,
        )

        detail = (
            f"Blue-chip screener: {result['prices_succeeded']}/{result['universe_size']} "
            f"price series refreshed; "
            f"{result['fundamentals_refreshed']} fundamentals refreshed; "
            f"{result['fundamentals_skipped_fresh']} fresh fundamentals reused; "
            f"{result['fundamentals_failed']} fundamentals failed."
        )

        if result["fundamental_failures"]:
            detail += " Failures: " + " | ".join(
                result["fundamental_failures"][:5]
            )

        if (
            result["prices_failed"] == 0
            and result["fundamentals_failed"] == 0
        ):
            status = "SUCCESS"
        elif result["prices_succeeded"] > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"

        _finish_job(db, run, status, detail)

        return {
            "job_name": "daily_screener",
            "status": status,
            "detail": detail,
        }

    except Exception as exc:
        detail = f"Daily blue-chip screener refresh failed: {exc}"
        _finish_job(db, run, "FAILED", detail)

        return {
            "job_name": "daily_screener",
            "status": "FAILED",
            "detail": detail,
        }

    finally:
        db.close()


async def run_weekly_earnings_job() -> dict:
    db = SessionLocal()
    run = _start_job(db, "weekly_earnings")

    try:
        result = await refresh_earnings_calendar(
            db=db,
            horizon="3month",
        )

        alerts = generate_earnings_alerts(db, days=7)
        db.commit()

        detail = (
            f"Yahoo earnings: received {result['received_market_events']} calendar rows; "
            f"stored {result['stored_blue_chip_events']} blue-chip events; "
            f"generated/updated {len(alerts)} high-impact alerts."
        )

        if result.get("diagnostic"):
            detail += " Diagnostic: " + result["diagnostic"]

        status = (
            "SUCCESS"
            if result["stored_blue_chip_events"] > 0
            else "PARTIAL"
        )

        _finish_job(db, run, status, detail)

        return {
            "job_name": "weekly_earnings",
            "status": status,
            "detail": detail,
        }

    except Exception as exc:
        detail = f"Weekly Yahoo earnings job failed: {exc}"
        _finish_job(db, run, "FAILED", detail)

        return {
            "job_name": "weekly_earnings",
            "status": "FAILED",
            "detail": detail,
        }

    finally:
        db.close()


async def run_alert_generation_job() -> dict:
    settings = get_settings()
    db = SessionLocal()
    run = _start_job(db, "alert_generation")

    try:
        alerts = generate_all_alerts(
            db=db,
            tickers=settings.daily_watchlist_symbols,
            min_score=settings.daily_alert_min_score,
        )

        detail = (
            f"Generated/updated {len(alerts)} alerts from existing stored data. "
            "No external market-data API calls were made."
        )

        _finish_job(db, run, "SUCCESS", detail)

        return {
            "job_name": "alert_generation",
            "status": "SUCCESS",
            "detail": detail,
        }

    except Exception as exc:
        detail = sanitize_secret(
            f"Alert-generation job failed: {exc}",
            settings.alpha_vantage_api_key,
        )

        _finish_job(db, run, "FAILED", detail)

        return {
            "job_name": "alert_generation",
            "status": "FAILED",
            "detail": detail,
        }

    finally:
        db.close()

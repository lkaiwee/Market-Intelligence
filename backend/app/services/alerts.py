from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Alert, DailyPrice, EarningsEvent, FundamentalSnapshot, Stock
from app.services.earnings import serialize_event
from app.services.investment_analysis import build_investment_analysis
from app.services.rotation import build_rotation_report
from app.services.technical_analysis import MIN_ANALYSIS_BARS, build_technical_analysis


def _local_today():
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _severity(score: int) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 80:
        return "HIGH"
    if score >= 70:
        return "MEDIUM"
    return "INFO"


def _upsert_alert(
    db: Session,
    *,
    ticker: str,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    score: int | None = None,
    price: float | None = None,
) -> Alert:
    alert_date = _local_today()

    alert = db.scalar(
        select(Alert).where(
            Alert.alert_date == alert_date,
            Alert.ticker == ticker,
            Alert.alert_type == alert_type,
        )
    )

    if alert is None:
        alert = Alert(
            alert_date=alert_date,
            ticker=ticker,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            score=score,
            price=Decimal(str(price)) if price is not None else None,
            is_active=True,
        )
        db.add(alert)
    else:
        alert.severity = severity
        alert.title = title
        alert.message = message
        alert.score = score
        alert.price = Decimal(str(price)) if price is not None else None
        alert.is_active = True

    db.flush()
    return alert


def generate_stock_alerts(
    db: Session,
    tickers: list[str],
    min_score: int,
) -> list[Alert]:
    generated = []

    for ticker in tickers:
        stock = db.get(Stock, ticker)
        if stock is None:
            continue

        prices = db.scalars(
            select(DailyPrice)
            .where(DailyPrice.ticker == ticker)
            .order_by(DailyPrice.trade_date.asc())
        ).all()

        if len(prices) < MIN_ANALYSIS_BARS:
            continue

        snapshot = db.get(FundamentalSnapshot, ticker)

        if snapshot is not None:
            analysis = build_investment_analysis(stock, snapshot, prices)
            score = analysis["opportunity_score"]

            if score < min_score:
                continue

            pullback = analysis["pullback_pct"]
            message = (
                f"{ticker} opportunity score {score}/100. "
                f"Technical {analysis['technical_score']}/100, "
                f"fundamental {analysis['fundamental_score']}/100, "
                f"valuation {analysis['valuation_score']}/100. "
                f"Pullback {pullback:.2f}%, "
                f"RSI {analysis['rsi14'] if analysis['rsi14'] is not None else 'N/A'}, "
                f"trend {analysis['trend']}."
            )

            generated.append(
                _upsert_alert(
                    db,
                    ticker=ticker,
                    alert_type="INVESTMENT_SETUP",
                    severity=_severity(score),
                    title=f"{ticker} investment setup",
                    message=message,
                    score=score,
                    price=analysis["price"],
                )
            )

        else:
            analysis = build_technical_analysis(ticker, prices)
            score = analysis["technical_score"]

            if score < min_score:
                continue

            pullback = (
                analysis["pullback_52w_pct"]
                if analysis["pullback_52w_pct"] is not None
                else analysis["pullback_available_pct"]
            )

            message = (
                f"{ticker} technical score {score}/100. "
                f"Pullback {pullback:.2f}%, "
                f"RSI {analysis['rsi14'] if analysis['rsi14'] is not None else 'N/A'}, "
                f"trend {analysis['trend']}. "
                "No stored fundamentals were available, so this is a technical-only alert."
            )

            generated.append(
                _upsert_alert(
                    db,
                    ticker=ticker,
                    alert_type="TECHNICAL_SETUP",
                    severity=_severity(score),
                    title=f"{ticker} technical setup",
                    message=message,
                    score=score,
                    price=analysis["price"],
                )
            )

    return generated


def generate_rotation_alerts(db: Session) -> list[Alert]:
    generated = []

    try:
        report = build_rotation_report(db, include_themes=False)
    except ValueError:
        return generated

    generated.append(
        _upsert_alert(
            db,
            ticker="MARKET",
            alert_type="MARKET_REGIME",
            severity="HIGH" if report["market_regime"] != "NEUTRAL" else "INFO",
            title=f"Market regime: {report['market_regime']}",
            message=(
                f"Risk-on score {report['risk_on_score']}/100. "
                f"Strongest groups: {', '.join(report['strongest'])}. "
                f"Weakest groups: {', '.join(report['weakest'])}."
            ),
            score=report["risk_on_score"],
        )
    )

    for row in report["rows"][:3]:
        if row["rotation_score"] < 60:
            continue

        generated.append(
            _upsert_alert(
                db,
                ticker=row["ticker"],
                alert_type="ROTATION_LEADER",
                severity=_severity(row["rotation_score"]),
                title=f"{row['name']} rotation leadership",
                message=(
                    f"{row['ticker']} ranks #{row['rank']} with rotation score "
                    f"{row['rotation_score']}/100 ({row['flow']}). "
                    f"5D {row['return_5d']:.2f}%, 20D {row['return_20d']:.2f}%, "
                    f"20D relative strength vs SPY {row['relative_20d']:.2f}%."
                ),
                score=row["rotation_score"],
                price=row["price"],
            )
        )

    return generated


def generate_earnings_alerts(db: Session, days: int = 7) -> list[Alert]:
    today = _local_today()
    end = today + timedelta(days=days)

    events = db.scalars(
        select(EarningsEvent)
        .where(
            EarningsEvent.report_date >= today,
            EarningsEvent.report_date <= end,
            EarningsEvent.impact_score >= 9,
        )
        .order_by(
            EarningsEvent.report_date.asc(),
            EarningsEvent.impact_score.desc(),
        )
    ).all()

    generated = []

    for event in events:
        serialized = serialize_event(event)
        related = serialized["related_tickers"]

        message = (
            f"{event.company_name} reports on {event.report_date.isoformat()}. "
            f"Impact score {event.impact_score}/10 ({event.impact_level})."
        )

        if related:
            message += f" Related tickers: {', '.join(related)}."

        generated.append(
            _upsert_alert(
                db,
                ticker=event.ticker,
                alert_type="HIGH_IMPACT_EARNINGS",
                severity="HIGH",
                title=f"{event.ticker} earnings approaching",
                message=message,
                score=event.impact_score * 10,
            )
        )

    return generated


def generate_all_alerts(
    db: Session,
    tickers: list[str],
    min_score: int,
) -> list[Alert]:
    alerts = []
    alerts.extend(generate_stock_alerts(db, tickers, min_score))
    alerts.extend(generate_rotation_alerts(db))
    alerts.extend(generate_earnings_alerts(db))

    db.commit()

    for alert in alerts:
        db.refresh(alert)

    return alerts

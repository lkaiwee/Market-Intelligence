from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Alert, DailyPrice, EarningsEvent, FundamentalSnapshot, Stock
from app.scheduler import get_scheduler_status
from app.services.earnings import serialize_event
from app.services.investment_analysis import build_investment_analysis
from app.services.rotation import build_rotation_report
from app.services.technical_analysis import MIN_ANALYSIS_BARS, build_technical_analysis


def build_dashboard(db: Session) -> dict:
    settings = get_settings()

    market_regime = None
    risk_on_score = None
    strongest_rotation = []
    rotation_top = []

    try:
        rotation = build_rotation_report(db, include_themes=False)
        market_regime = rotation["market_regime"]
        risk_on_score = rotation["risk_on_score"]
        strongest_rotation = rotation["strongest"]
        rotation_top = rotation["rows"][:5]
    except ValueError:
        pass

    recent_date = datetime.now(timezone.utc).date() - timedelta(days=7)

    alerts = db.scalars(
        select(Alert)
        .where(
            Alert.alert_date >= recent_date,
            Alert.is_active.is_(True),
        )
        .order_by(
            Alert.alert_date.desc(),
            Alert.score.desc().nullslast(),
            Alert.created_at.desc(),
        )
        .limit(15)
    ).all()

    investment_results = []
    technical_results = []

    for ticker in settings.daily_watchlist_symbols:
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

        technical = build_technical_analysis(ticker, prices)
        technical_results.append(technical)

        snapshot = db.get(FundamentalSnapshot, ticker)
        if snapshot is not None:
            investment_results.append(
                build_investment_analysis(stock, snapshot, prices)
            )

    investment_results.sort(
        key=lambda item: item["opportunity_score"],
        reverse=True,
    )

    technical_results.sort(
        key=lambda item: item["technical_score"],
        reverse=True,
    )

    today = datetime.now(timezone.utc).date()
    earnings_end = today + timedelta(days=14)

    earnings = db.scalars(
        select(EarningsEvent)
        .where(
            EarningsEvent.report_date >= today,
            EarningsEvent.report_date <= earnings_end,
            EarningsEvent.impact_score >= 8,
        )
        .order_by(
            EarningsEvent.report_date.asc(),
            EarningsEvent.impact_score.desc(),
        )
        .limit(20)
    ).all()

    return {
        "generated_at": datetime.now(timezone.utc),
        "market_regime": market_regime,
        "risk_on_score": risk_on_score,
        "strongest_rotation": strongest_rotation,
        "rotation_top": rotation_top,
        "alerts": alerts,
        "top_investment_opportunities": investment_results[:5],
        "technical_watchlist": technical_results[:8],
        "upcoming_earnings": [serialize_event(event) for event in earnings],
        "scheduler": get_scheduler_status(),
    }

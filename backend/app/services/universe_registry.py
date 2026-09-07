from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_universe import CustomUniverseStock
from app.services.blue_chip_universe import BLUE_CHIP_UNIVERSE


def core_universe() -> dict[str, dict]:
    result = {}
    for ticker, (company_name, sector, impact_score) in BLUE_CHIP_UNIVERSE.items():
        result[ticker] = {
            "ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "industry": None,
            "screening_enabled": True,
            "earnings_enabled": True,
            "earnings_impact_score": impact_score,
            "is_core": True,
        }
    return result


def custom_universe(db: Session) -> dict[str, dict]:
    rows = db.scalars(
        select(CustomUniverseStock).order_by(CustomUniverseStock.ticker.asc())
    ).all()

    return {
        row.ticker: {
            "ticker": row.ticker,
            "company_name": row.company_name,
            "sector": row.sector,
            "industry": row.industry,
            "screening_enabled": row.screening_enabled,
            "earnings_enabled": row.earnings_enabled,
            "earnings_impact_score": row.earnings_impact_score,
            "is_core": False,
        }
        for row in rows
    }


def merged_universe(db: Session) -> dict[str, dict]:
    result = core_universe()
    for ticker, item in custom_universe(db).items():
        if ticker not in result:
            result[ticker] = item
    return result


def screening_universe(db: Session) -> dict[str, dict]:
    return {
        ticker: item
        for ticker, item in merged_universe(db).items()
        if item["screening_enabled"]
    }


def earnings_universe_registry(db: Session) -> dict[str, dict]:
    return {
        ticker: item
        for ticker, item in merged_universe(db).items()
        if item["earnings_enabled"]
    }

from app.services.fundamentals import serialize_fundamentals
from app.services.technical_analysis import build_technical_analysis


def build_investment_analysis(stock, snapshot, prices) -> dict:
    technical = build_technical_analysis(stock.ticker, prices)
    fundamental = serialize_fundamentals(stock, snapshot)

    technical_score = technical["technical_score"]
    fundamental_score = fundamental["fundamental_score"]
    valuation_score = fundamental["valuation_score"]
    leadership_score = fundamental["leadership_score"]

    opportunity_score = round(
        technical_score * 0.40
        + fundamental_score * 0.35
        + valuation_score * 0.15
        + leadership_score * 0.10
    )

    # Require fundamental quality for the strongest labels. This prevents a
    # technically oversold weak company from being called an exceptional setup.
    if opportunity_score >= 85 and fundamental_score >= 75:
        investment_signal = "HIGH_CONVICTION_WATCH"
    elif opportunity_score >= 75 and fundamental_score >= 65:
        investment_signal = "ATTRACTIVE"
    elif opportunity_score >= 60:
        investment_signal = "WATCH"
    else:
        investment_signal = "PASS"

    pullback_pct = (
        technical["pullback_52w_pct"]
        if technical["pullback_52w_pct"] is not None
        else technical["pullback_available_pct"]
    )

    warnings = list(technical.get("warnings", []))
    warnings.extend(fundamental.get("warnings", []))

    return {
        "ticker": stock.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "industry": stock.industry,

        "price": technical["price"],
        "latest_date": technical["latest_date"],

        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "valuation_score": valuation_score,
        "leadership_score": leadership_score,

        "opportunity_score": opportunity_score,
        "investment_signal": investment_signal,

        "pullback_pct": pullback_pct,
        "rsi14": technical["rsi14"],
        "trend": technical["trend"],

        "forward_pe": fundamental["forward_pe"],
        "peg_ratio": fundamental["peg_ratio"],
        "free_cash_flow_ttm": fundamental["free_cash_flow_ttm"],
        "free_cash_flow_yield": fundamental["free_cash_flow_yield"],
        "revenue_growth_yoy": fundamental["revenue_growth_yoy"],
        "earnings_growth_yoy": fundamental["earnings_growth_yoy"],
        "debt_to_equity": fundamental["debt_to_equity"],

        "warnings": warnings,
    }

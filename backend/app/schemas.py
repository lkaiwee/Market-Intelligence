from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DailyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class RefreshResult(BaseModel):
    ticker: str
    received: int
    inserted_or_updated: int
    newest_date: date | None = None


class TechnicalScoreBreakdown(BaseModel):
    trend_alignment: int = Field(ge=0, le=25)
    momentum: int = Field(ge=0, le=25)
    pullback_setup: int = Field(ge=0, le=25)
    volume_volatility: int = Field(ge=0, le=15)
    price_confirmation: int = Field(ge=0, le=10)


class TechnicalAnalysisOut(BaseModel):
    ticker: str
    latest_date: date
    history_bars: int
    price: float

    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None

    ema9: float | None = None
    ema20: float | None = None

    rsi14: float | None = None

    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    atr14: float | None = None
    atr_pct: float | None = None

    avg_volume20: float | None = None
    volume_ratio: float | None = None

    high_available: float
    pullback_available_pct: float

    high_52w: float | None = None
    pullback_52w_pct: float | None = None

    trend: str
    technical_score: int = Field(ge=0, le=100)
    signal: str
    score_breakdown: TechnicalScoreBreakdown
    warnings: list[str] = []


class FundamentalRefreshOut(BaseModel):
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    updated_at: datetime


class FundamentalOut(BaseModel):
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    market_cap: float | None = None
    revenue_ttm: float | None = None
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None

    profit_margin: float | None = None
    operating_margin: float | None = None
    roe: float | None = None

    trailing_pe: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None

    operating_cashflow_ttm: float | None = None
    capex_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    free_cash_flow_margin: float | None = None
    free_cash_flow_yield: float | None = None

    total_debt: float | None = None
    cash_and_equivalents: float | None = None
    shareholder_equity: float | None = None
    debt_to_equity: float | None = None
    net_cash: float | None = None

    fundamental_score: int
    valuation_score: int
    leadership_score: int

    updated_at: datetime
    warnings: list[str] = []


class InvestmentAnalysisOut(BaseModel):
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    price: float
    latest_date: date

    technical_score: int
    fundamental_score: int
    valuation_score: int
    leadership_score: int

    opportunity_score: int
    investment_signal: str

    pullback_pct: float
    rsi14: float | None = None
    trend: str

    forward_pe: float | None = None
    peg_ratio: float | None = None
    free_cash_flow_ttm: float | None = None
    free_cash_flow_yield: float | None = None
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None
    debt_to_equity: float | None = None

    warnings: list[str] = []


class RotationUniverseItem(BaseModel):
    ticker: str
    name: str
    group: str


class RotationRefreshItem(BaseModel):
    ticker: str
    status: str
    received: int = 0
    newest_date: date | None = None
    detail: str | None = None


class RotationRefreshOut(BaseModel):
    requested: int
    succeeded: int
    failed: int
    items: list[RotationRefreshItem]


class RotationRow(BaseModel):
    rank: int
    ticker: str
    name: str
    group: str
    latest_date: date
    price: float

    return_1d: float
    return_5d: float
    return_20d: float

    relative_1d: float
    relative_5d: float
    relative_20d: float

    momentum_20d: float
    rotation_score: int = Field(ge=0, le=100)
    flow: str


class RotationReportOut(BaseModel):
    latest_date: date
    benchmark: str
    market_regime: str
    risk_on_score: int = Field(ge=0, le=100)
    strongest: list[str]
    weakest: list[str]
    rows: list[RotationRow]
    warnings: list[str] = []


class EarningsUniverseItem(BaseModel):
    ticker: str
    company_name: str
    sector: str
    impact_score: int = Field(ge=1, le=10)


class EarningsRefreshOut(BaseModel):
    horizon: str
    received_market_events: int
    stored_blue_chip_events: int
    refreshed_at: datetime

    unique_market_symbols: int = 0
    matched_blue_chip_symbols: list[str] = []
    returned_symbol_sample: list[str] = []
    diagnostic: str | None = None


class EarningsEventOut(BaseModel):
    ticker: str
    company_name: str
    sector: str
    report_date: date
    fiscal_date_ending: date | None = None
    eps_estimate: float | None = None
    currency: str | None = None
    impact_score: int = Field(ge=1, le=10)
    impact_level: str
    impact_note: str
    related_tickers: list[str]


class WeeklyEarningsOut(BaseModel):
    week_start: date
    week_end: date
    total_events: int
    high_impact_events: int
    events: list[EarningsEventOut]


class UpcomingEarningsOut(BaseModel):
    start_date: date
    end_date: date
    total_events: int
    events: list[EarningsEventOut]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_date: date
    ticker: str
    alert_type: str
    severity: str
    title: str
    message: str
    score: int | None = None
    price: Decimal | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    detail: str | None = None


class ScheduledJobOut(BaseModel):
    id: str
    next_run_time: datetime | None = None


class JobStatusOut(BaseModel):
    scheduler_enabled: bool
    scheduler_running: bool
    timezone: str
    daily_schedule: str
    weekly_schedule: str
    watchlist: list[str]
    jobs: list[ScheduledJobOut]


class ManualJobResultOut(BaseModel):
    job_name: str
    status: str
    detail: str


class DashboardOut(BaseModel):
    generated_at: datetime

    market_regime: str | None = None
    risk_on_score: int | None = None
    strongest_rotation: list[str] = []
    rotation_top: list[RotationRow] = []

    alerts: list[AlertOut] = []

    top_investment_opportunities: list[InvestmentAnalysisOut] = []
    technical_watchlist: list[TechnicalAnalysisOut] = []

    upcoming_earnings: list[EarningsEventOut] = []

    scheduler: JobStatusOut

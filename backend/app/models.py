from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    prices: Mapped[list["DailyPrice"]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
    )

    fundamentals: Mapped["FundamentalSnapshot | None"] = relationship(
        back_populates="stock",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_daily_price_ticker_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        ForeignKey("stocks.ticker", ondelete="CASCADE"),
        index=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 0))

    stock: Mapped["Stock"] = relationship(back_populates="prices")


class FundamentalSnapshot(Base):
    __tablename__ = "stock_fundamentals"

    ticker: Mapped[str] = mapped_column(
        ForeignKey("stocks.ticker", ondelete="CASCADE"),
        primary_key=True,
    )

    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    revenue_ttm: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    revenue_growth_yoy: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    earnings_growth_yoy: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    profit_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    trailing_pe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    peg_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_to_book: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    operating_cashflow_ttm: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    capex_ttm: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    free_cash_flow_ttm: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    total_debt: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    cash_and_equivalents: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    shareholder_equity: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    stock: Mapped["Stock"] = relationship(back_populates="fundamentals")


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "report_date",
            "fiscal_date_ending",
            name="uq_earnings_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100))
    report_date: Mapped[date] = mapped_column(Date, index=True)
    fiscal_date_ending: Mapped[date | None] = mapped_column(Date, nullable=True)
    eps_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    impact_score: Mapped[int] = mapped_column()
    impact_level: Mapped[str] = mapped_column(String(32))
    impact_note: Mapped[str] = mapped_column(String(500))
    related_tickers: Mapped[str] = mapped_column(String(1000), default="")
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "alert_date",
            "ticker",
            "alert_type",
            name="uq_alert_day_ticker_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_date: Mapped[date] = mapped_column(Date, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(100), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketRefreshState(Base):
    __tablename__ = "market_refresh_state"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_attempt_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    newest_market_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

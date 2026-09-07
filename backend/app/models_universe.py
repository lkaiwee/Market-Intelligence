from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomUniverseStock(Base):
    __tablename__ = "custom_universe_stocks"

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(150), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)

    screening_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    earnings_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    earnings_impact_score: Mapped[int] = mapped_column(Integer, default=7)

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PriceBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_daily_prices(self, ticker: str) -> list[PriceBar]:
        raise NotImplementedError

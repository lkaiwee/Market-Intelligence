from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Stock Market Intelligence API"
    database_url: str = (
        "postgresql+psycopg://stockuser:stockpass@localhost:5432/stock_dashboard"
    )

    alpha_vantage_api_key: str = "demo"
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"

    yahoo_history_period: str = "2y"

    scheduler_enabled: bool = True
    app_timezone: str = "Asia/Singapore"

    daily_job_day_of_week: str = "tue-sat"
    daily_job_hour: int = 7
    daily_job_minute: int = 15

    screener_job_day_of_week: str = "tue-sat"
    screener_job_hour: int = 7
    screener_job_minute: int = 35
    screener_fundamentals_max_age_days: int = 7

    weekly_job_day_of_week: str = "sun"
    weekly_job_hour: int = 18
    weekly_job_minute: int = 0

    daily_watchlist: str = "MSFT,NVDA,GOOGL,META,AVGO,MU,LRCX,JPM"
    daily_alert_min_score: int = 75

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def daily_watchlist_symbols(self) -> list[str]:
        seen = set()
        result = []

        for raw in self.daily_watchlist.split(","):
            ticker = raw.strip().upper()

            if ticker and ticker not in seen:
                seen.add(ticker)
                result.append(ticker)

        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()

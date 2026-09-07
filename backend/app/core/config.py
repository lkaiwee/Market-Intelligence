from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Stock Market Intelligence API"
    database_url: str = (
        "postgresql+psycopg://stockuser:stockpass@localhost:5432/stock_dashboard"
    )
    api_auth_required: bool = False
    api_access_token: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    scheduler_external: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value):
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def require_hosted_access_token(self):
        token = self.api_access_token.get_secret_value()
        if self.api_auth_required and len(token) < 32:
            raise ValueError("Hosted API requires an API_ACCESS_TOKEN of at least 32 characters")
        return self

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

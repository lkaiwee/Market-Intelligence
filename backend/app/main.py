from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.automation import router as automation_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.earnings import router as earnings_router
from app.api.routes.fundamentals import router as fundamentals_router
from app.api.routes.health import router as health_router
from app.api.routes.investment import router as investment_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.rotation import router as rotation_router
from app.api.routes.screener import router as screener_router
from app.api.routes.stocks import router as stocks_router
from app.api.routes.universe import router as universe_router
from app.core.config import get_settings
from app.database import Base, engine
from app.scheduler import start_scheduler, stop_scheduler
from app.services.security_cleanup import sanitize_persisted_secrets

from app import models  # noqa: F401
from app import models_universe  # noqa: F401
from app import models_portfolio  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    sanitize_persisted_secrets()
    start_scheduler()

    try:
        yield
    finally:
        stop_scheduler()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.7.4",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(stocks_router, prefix="/api")
app.include_router(fundamentals_router, prefix="/api")
app.include_router(screener_router, prefix="/api")
app.include_router(investment_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(rotation_router, prefix="/api")
app.include_router(earnings_router, prefix="/api")
app.include_router(universe_router, prefix="/api")
app.include_router(automation_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Stock Market Intelligence API is running.",
        "version": "0.7.4",
        "daily_market_provider": "Yahoo Finance",
        "screener_provider": "Yahoo Finance",
        "earnings_provider": "Yahoo Finance ticker calendars + earnings-dates fallback",
        "custom_universe": True,
        "portfolio_tracker": True,
        "frontend": "http://localhost:3000",
        "docs": "/docs",
    }

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.access import ApiAccessMiddleware
from app.database import Base, get_db
from app.main import app as deployed_app
from app.api.routes import backtest, journal, macro_surprise, market_regime, quality, risk, setups, stress, valuation


class ResearchRouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.app = FastAPI()
        for module in [backtest, journal, macro_surprise, market_regime, quality, risk, setups, stress, valuation]:
            self.app.include_router(module.router, prefix="/api")
        self.app.add_middleware(ApiAccessMiddleware, token="r" * 32)
        def database():
            with Session(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Bearer " + "r" * 32}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def test_all_nine_features_registered_in_deployed_app(self):
        paths = deployed_app.openapi()["paths"]
        for path in ["/api/backtest", "/api/journal", "/api/macro-surprise", "/api/market-regime",
                     "/api/quality/{ticker}", "/api/risk/size", "/api/setups", "/api/stress/analyze", "/api/valuation/{ticker}"]:
            self.assertIn(path, paths)

    def test_all_research_reads_and_writes_remain_protected(self):
        for method, path in [("get", "/api/journal"), ("post", "/api/journal"),
                             ("get", "/api/macro-surprise"), ("post", "/api/macro-surprise"),
                             ("get", "/api/market-regime"), ("get", "/api/setups"),
                             ("post", "/api/backtest"), ("post", "/api/risk/size"),
                             ("post", "/api/stress/analyze"), ("get", "/api/quality/MSFT"),
                             ("post", "/api/quality/MSFT/refresh"), ("post", "/api/valuation/MSFT")]:
            with self.subTest(path=path, method=method):
                self.assertEqual(getattr(self.client, method)(path).status_code, 401)

    def test_empty_database_is_explained_without_fabricated_data(self):
        for path in ["/api/journal", "/api/journal/analytics", "/api/macro-surprise",
                     "/api/market-regime", "/api/setups", "/api/quality/MSFT", "/api/valuation/MSFT"]:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn("NaN", response.text)
        response = self.client.post("/api/backtest", json={"ticker": "MSFT"}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("No stored", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

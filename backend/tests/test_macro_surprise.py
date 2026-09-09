import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import stdev

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.macro_surprise import router
from app.database import get_db
from app.models_macro_surprise import MacroRelease
from app.services.macro_surprise import macro_surprise_dashboard


class MacroSurpriseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        MacroRelease.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def payload(self, **changes):
        result = {"indicator": " US CPI MoM ", "release_at": "2025-09-11T08:30:00-04:00", "period": "August 2025",
                  "unit": "% MoM", "actual": "0.4", "consensus": "0.3", "previous": "0.2",
                  "actual_source": "BLS release, September 2025", "consensus_source": "Recorded survey before release"}
        return result | changes

    def test_create_edit_and_delete_persist_and_recalculate(self):
        response = self.client.post("/api/macro-surprise", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        row = response.json()["releases"][0]
        self.assertEqual(row["indicator"], "us cpi mom")
        self.assertEqual(row["unit"], "% mom")
        self.assertEqual(row["release_at"], "2025-09-11T12:30:00+00:00")
        self.assertAlmostEqual(row["surprise"], 0.1)
        self.assertAlmostEqual(row["surprise_pct"], 100 / 3)
        self.assertIsNone(row["standardized_surprise"])
        updated = self.client.put(f"/api/macro-surprise/{row['id']}", json=self.payload(actual="0.2"))
        self.assertEqual(updated.status_code, 200)
        self.assertAlmostEqual(updated.json()["releases"][0]["surprise"], -0.1)
        self.assertEqual(self.client.get("/api/macro-surprise").json()["count"], 1)
        self.assertEqual(self.client.delete(f"/api/macro-surprise/{row['id']}").json()["count"], 0)
        self.assertEqual(self.client.delete(f"/api/macro-surprise/{row['id']}").status_code, 404)

    def test_duplicate_is_conflict_and_does_not_poison_session(self):
        self.assertEqual(self.client.post("/api/macro-surprise", json=self.payload()).status_code, 201)
        self.assertEqual(self.client.post("/api/macro-surprise", json=self.payload()).status_code, 409)
        self.assertEqual(self.client.get("/api/macro-surprise").json()["count"], 1)

    def test_validation_rejects_unsourced_actual_future_actual_and_naive_time(self):
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        for changes in ({"actual_source": "  "}, {"consensus_source": None}, {"release_at": future},
                        {"release_at": "2025-09-11T08:30:00"}, {"indicator": " "}, {"actual": "NaN"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/macro-surprise", json=self.payload(**changes)).status_code, 422)
        planned = self.client.post("/api/macro-surprise", json=self.payload(release_at=future, actual=None, actual_source=None))
        self.assertEqual(planned.status_code, 201)
        self.assertEqual(planned.json()["releases"][0]["status"], "scheduled")

    def test_zero_and_negative_consensus_are_well_defined(self):
        response = self.client.post("/api/macro-surprise", json=self.payload(actual="0.1", consensus="0"))
        self.assertIsNone(response.json()["releases"][0]["surprise_pct"])
        row_id = response.json()["releases"][0]["id"]
        response = self.client.put(f"/api/macro-surprise/{row_id}", json=self.payload(actual="-1", consensus="-2"))
        self.assertEqual(response.json()["releases"][0]["surprise_pct"], 50)

    def add_release(self, day, surprise, unit="% mom", indicator="cpi"):
        self.db.add(MacroRelease(indicator=indicator, release_at=day, period=str(day.date()), unit=unit,
                                actual=Decimal(surprise) + 10, consensus=Decimal(10), actual_source="fixture", consensus_source="fixture"))

    def test_standardization_uses_only_strictly_prior_same_series_and_unit(self):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for month, surprise in enumerate([1, 2, 3, 4, 5]):
            self.add_release(base + timedelta(days=month * 30), surprise)
        target = base + timedelta(days=150)
        self.add_release(target, 6)
        self.add_release(base + timedelta(days=140), 1000, unit="% yoy")
        self.add_release(base + timedelta(days=145), 1000, indicator="pce")
        self.add_release(target, 1000, indicator="pce")
        self.add_release(base + timedelta(days=180), 1000)
        self.db.commit()
        response = macro_surprise_dashboard(self.db, now=target + timedelta(days=1))
        row = next(row for row in response["releases"] if row["indicator"] == "cpi" and row["release_at"] == target.isoformat())
        self.assertEqual(row["history_count"], 5)
        self.assertAlmostEqual(row["standardized_surprise"], 6 / stdev([1, 2, 3, 4, 5]))

    def test_zero_historical_dispersion_does_not_emit_infinity(self):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for index in range(6):
            self.add_release(base + timedelta(days=30 * index), 1)
        self.db.commit()
        result = macro_surprise_dashboard(self.db)["releases"][0]
        self.assertEqual(result["history_count"], 5)
        self.assertIsNone(result["standardized_surprise"])


if __name__ == "__main__":
    unittest.main()

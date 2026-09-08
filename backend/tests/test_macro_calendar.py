import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.access import ApiAccessMiddleware
from app.api.routes.earnings import router
from app.services import macro_calendar as macro


class CalendarParsingTests(unittest.TestCase):
    def test_ics_handles_folding_dst_and_invalid_events(self):
        events = macro.parse_bls_ics("\n".join([
            "BEGIN:VEVENT", "SUMMARY:Consumer Price ",
            " Index", "DTSTART;TZID=America/New_York:20260911T083000", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:Consumer Price Index",
            "DTSTART:20261110T133000Z", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:Consumer Price Index",
            "DTSTART;VALUE=DATE:20261399", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:State Job Openings and Labor Turnover",
            "DTSTART:20261110T133000Z", "END:VEVENT",
        ]))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["release_at_sgt"], "2026-09-11T20:30:00+08:00")
        self.assertEqual(events[1]["release_at_sgt"], "2026-11-10T21:30:00+08:00")

    def test_bea_uses_published_release_year_not_reference_year(self):
        html = """<table><tr><th>Year 2027</th></tr>
        <tr><td>January 29 8:30 AM</td><td>GDP, 4th Quarter and Year 2026</td></tr><tr>
        <td>January 29 8:30 AM</td><td>Personal Income and Outlays, December 2026</td>
        </tr></table>"""
        events = macro._parse_bea_rows(html, 2026)
        self.assertEqual(events[0]["release_date"], "2027-01-29")

    def test_missing_readings_do_not_produce_directional_predictions(self):
        for event_type in ("CPI", "PPI", "PCE", "JOBS", "JOLTS", "ECI", "FOMC"):
            prediction = macro._prediction_for(event_type, {})
            self.assertEqual(prediction["prediction"], "UNAVAILABLE")
            self.assertIsNone(prediction["confidence"])
            self.assertTrue(prediction["scenarios"])
        self.assertEqual(macro._macro_regime({})["label"], "INSUFFICIENT DATA")


class CalendarFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_bls_feed_returns_documented_fallback_including_eci(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(403, request=request))
        async with httpx.AsyncClient(transport=transport) as client:
            events, warning = await macro._fetch_bls_events(client)
        self.assertIn("saved 2026", warning)
        self.assertTrue(any(e["event_type"] == "ECI" and e["release_date"] == "2026-10-30" for e in events))

    async def test_cached_results_exclude_releases_that_have_passed(self):
        now = datetime.now(timezone.utc)
        old_cache = macro._cache_payload, macro._cache_expires_at
        try:
            macro._cache_payload = {"_cached_days": 120, "events": [
                {"release_at_et": (now - timedelta(seconds=1)).isoformat()},
                {"release_at_et": (now + timedelta(hours=1)).isoformat()},
            ]}
            macro._cache_expires_at = now + timedelta(minutes=10)
            result = await macro.get_macro_calendar()
            self.assertEqual(len(result["events"]), 1)
            self.assertNotIn("_cached_days", result)
        finally:
            macro._cache_payload, macro._cache_expires_at = old_cache


class MacroRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(ApiAccessMiddleware, token="test-owner-token-" * 3)
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "test-owner-token-" * 3}

    def test_route_remains_private_and_passes_refresh_options(self):
        with patch("app.api.routes.earnings.get_macro_calendar", new_callable=AsyncMock) as fetch:
            fetch.return_value = {"events": []}
            self.assertEqual(self.client.get("/api/earnings/macro").status_code, 401)
            fetch.assert_not_called()
            result = self.client.get("/api/earnings/macro?days=30&refresh=true", headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers["cache-control"], "no-store")
            fetch.assert_awaited_once_with(days=30, force_refresh=True)

    def test_invalid_horizon_does_not_call_government_sources(self):
        with patch("app.api.routes.earnings.get_macro_calendar", new_callable=AsyncMock) as fetch:
            for days in (0, 366):
                result = self.client.get(f"/api/earnings/macro?days={days}", headers=self.headers)
                self.assertEqual(result.status_code, 422)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()

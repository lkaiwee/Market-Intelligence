from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

import httpx


BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule/full"
FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

ET = ZoneInfo("America/New_York")
SGT = ZoneInfo("Asia/Singapore")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36 "
        "Market-Intelligence-Dashboard/0.7.5"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml,text/calendar,*/*",
}

# Fed decision dates are published on the official FOMC calendar.
# Decision time is normally 2:00 p.m. ET.
FOMC_DECISIONS: dict[int, list[tuple[int, int, bool]]] = {
    2026: [
        (1, 28, False),
        (3, 18, True),
        (4, 29, False),
        (6, 17, True),
        (7, 29, False),
        (9, 16, True),
        (10, 28, False),
        (12, 9, True),
    ],
    2027: [
        (1, 27, False),
        (3, 17, True),
        (4, 28, False),
        (6, 9, True),
        (7, 28, False),
        (9, 15, True),
        (10, 27, False),
        (12, 8, True),
    ],
}

# Fallback dates keep the calendar useful if BLS blocks a request temporarily.
# The live BLS iCalendar feed is always preferred.
BLS_FALLBACK_2026 = [
    # CPI
    ("CPI", "Consumer Price Index", 9, 11, 8, 30),
    ("CPI", "Consumer Price Index", 10, 14, 8, 30),
    ("CPI", "Consumer Price Index", 11, 10, 8, 30),
    ("CPI", "Consumer Price Index", 12, 10, 8, 30),
    # PPI
    ("PPI", "Producer Price Index", 9, 10, 8, 30),
    ("PPI", "Producer Price Index", 10, 15, 8, 30),
    ("PPI", "Producer Price Index", 11, 13, 8, 30),
    ("PPI", "Producer Price Index", 12, 15, 8, 30),
    # Employment Situation / NFP
    ("JOBS", "Employment Situation (Nonfarm Payrolls)", 10, 2, 8, 30),
    ("JOBS", "Employment Situation (Nonfarm Payrolls)", 11, 6, 8, 30),
    ("JOBS", "Employment Situation (Nonfarm Payrolls)", 12, 4, 8, 30),
    # JOLTS
    ("JOLTS", "JOLTS Job Openings", 9, 29, 10, 0),
    ("JOLTS", "JOLTS Job Openings", 11, 3, 10, 0),
    ("JOLTS", "JOLTS Job Openings", 12, 1, 10, 0),
    # Verified against https://www.bls.gov/schedule/2026/home.htm on 2026-09-08.
    ("ECI", "Employment Cost Index", 10, 30, 8, 30),
]

# BEA Personal Income and Outlays contains the Fed-preferred PCE price indexes.
BEA_PCE_FALLBACK_2026 = [
    (9, 30),
    (10, 29),
    (11, 25),
    (12, 23),
]

CACHE_TTL = timedelta(minutes=30)
_cache_payload: dict[str, Any] | None = None
_cache_expires_at: datetime | None = None


class _TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.current: list[str] = []
        self.rows: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "tr":
            self.in_row = True
            self.current = []

    def handle_data(self, data: str):
        if self.in_row:
            value = " ".join(data.split())
            if value:
                self.current.append(value)

    def handle_endtag(self, tag: str):
        if tag.lower() == "tr" and self.in_row:
            row = " ".join(self.current).strip()
            if row:
                self.rows.append(row)
            self.current = []
            self.in_row = False


def _event(
    *,
    event_type: str,
    title: str,
    release_at_et: datetime,
    source: str,
    source_url: str,
    impact_score: int,
    note: str,
) -> dict[str, Any]:
    if release_at_et.tzinfo is None:
        release_at_et = release_at_et.replace(tzinfo=ET)
    else:
        release_at_et = release_at_et.astimezone(ET)

    release_at_sgt = release_at_et.astimezone(SGT)

    return {
        "event_type": event_type,
        "title": title,
        "release_date": release_at_et.date().isoformat(),
        "release_at_et": release_at_et.isoformat(),
        "release_at_sgt": release_at_sgt.isoformat(),
        "source": source,
        "source_url": source_url,
        "impact_score": impact_score,
        "note": note,
    }


def _unfold_ics(text: str) -> list[str]:
    unfolded: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw)
    return unfolded


def _parse_ics_datetime(line: str) -> datetime | None:
    if ":" not in line:
        return None

    key, value = line.split(":", 1)
    value = value.strip()

    if len(value) == 8 and value.isdigit():
        try:
            parsed = datetime.strptime(value, "%Y%m%d")
            return parsed.replace(tzinfo=ET)
        except ValueError:
            return None

    formats = ["%Y%m%dT%H%M%S", "%Y%m%dT%H%M"]
    parsed = None

    for fmt in formats:
        try:
            parsed = datetime.strptime(value.rstrip("Z"), fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        return None

    if value.endswith("Z"):
        return parsed.replace(tzinfo=timezone.utc).astimezone(ET)

    # The BLS feed publishes Eastern release times.
    if "TZID=" in key.upper():
        tzid = key.split("TZID=", 1)[1].split(";", 1)[0]
        try:
            return parsed.replace(tzinfo=ZoneInfo(tzid))
        except Exception:
            pass

    return parsed.replace(tzinfo=ET)


def _classify_bls_summary(summary: str) -> tuple[str, str, int, str] | None:
    lowered = summary.lower()

    if lowered.startswith("state "):
        return None

    if "employment situation" in lowered:
        return (
            "JOBS",
            "Employment Situation (Nonfarm Payrolls)",
            10,
            "Payroll growth, unemployment and wages can rapidly change Fed-rate expectations.",
        )

    if "consumer price index" in lowered:
        return (
            "CPI",
            "Consumer Price Index",
            10,
            "Headline and core CPI are major drivers of Treasury yields and Fed expectations.",
        )

    if "producer price index" in lowered:
        return (
            "PPI",
            "Producer Price Index",
            9,
            "Producer inflation can change expectations for future consumer inflation and margins.",
        )

    if "job openings and labor turnover" in lowered:
        return (
            "JOLTS",
            "JOLTS Job Openings",
            8,
            "Job openings and quits help measure labour-market tightness before the next FOMC meeting.",
        )

    if "employment cost index" in lowered:
        return (
            "ECI",
            "Employment Cost Index",
            8,
            "Compensation growth is watched for signs of persistent wage-driven inflation.",
        )

    return None


def parse_bls_ics(text: str) -> list[dict[str, Any]]:
    lines = _unfold_ics(text)
    events: list[dict[str, Any]] = []
    current: dict[str, str] | None = None

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue

        if line == "END:VEVENT":
            if not current:
                current = None
                continue

            summary = current.get("SUMMARY", "")
            classified = _classify_bls_summary(summary)
            release_at = _parse_ics_datetime(current.get("DTSTART", ""))

            if classified and release_at:
                event_type, title, impact_score, note = classified
                events.append(
                    _event(
                        event_type=event_type,
                        title=title,
                        release_at_et=release_at,
                        source="U.S. Bureau of Labor Statistics",
                        source_url=BLS_SCHEDULE_URL,
                        impact_score=impact_score,
                        note=note,
                    )
                )

            current = None
            continue

        if current is None or ":" not in line:
            continue

        key = line.split(":", 1)[0].split(";", 1)[0].upper()
        if key in {"SUMMARY", "DTSTART"}:
            current[key] = line

            if key == "SUMMARY":
                current[key] = line.split(":", 1)[1].strip()

    return events


def _fallback_bls_events() -> list[dict[str, Any]]:
    result = []

    for event_type, title, month, day, hour, minute in BLS_FALLBACK_2026:
        notes = {
            "CPI": "Headline and core CPI are major drivers of Treasury yields and Fed expectations.",
            "PPI": "Producer inflation can change expectations for future consumer inflation and margins.",
            "JOBS": "Payroll growth, unemployment and wages can rapidly change Fed-rate expectations.",
            "JOLTS": "Job openings and quits help measure labour-market tightness.",
            "ECI": "Compensation growth helps track persistent wage-driven inflation.",
        }

        result.append(
            _event(
                event_type=event_type,
                title=title,
                release_at_et=datetime(2026, month, day, hour, minute, tzinfo=ET),
                source="U.S. Bureau of Labor Statistics",
                source_url=BLS_SCHEDULE_URL,
                impact_score=10 if event_type in {"CPI", "JOBS"} else 9 if event_type == "PPI" else 8,
                note=notes[event_type],
            )
        )

    return result


async def _fetch_bls_events(client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], str | None]:
    try:
        response = await client.get(BLS_ICS_URL)
        response.raise_for_status()
        events = parse_bls_ics(response.text)
        if events:
            return events, None
        return _fallback_bls_events(), "BLS live calendar returned no recognised events; 2026 fallback dates were used."
    except Exception:
        return _fallback_bls_events(), "BLS live calendar unavailable; saved 2026 dates were used. Check the official schedule for changes."


MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
    )
    if name
}


def _parse_bea_rows(html: str, year: int) -> list[dict[str, Any]]:
    parser = _TableRows()
    parser.feed(html)

    events: list[dict[str, Any]] = []

    # Typical row text:
    # "September 30 8:30 AM News Personal Income and Outlays, August 2026 View"
    pattern = re.compile(
        r"\b(" + "|".join(MONTHS.keys()) + r")\s+"
        r"(\d{1,2})\s+"
        r"(\d{1,2}:\d{2})\s*([AP]M)\b"
        r".*?(Personal Income and Outlays[^|]*?)(?:\s+View)?$",
        re.IGNORECASE,
    )

    for row in parser.rows:
        published_year = re.search(r"\bYear\s+(\d{4})\b", row)
        if published_year:
            year = int(published_year.group(1))
        match = pattern.search(row)
        if not match:
            continue

        month_name, day_text, clock_text, ampm, title = match.groups()
        month = MONTHS[month_name.title()]
        day = int(day_text)
        parsed_clock = datetime.strptime(f"{clock_text} {ampm.upper()}", "%I:%M %p").time()

        release_at = datetime.combine(
            date(year, month, day),
            parsed_clock,
            tzinfo=ET,
        )

        events.append(
            _event(
                event_type="PCE",
                title="PCE Inflation / Personal Income & Outlays",
                release_at_et=release_at,
                source="U.S. Bureau of Economic Analysis",
                source_url=BEA_SCHEDULE_URL,
                impact_score=10,
                note=(
                    "The PCE price indexes are the Federal Reserve's preferred inflation measures. "
                    "Core PCE can materially change rate-cut or rate-hike expectations."
                ),
            )
        )

    return events


def _fallback_pce_events() -> list[dict[str, Any]]:
    return [
        _event(
            event_type="PCE",
            title="PCE Inflation / Personal Income & Outlays",
            release_at_et=datetime(2026, month, day, 8, 30, tzinfo=ET),
            source="U.S. Bureau of Economic Analysis",
            source_url=BEA_SCHEDULE_URL,
            impact_score=10,
            note=(
                "The PCE price indexes are the Federal Reserve's preferred inflation measures. "
                "Core PCE can materially change rate expectations."
            ),
        )
        for month, day in BEA_PCE_FALLBACK_2026
    ]


async def _fetch_bea_events(client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], str | None]:
    current_year = datetime.now(ET).year

    try:
        response = await client.get(BEA_SCHEDULE_URL)
        response.raise_for_status()
        events = _parse_bea_rows(response.text, current_year)

        if events:
            return events, None

        if current_year == 2026:
            return _fallback_pce_events(), "BEA live schedule could not be parsed; 2026 fallback PCE dates were used."

        return [], "BEA live schedule could not be parsed."
    except Exception:
        if current_year == 2026:
            return _fallback_pce_events(), "BEA schedule unavailable; saved 2026 PCE dates were used. Check the official schedule for changes."
        return [], "BEA schedule unavailable."


def _fomc_events() -> list[dict[str, Any]]:
    result = []

    for year, meetings in FOMC_DECISIONS.items():
        for month, day, has_sep in meetings:
            title = "FOMC Rate Decision"
            if has_sep:
                title += " + Economic Projections"

            result.append(
                _event(
                    event_type="FOMC",
                    title=title,
                    release_at_et=datetime(year, month, day, 14, 0, tzinfo=ET),
                    source="Federal Reserve",
                    source_url=FED_FOMC_URL,
                    impact_score=10,
                    note=(
                        "The policy statement, rate decision and Chair's press conference can move "
                        "equities, Treasury yields and the U.S. dollar. SEP meetings also include the dot plot."
                    ),
                )
            )

    return result


def _series_points(series: dict[str, Any]) -> list[tuple[date, float]]:
    points = []

    for item in series.get("data", []):
        period = item.get("period", "")
        if not re.fullmatch(r"M\d{2}", period):
            continue

        month = int(period[1:])
        if month < 1 or month > 12:
            continue

        try:
            points.append(
                (
                    date(int(item["year"]), month, 1),
                    float(item["value"].replace(",", "")),
                )
            )
        except Exception:
            continue

    points.sort(key=lambda value: value[0])
    return points


def _yoy(points: list[tuple[date, float]]) -> tuple[float | None, str | None]:
    if len(points) < 13:
        return None, None

    current_date, current_value = points[-1]
    prior = None

    for point_date, point_value in reversed(points[:-1]):
        if (
            point_date.year == current_date.year - 1
            and point_date.month == current_date.month
        ):
            prior = point_value
            break

    if prior in (None, 0):
        return None, current_date.isoformat()

    return round((current_value / prior - 1) * 100, 2), current_date.isoformat()


async def _fetch_macro_snapshot(
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], str | None]:
    now = datetime.now(ET)

    payload = {
        "seriesid": [
            "CUUR0000SA0",       # CPI-U all items, not seasonally adjusted
            "CUUR0000SA0L1E",    # CPI-U all items less food and energy
            "LNS14000000",       # unemployment rate
            "CES0000000001",     # total nonfarm payroll employment (thousands)
        ],
        "startyear": str(now.year - 2),
        "endyear": str(now.year),
    }

    try:
        response = await client.post(BLS_API_URL, json=payload)
        response.raise_for_status()
        body = response.json()

        if body.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(body.get("message") or "BLS API request failed")

        series_by_id = {
            item.get("seriesID"): item
            for item in body.get("Results", {}).get("series", [])
        }

        headline_points = _series_points(series_by_id.get("CUUR0000SA0", {}))
        core_points = _series_points(series_by_id.get("CUUR0000SA0L1E", {}))
        unemployment_points = _series_points(series_by_id.get("LNS14000000", {}))
        payroll_points = _series_points(series_by_id.get("CES0000000001", {}))

        headline_yoy, headline_period = _yoy(headline_points)
        core_yoy, core_period = _yoy(core_points)

        unemployment = (
            round(unemployment_points[-1][1], 2)
            if unemployment_points
            else None
        )
        unemployment_period = (
            unemployment_points[-1][0].isoformat()
            if unemployment_points
            else None
        )

        payroll_change = None
        payroll_period = None

        if len(payroll_points) >= 2:
            payroll_change = round(
                payroll_points[-1][1] - payroll_points[-2][1],
                1,
            )
            payroll_period = payroll_points[-1][0].isoformat()

        snapshot = {
            "headline_cpi_yoy": headline_yoy,
            "headline_cpi_period": headline_period,
            "core_cpi_yoy": core_yoy,
            "core_cpi_period": core_period,
            "unemployment_rate": unemployment,
            "unemployment_period": unemployment_period,
            "payroll_change_k": payroll_change,
            "payroll_period": payroll_period,
        }

        missing = any(snapshot[key] is None for key in (
            "headline_cpi_yoy", "core_cpi_yoy", "unemployment_rate", "payroll_change_k"
        ))
        return snapshot, ("Some official readings are unavailable; affected model biases are withheld." if missing else None)

    except Exception:
        return {
            "headline_cpi_yoy": None,
            "headline_cpi_period": None,
            "core_cpi_yoy": None,
            "core_cpi_period": None,
            "unemployment_rate": None,
            "unemployment_period": None,
            "payroll_change_k": None,
            "payroll_period": None,
        }, "BLS latest-data API unavailable. Model biases are withheld until official readings are available."


def _inflation_state(snapshot: dict[str, Any]) -> str:
    headline = snapshot.get("headline_cpi_yoy")
    core = snapshot.get("core_cpi_yoy")

    values = [value for value in [headline, core] if value is not None]
    if not values:
        return "UNKNOWN"

    if (headline is not None and headline >= 3.2) or (core is not None and core >= 3.0):
        return "HOT"

    if (headline is not None and headline <= 2.5) and (core is not None and core <= 2.5):
        return "COOL"

    return "ELEVATED"


def _labor_state(snapshot: dict[str, Any]) -> str:
    payroll = snapshot.get("payroll_change_k")
    unemployment = snapshot.get("unemployment_rate")

    if payroll is None and unemployment is None:
        return "UNKNOWN"

    if (payroll is not None and payroll < 75) or (
        unemployment is not None and unemployment >= 4.7
    ):
        return "WEAK"

    if (payroll is not None and payroll >= 225) and (
        unemployment is None or unemployment <= 4.0
    ):
        return "HOT"

    return "BALANCED"


def _prediction_for(
    event_type: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    inflation = _inflation_state(snapshot)
    labor = _labor_state(snapshot)

    prediction = "BULLISH"
    equity_bias = "BULLISH"
    policy_bias = "DOVISH"
    confidence = 55
    rationale = "Current official data is consistent with a soft-landing setup."

    if event_type in {"CPI", "PPI", "PCE", "ECI"}:
        if inflation == "HOT":
            prediction = "HAWKISH"
            equity_bias = "BEARISH"
            policy_bias = "HAWKISH"
            confidence = 68
            rationale = (
                "Inflation remains sufficiently elevated that an upside surprise would "
                "raise higher-for-longer or rate-hike risk."
            )
        elif inflation == "COOL":
            prediction = "BULLISH"
            equity_bias = "BULLISH"
            policy_bias = "DOVISH"
            confidence = 66
            rationale = (
                "Inflation is near the Fed's desired direction, so another soft reading "
                "would generally support lower yields and risk assets."
            )
        else:
            prediction = "HAWKISH"
            equity_bias = "BEARISH"
            policy_bias = "HAWKISH"
            confidence = 56
            rationale = (
                "Inflation is not clearly back at target. The release has asymmetric risk: "
                "a hot surprise is likely more damaging than a small cool surprise is helpful."
            )

    elif event_type in {"JOBS", "JOLTS"}:
        if labor == "WEAK":
            prediction = "BEARISH"
            equity_bias = "BEARISH"
            policy_bias = "DOVISH"
            confidence = 65
            rationale = (
                "Labour conditions are weak enough that further deterioration could trigger "
                "growth/recession concerns even if it increases rate-cut expectations."
            )
        elif labor == "HOT":
            prediction = "HAWKISH"
            equity_bias = "BEARISH"
            policy_bias = "HAWKISH"
            confidence = 62
            rationale = (
                "A hot labour market can delay easing and push yields higher, which is usually "
                "a headwind for long-duration growth stocks."
            )
        else:
            prediction = "BULLISH"
            equity_bias = "BULLISH"
            policy_bias = "NEUTRAL"
            confidence = 60
            rationale = (
                "Labour conditions look balanced. A moderate report would reinforce the "
                "soft-landing narrative without forcing the Fed materially more hawkish."
            )

    elif event_type == "FOMC":
        if inflation == "HOT":
            prediction = "HAWKISH"
            equity_bias = "BEARISH"
            policy_bias = "HAWKISH"
            confidence = 67
            rationale = (
                "Inflation remains the dominant policy constraint, increasing the chance of "
                "higher-for-longer guidance or fewer expected cuts."
            )
        elif labor == "WEAK":
            prediction = "BEARISH"
            equity_bias = "BEARISH"
            policy_bias = "DOVISH"
            confidence = 58
            rationale = (
                "The Fed may sound more dovish, but a sharp labour slowdown can still be "
                "bearish because markets may focus on growth risk."
            )
        else:
            prediction = "BULLISH"
            equity_bias = "BULLISH"
            policy_bias = "DOVISH"
            confidence = 55
            rationale = (
                "With labour conditions balanced and inflation not accelerating sharply, "
                "a neutral-to-dovish policy path would generally support risk assets."
            )

    scenarios = {
        "CPI": {
            "upside": "Hotter than expected → HAWKISH / yields up / QQQ and semis at risk.",
            "base": "Near expectations → reaction depends on core services and revisions.",
            "downside": "Cooler than expected → BULLISH / yields down / growth stocks benefit.",
        },
        "PPI": {
            "upside": "Hot PPI → HAWKISH inflation read-through and margin pressure.",
            "base": "In line → usually secondary to CPI/PCE unless components surprise.",
            "downside": "Soft PPI → BULLISH if it confirms pipeline disinflation.",
        },
        "PCE": {
            "upside": "Hot core PCE → HAWKISH / fewer cuts or higher-for-longer risk.",
            "base": "In line → focus shifts to income, spending and core-services details.",
            "downside": "Cool core PCE → BULLISH / lower yields / easier Fed path.",
        },
        "JOBS": {
            "upside": "Very strong jobs/wages → HAWKISH because the Fed can stay restrictive.",
            "base": "Moderate hiring with stable unemployment → BULLISH soft-landing outcome.",
            "downside": "Very weak payrolls or unemployment spike → BEARISH growth scare.",
        },
        "JOLTS": {
            "upside": "Job openings surge → HAWKISH labour-tightness signal.",
            "base": "Gradual cooling → BULLISH soft-landing signal.",
            "downside": "Sharp collapse in openings → BEARISH growth concern.",
        },
        "FOMC": {
            "upside": "Higher dots / fewer cuts / hike language → HAWKISH and usually equity-negative.",
            "base": "Policy matches expectations → Powell guidance becomes the key catalyst.",
            "downside": "More cuts / clearly dovish guidance → BULLISH unless driven by recession risk.",
        },
        "ECI": {
            "upside": "Hot wage costs → HAWKISH because services inflation may stay sticky.",
            "base": "In line → limited reaction unless other inflation data disagree.",
            "downside": "Cool wage growth → BULLISH disinflation signal.",
        },
    }.get(
        event_type,
        {
            "upside": "Stronger/hotter than expected can raise yields.",
            "base": "In-line data usually reduces event risk.",
            "downside": "Softer data can help rates unless it signals a growth shock.",
        },
    )

    required = {
        "CPI": ("headline_cpi_yoy", "core_cpi_yoy"),
        "PPI": ("headline_cpi_yoy", "core_cpi_yoy"),
        "PCE": ("headline_cpi_yoy", "core_cpi_yoy"),
        "ECI": ("headline_cpi_yoy", "core_cpi_yoy"),
        "JOBS": ("unemployment_rate", "payroll_change_k"),
        "JOLTS": ("unemployment_rate", "payroll_change_k"),
        "FOMC": ("headline_cpi_yoy", "core_cpi_yoy", "unemployment_rate", "payroll_change_k"),
    }.get(event_type, ())
    if any(snapshot.get(key) is None for key in required):
        prediction = equity_bias = policy_bias = "UNAVAILABLE"
        confidence = None
        rationale = "Required official readings are unavailable. These scenarios describe possible reactions; no current directional bias is assigned."

    return {
        "prediction": prediction,
        "equity_bias": equity_bias,
        "policy_bias": policy_bias,
        "confidence": confidence,
        "rationale": rationale,
        "scenarios": scenarios,
    }


def _macro_regime(snapshot: dict[str, Any]) -> dict[str, Any]:
    inflation = _inflation_state(snapshot)
    labor = _labor_state(snapshot)

    if any(snapshot.get(key) is None for key in (
        "headline_cpi_yoy", "core_cpi_yoy", "unemployment_rate", "payroll_change_k"
    )):
        label = "INSUFFICIENT DATA"
        market_bias = "UNAVAILABLE"
        explanation = "A current macro regime cannot be assigned until the required official readings are available."
    elif labor == "WEAK":
        label = "GROWTH RISK"
        market_bias = "BEARISH"
        explanation = (
            "Labour deterioration is large enough that growth risk may outweigh the benefit "
            "of easier monetary policy."
        )
    elif inflation == "HOT":
        label = "INFLATION / RATE RISK"
        market_bias = "HAWKISH"
        explanation = (
            "Inflation is still elevated, so hotter releases can lift Treasury yields and "
            "pressure rate-sensitive equities."
        )
    elif inflation == "COOL" and labor == "BALANCED":
        label = "SOFT LANDING"
        market_bias = "BULLISH"
        explanation = (
            "Cooling inflation with a balanced labour market is the most supportive combination "
            "for lower yields without a recession signal."
        )
    else:
        label = "MIXED / DATA DEPENDENT"
        market_bias = "BULLISH" if labor == "BALANCED" else "HAWKISH"
        explanation = (
            "The macro backdrop is mixed. Upcoming inflation and labour releases are likely to "
            "drive the next meaningful shift in rate expectations."
        )

    return {
        "label": label,
        "market_bias": market_bias,
        "inflation_state": inflation,
        "labor_state": labor,
        "explanation": explanation,
    }


def _dedupe(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []

    for item in sorted(events, key=lambda event: event["release_at_et"]):
        key = (
            item["event_type"],
            item["release_date"],
            item["title"],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


async def get_macro_calendar(
    days: int = 120,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    global _cache_payload, _cache_expires_at

    now_utc = datetime.now(timezone.utc)

    if (
        not force_refresh
        and _cache_payload is not None
        and _cache_expires_at is not None
        and now_utc < _cache_expires_at
        and _cache_payload.get("_cached_days") == days
    ):
        cached = {
            key: value
            for key, value in _cache_payload.items()
            if not key.startswith("_")
        }
        cached["events"] = [event for event in cached["events"]
                            if datetime.fromisoformat(event["release_at_et"]) >= now_utc]
        return cached

    timeout = httpx.Timeout(20.0, connect=10.0)

    async with httpx.AsyncClient(
        headers=HTTP_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        (bls_events, bls_warning), (bea_events, bea_warning), (
            snapshot,
            snapshot_warning,
        ) = await asyncio.gather(
            _fetch_bls_events(client),
            _fetch_bea_events(client),
            _fetch_macro_snapshot(client),
        )

    events = _dedupe(bls_events + bea_events + _fomc_events())

    start = datetime.now(ET)
    end = start + timedelta(days=days)

    upcoming = []

    for item in events:
        release_at = datetime.fromisoformat(item["release_at_et"])

        if release_at < start or release_at > end:
            continue

        prediction = _prediction_for(item["event_type"], snapshot)

        upcoming.append(
            {
                **item,
                **prediction,
            }
        )

    upcoming.sort(key=lambda item: item["release_at_et"])

    warnings = [
        warning
        for warning in [bls_warning, bea_warning, snapshot_warning]
        if warning
    ]
    warnings.append("FOMC dates use the published 2026–2027 schedule saved on 2026-09-08. Meeting dates can change; check the linked official schedule.")

    payload = {
        "generated_at": now_utc.isoformat(),
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "timezone_note": "Official U.S. release times are Eastern Time; Singapore times are converted automatically.",
        "regime": _macro_regime(snapshot),
        "latest_data": snapshot,
        "events": upcoming,
        "warnings": warnings,
        "sources": [
            {
                "name": "U.S. Bureau of Labor Statistics",
                "url": BLS_SCHEDULE_URL,
                "covers": "CPI, PPI, Employment Situation, JOLTS, ECI",
            },
            {
                "name": "U.S. Bureau of Economic Analysis",
                "url": BEA_SCHEDULE_URL,
                "covers": "PCE inflation / Personal Income and Outlays",
            },
            {
                "name": "Federal Reserve",
                "url": FED_FOMC_URL,
                "covers": "FOMC rate decisions and SEP meetings",
            },
        ],
        "methodology": (
            "Pre-event labels are scenario-based model biases derived from the latest official "
            "BLS inflation and labour readings. They are not consensus forecasts and should not "
            "be treated as guaranteed market direction. Rule scores are hand-set model weights, "
            "not calibrated probabilities."
        ),
    }

    _cache_payload = {
        **payload,
        "_cached_days": days,
    }
    _cache_expires_at = now_utc + CACHE_TTL

    return payload

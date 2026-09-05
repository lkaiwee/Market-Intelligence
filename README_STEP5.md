# Step 5 Patch — Weekly Blue-Chip Earnings Calendar

Apply this patch on top of your working Step 4 project.

## New endpoints

- `GET /api/earnings/universe`
- `POST /api/earnings/refresh`
- `GET /api/earnings/weekly`
- `GET /api/earnings/upcoming`

## Why this design is API-efficient

Alpha Vantage's EARNINGS_CALENDAR endpoint returns the upcoming market earnings calendar
in one CSV response. The backend downloads it once and filters it locally to a curated
blue-chip / major-industry-leader universe.

That means one calendar refresh is normally one API request instead of one request per stock.

## Default blue-chip universe

The initial universe contains major US/US-listed leaders across:

- Mega-cap technology
- Semiconductors
- Software / cloud
- Financials
- Consumer
- Healthcare
- Industrials
- Energy
- Communication services

You can edit the universe later in:

`backend/app/services/earnings.py`

## Impact score

Each company receives a transparent importance score from 1 to 10.

Examples:

- 10: market-moving mega-cap / AI leaders
- 9: major semiconductor, cloud, financial or consumer leaders
- 8: large industry leaders
- 7: other blue-chip names in the initial universe

The score does NOT predict whether earnings will be good or bad. It measures how important
the event may be to the broader market or related industries.

## Related-ticker mapping

High-impact names also include related tickers.

Examples:

NVDA:
- AMD
- AVGO
- MU
- LRCX
- AMAT
- TSM
- SMH
- SOXX

MSFT:
- GOOGL
- AMZN
- ORCL
- CRM
- NVDA
- QQQ

This will later allow the GUI to show portfolio exposure warnings.

## Installation

Extract this ZIP into the existing inner project root and replace matching files.

Then:

```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

`http://127.0.0.1:8000/docs`

The API version should now be 0.5.0.

## First test

### 1. View the universe

`GET /api/earnings/universe`

### 2. Download the earnings calendar

`POST /api/earnings/refresh`

Use:

`horizon = 3month`

Expected success:

```json
{
  "horizon": "3month",
  "received_market_events": 5000,
  "stored_blue_chip_events": 40,
  "refreshed_at": "..."
}
```

The market-event count varies.

### 3. View this week's blue-chip earnings

`GET /api/earnings/weekly`

Use:

- `week_offset = 0`
- `min_impact = 0`

### 4. View next week's earnings

`GET /api/earnings/weekly`

Use:

- `week_offset = 1`

### 5. View the next 14 days

`GET /api/earnings/upcoming`

Use:

- `days = 14`
- `min_impact = 8`

## Notes

Alpha Vantage's earnings calendar supplies expected earnings dates, fiscal period,
EPS estimate and currency. It does not provide a reliable before-market / after-market
field in this endpoint, so this version deliberately does not invent one.

Later Step 6 will add:
- scheduled daily/weekly jobs
- persisted alerts
- notification-ready outputs

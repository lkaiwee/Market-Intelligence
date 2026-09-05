# Step 4 Patch — Daily Money Rotation Engine

Apply this patch on top of your working Step 3 project.

## New endpoints

- `POST /api/rotation/refresh`
- `GET /api/rotation`
- `GET /api/rotation/universe`

## Default rotation universe

Benchmark:
- SPY — S&P 500

Sectors:
- XLK — Technology
- XLC — Communication Services
- XLY — Consumer Discretionary
- XLF — Financials
- XLI — Industrials
- XLE — Energy
- XLV — Health Care
- XLU — Utilities
- XLP — Consumer Staples
- XLRE — Real Estate
- XLB — Materials

Optional themes:
- SOXX — Semiconductors
- IGV — Software
- CIBR — Cybersecurity
- IWM — Small Caps
- QQQ — Nasdaq 100

## Rotation model

For each ETF the engine calculates:

- 1-day return
- 5-day return
- 20-day return
- 1-day relative strength vs SPY
- 5-day relative strength vs SPY
- 20-day relative strength vs SPY
- 20-day trend slope proxy
- rotation score /100
- flow classification

Flow labels:

- STRONG_INFLOW
- INFLOW
- NEUTRAL
- OUTFLOW
- STRONG_OUTFLOW

The market regime is also classified as:

- RISK_ON
- NEUTRAL
- RISK_OFF

The regime uses the cross-sector rotation data and relative performance of growth/cyclical
groups versus defensive groups. It is a rules-based dashboard signal, not a market forecast.

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

## First test

### 1. See the ETF universe

Run:

`GET /api/rotation/universe`

### 2. Refresh core rotation data

Run:

`POST /api/rotation/refresh`

Use:

- `include_themes = false`

This downloads SPY plus the 11 sector ETFs.

IMPORTANT: This consumes 12 Alpha Vantage requests. With a free 25-request/day API limit,
do not repeatedly run it during development.

### 3. Generate rotation table

Run:

`GET /api/rotation`

Use:

- `include_themes = false`

You should receive ranked sectors and a market regime.

## Optional theme mode

If the theme ETFs have already been stored, call:

`GET /api/rotation?include_themes=true`

To download them using the rotation refresh endpoint:

`POST /api/rotation/refresh?include_themes=true`

This will request additional ETF data and consumes more of the daily API quota.

## Daily production design

Later, the scheduler will run this once after the US market close:

1. refresh rotation ETFs
2. calculate rotation table
3. save daily snapshot
4. display on the web GUI
5. generate alert only when leadership changes materially

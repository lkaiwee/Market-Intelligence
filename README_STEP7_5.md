# Step 7.5 — Portfolio Tracker + U.S. Macro Risk Calendar

> Hosted integration: GitHub Pages, Render, and Neon remain configured. Owner-token protection, the hosted CORS origin, and GitHub Actions refreshes are preserved. The local Windows commands below are reference instructions from the supplied package; they are not required for the deployed app.

The hosted integration shows BLS reference months, withholds directional model labels when required readings are missing, and labels the supplied hand-set confidence values as **rule scores**, not calibrated probabilities. Completed releases are removed from the upcoming list, including cached responses. Saved FOMC dates and fallback calendar use are identified in the page's data-source notes. The 2026 fallback includes the October 30 ECI release, verified against the [official BLS calendar](https://www.bls.gov/schedule/2026/home.htm).

Step 7.5 is built on top of the existing **Step 7.4 Portfolio Tracker**.

It preserves all Step 7.4 portfolio features and adds a U.S. macroeconomic
risk calendar directly to the Earnings page.

## Step 7.4 features retained

Portfolio page:

`/portfolio`

Retained features include:

- add/edit/remove portfolio positions
- entry price and share tracking
- cost basis and current market value
- unrealized P/L
- rules-based 2R target and 3R stretch target
- technical stop-loss
- support levels
- 20-day, 50-day and approximately 52-week breakout levels
- RSI, ATR, trend and technical score
- portfolio tickers included in scheduled market refreshes

## Step 7.5 feature

Earnings & Macro page:

`/earnings`

The page now combines:

1. Company earnings
2. U.S. inflation releases
3. U.S. labour-market releases
4. Federal Reserve rate decisions
5. Pre-event market-bias analysis

## U.S. events tracked

### Inflation

- CPI — Consumer Price Index
- PPI — Producer Price Index
- PCE — Personal Consumption Expenditures price indexes
- ECI — Employment Cost Index

### Jobs / labour market

- Employment Situation / Nonfarm Payrolls
- Unemployment rate
- JOLTS Job Openings

### Federal Reserve

- FOMC interest-rate decisions
- FOMC meetings with Summary of Economic Projections / dot plot

## Official sources

The feature uses official public sources:

- U.S. Bureau of Labor Statistics — release schedule and latest CPI/jobs data
- U.S. Bureau of Economic Analysis — Personal Income & Outlays / PCE schedule
- Federal Reserve — FOMC meeting calendar

The BLS release calendar is read from the official BLS iCalendar feed when
available. Fallback 2026 dates are included so a temporary government-site
failure does not blank the dashboard.

The macro endpoint caches results for 30 minutes.

## Market-bias model

The backend reads the latest official values for:

- headline CPI YoY
- core CPI YoY
- unemployment rate
- monthly nonfarm payroll change

It classifies the current environment as one of:

- SOFT LANDING
- INFLATION / RATE RISK
- GROWTH RISK
- MIXED / DATA DEPENDENT

Each event receives a pre-release model label:

- BULLISH
- HAWKISH
- BEARISH

Each event also shows:

- equity-market bias
- Fed/policy bias
- confidence percentage
- rationale
- hot/strong surprise scenario
- near-consensus scenario
- cool/weak surprise scenario

Example:

```text
CPI
Prediction: HAWKISH
Equity bias: BEARISH
Fed bias: HAWKISH

Hotter than expected:
Treasury yields likely rise and high-duration growth stocks may come under pressure.

Cooler than expected:
Treasury yields may fall and growth/technology stocks may benefit.
```

For jobs data, the model distinguishes between:

- strong labour data that may be hawkish for rates
- balanced labour data that supports a soft landing
- very weak labour data that may become bearish because of recession/growth risk

## Important limitation

The labels are scenario-based model biases, not guaranteed forecasts.

The most useful trading interpretation still depends on:

- actual release
- market consensus
- previous reading
- revisions
- Treasury-yield reaction
- positioning before the release

A future version can add actual-vs-consensus surprise scoring after each release.

## New API endpoint

Upcoming macro calendar:

`GET /api/earnings/macro?days=120`

Force a fresh government-data request:

`GET /api/earnings/macro?days=120&refresh=true`

## Version

FastAPI version after installation:

`0.7.5`

The root endpoint also reports:

```json
{
  "portfolio_tracker": true,
  "macro_risk_calendar": true
}
```

## Installation

This ZIP contains the Step 7.4 Portfolio Tracker files plus the Step 7.5
Macro Risk Calendar additions.

Extract the ZIP into your repository root:

```text
C:\Users\admin\Documents\market-intelligence-local
```

Replace matching files.

No new PostgreSQL migration is required for the macro calendar.

No additional Python or npm packages are required if your Step 7.4
environment is already installed.

### Start PostgreSQL

Make sure Docker Desktop is running, then:

```powershell
docker start stock_dashboard_postgres
```

### Start backend

```powershell
cd "C:\Users\admin\Documents\market-intelligence-local\backend"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload
```

Backend:

`http://127.0.0.1:8000`

Swagger:

`http://127.0.0.1:8000/docs`

### Start frontend

Your Windows installation currently reserves port 3000, so Step 7.5 also
allows port 3100 in FastAPI CORS.

```powershell
cd "C:\Users\admin\Documents\market-intelligence-local\frontend"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

npm run dev -- -p 3100
```

Open:

`http://localhost:3100`

Portfolio:

`http://localhost:3100/portfolio`

Earnings & Macro:

`http://localhost:3100/earnings`

## Files added by Step 7.5

- `backend/app/services/macro_calendar.py`
- `backend/app/api/routes/earnings.py`
- `frontend/app/earnings/page.tsx`
- `frontend/app/earnings/earnings.module.css`

## Files updated by Step 7.5

- `backend/app/main.py`
- `frontend/components/Sidebar.tsx`

All Step 7.4 Portfolio Tracker files remain included in the patch.

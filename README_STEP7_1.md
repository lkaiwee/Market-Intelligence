# Step 7.1 — Full Blue-Chip Screener + Yahoo Earnings Calendar

Apply this patch on top of Step 7.

## Fixes

### Screener

The full investment screener is no longer limited to stocks that you manually refreshed
through Alpha Vantage fundamentals.

Step 7.1 adds a curated blue-chip universe and uses Yahoo Finance for:

- 2 years of daily prices
- company metadata
- revenue / earnings growth
- operating/profit margins
- ROE
- forward / trailing P/E
- PEG
- price/book
- operating cash flow
- free cash flow
- debt
- cash

Fundamentals are refreshed when:
- missing, or
- older than 7 days

Prices are refreshed daily.

### Daily screener update

New endpoint:

`POST /api/screener/refresh`

Default:
- refresh all blue-chip prices
- refresh only missing/stale fundamentals

The scheduler also runs the blue-chip screener automatically at:

`Tue-Sat 07:35 Asia/Singapore`

This follows the previous US market close.

### Earnings

Upcoming earnings now use yfinance `Calendars` instead of Alpha Vantage.

New earnings refresh:
- fetches the next 90 days
- paginates Yahoo's earnings calendar
- filters locally to the blue-chip universe
- saves results into PostgreSQL

`POST /api/earnings/refresh?horizon=3month`

continues to work, but now uses Yahoo Finance.

The weekly scheduler continues to refresh the earnings calendar Sunday evening.

## Current blue-chip universe

Technology / internet:
AAPL, MSFT, NVDA, GOOGL, GOOG, AMZN, META

Semiconductors:
AVGO, AMD, MU, LRCX, AMAT, QCOM, TXN, INTC, TSM

Software / cloud:
ORCL, CRM, ADBE, NOW, PANW, CRWD, IBM

Financials:
JPM, BAC, WFC, GS, MS, V, MA, BRK.B

Consumer:
WMT, COST, HD, MCD, NKE, PG, KO, PEP

Healthcare:
LLY, UNH, JNJ, ABBV, MRK

Industrials:
CAT, GE, HON, RTX, BA

Energy:
XOM, CVX

Communication:
NFLX, DIS

## Install

Extract this ZIP into the existing inner project root.

Replace matching files.

Then stop both servers.

### Backend

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\backend"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload
```

### Frontend

In another PowerShell window:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\frontend"

npm run dev
```

No npm package changes are required.

## First sync

Open:

`http://localhost:3000/screener`

Click:

`Update Blue-Chip Screener`

The first run is the largest run because most stocks do not yet have Yahoo fundamental
snapshots. It can take roughly 1-3 minutes depending on Yahoo response speed.

After the first successful sync, later daily refreshes are much lighter because fundamentals
are reused for up to 7 days.

## Earnings

Open:

`http://localhost:3000/earnings`

Click:

`Refresh Upcoming Earnings`

The page should populate with upcoming blue-chip earnings from the next 90 days.

## API version

`0.7.1`

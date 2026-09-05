# Step 7.2 — Earnings Calendar Reliability Fix

Apply this patch on top of Step 7.1.

## Problem

The Step 7.1 whole-market `yfinance.Calendars` query can return a DataFrame whose
layout/schema differs across Yahoo/yfinance versions. That can result in zero matched
blue-chip events even though future earnings dates exist.

## Fix

Step 7.2 changes earnings refresh to a blue-chip-first strategy.

For every configured blue-chip ticker:

1. Call `Ticker.get_calendar()`
2. Parse the upcoming `Earnings Date`
3. Capture earnings estimate fields when Yahoo provides them
4. If calendar data is missing, fall back to `Ticker.get_earnings_dates(limit=8)`
5. Keep only dates inside the selected horizon
6. Store the earliest upcoming date in PostgreSQL

This is slower than one whole-market query, but much more reliable for a ~53-stock
blue-chip universe and does not consume Alpha Vantage quota.

## New diagnostics

The refresh response reports:

- requested blue-chip symbols
- symbols successfully checked
- symbols with upcoming earnings
- failed symbols
- a sample of failures
- matched tickers

## Install

Extract into your inner project root and replace matching files.

Restart backend:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\backend"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload
```

API version becomes:

`0.7.2`

## Test

Open:

`http://127.0.0.1:8000/docs`

Run:

`POST /api/earnings/refresh?horizon=3month`

A healthy result should have:

- `received_market_events` greater than 0
- `stored_blue_chip_events` greater than 0
- `matched_blue_chip_symbols` populated

Then open:

`http://localhost:3000/earnings`

and click:

`Refresh view`

or simply reload the page.

The existing Step 7.1 frontend does not need to be changed.

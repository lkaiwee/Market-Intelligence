# Step 7.4 — Portfolio Tracker

Adds a persistent portfolio tracker to the Market Intelligence dashboard.

## New page

`http://localhost:3000/portfolio`

## Features

- Add a portfolio position with:
  - ticker
  - average entry price
  - number of shares
  - optional purchase date
  - optional notes
- Automatically validates and refreshes the ticker with Yahoo Finance when added.
- Calculates:
  - cost basis
  - current market value using the latest stored daily close
  - unrealized P/L in dollars and percent
  - rule-based 2R target price
  - 3R stretch target
  - technical stop-loss level
  - nearest support and source
  - prior 20-day breakout level
  - prior 50-day breakout level
  - prior 52-week breakout level
  - breakout status
  - RSI, ATR, trend and technical score
- Edit average entry price, shares, purchase date and notes.
- Remove a position without deleting its stored market history.
- Refresh all portfolio stocks from Yahoo Finance from the Portfolio page.
- Portfolio tickers are automatically included in the scheduled daily market-data job and stock-alert pass.

## Level methodology

### Target

The main target is a transparent **2R forward target** based on the latest close and the current technical-stop distance.

A **3R stretch target** is also displayed.

### Stop

The stop uses the nearest valid support among:

- SMA20
- SMA50
- prior 20-day low
- prior 50-day low

An ATR buffer is applied and the stop is kept at least 1.5 ATR below the latest close. If support or ATR is unavailable, a conservative fallback is used.

### Breakouts

The tracker displays:

- prior 20-day high — primary breakout
- prior 50-day high
- prior 252-trading-day high — approximately 52 weeks

Breakout status can be:

- `BELOW`
- `NEAR_BREAKOUT`
- `ABOVE_LEVEL`
- `CONFIRMED`

`CONFIRMED` requires price to clear the primary level by an ATR buffer and volume to be at least 1.2× its recent average.

## Database

A new table is created automatically when FastAPI starts:

`portfolio_positions`

No manual SQL migration is required because this project uses `Base.metadata.create_all()` at startup.

## New API endpoints

- `GET /api/portfolio`
- `POST /api/portfolio/positions`
- `PUT /api/portfolio/positions/{ticker}`
- `DELETE /api/portfolio/positions/{ticker}`
- `POST /api/portfolio/refresh`

Example add-position body:

```json
{
  "ticker": "NVDA",
  "entry_price": 150.00,
  "shares": 10,
  "opened_on": "2026-09-07",
  "notes": "Core AI infrastructure position"
}
```

## Installation

This patch is designed to be applied **on top of Step 7.3**.

Extract it into the repository root and replace matching files.

Then restart the backend:

```powershell
cd "$HOME\Documents\market-intelligence\backend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Restart the frontend in a second PowerShell window:

```powershell
cd "$HOME\Documents\market-intelligence\frontend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
npm run dev
```

Open:

`http://localhost:3000/portfolio`

API version after installation: `0.7.4`

## Important

The generated target, stop and breakout levels are rules-based planning aids, not guaranteed outcomes or personalized financial advice. Overnight gaps can trade through stop prices.

# Step 6.2 Patch — Yahoo Finance Daily Market Data Provider

Apply this patch on top of Step 6.1.1.

## Architecture after Step 6.2

Daily prices / ETFs:
- Yahoo Finance via `yfinance`

Fundamentals:
- Alpha Vantage

Earnings calendar:
- Alpha Vantage

This removes the Alpha Vantage 25-request/day bottleneck from the daily market pipeline.

## What changes

### Yahoo Finance now powers:

- `POST /api/stocks/{ticker}/refresh`
- `POST /api/rotation/refresh`
- scheduled/manual daily market job
- watchlist daily OHLCV
- SPY + sector ETF daily OHLCV

### Alpha Vantage remains for:

- `POST /api/stocks/{ticker}/fundamentals/refresh`
- `POST /api/earnings/refresh`
- weekly earnings scheduler

## Historical depth

Yahoo Finance is configured to fetch approximately 2 years of daily history.

That is enough for:

- SMA20
- SMA50
- SMA200
- EMA9
- EMA20
- RSI14
- MACD
- ATR14
- true 52-week high
- true 52-week pullback

After refreshing a ticker with Step 6.2, `sma200` and `high_52w` should normally stop being null.

## Installation

Extract this ZIP into your existing inner project root and replace matching files.

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

The API version should now be:

`0.6.2`

## Recommended migration test

### 1. Refresh one stock using Yahoo Finance

Run:

`POST /api/stocks/MSFT/refresh`

A successful response should show several hundred daily bars rather than ~100.

### 2. Check analysis

Run:

`GET /api/stocks/MSFT/analysis`

Look for:

- `history_bars` around 400–520
- non-null `sma200`
- non-null `high_52w`
- non-null `pullback_52w_pct`

### 3. Refresh the full daily universe

Run:

`POST /api/jobs/daily/run?force=true`

The daily job no longer consumes Alpha Vantage quota.

### 4. Verify PostgreSQL

```sql
SELECT ticker, MAX(trade_date) AS latest_date, COUNT(*) AS rows
FROM daily_prices
GROUP BY ticker
ORDER BY ticker;
```

## Same-day protection

The existing same-day ticker refresh guard remains.

With:

`force=false`

tickers already attempted today are skipped.

Use:

`force=true`

once after installing Step 6.2 so existing tickers can be reloaded from Yahoo Finance with the deeper history.

## Notes

Yahoo Finance remains an external web data source and may occasionally throttle or return transient errors.
The provider raises a clean application error when it receives no usable daily data.

The provider abstraction remains intact, so another market-data vendor can be added later without rewriting the analysis engine.

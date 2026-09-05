# Step 3 Rate-Limit Fix

This patch fixes the Alpha Vantage free-tier `1 request per second` limit.

## What changed

The Alpha Vantage provider now:

- waits at least 1.2 seconds between API calls made by the same provider instance
- retries rate-limited requests with incremental backoff
- applies the same request helper to daily price data and fundamental data

This is especially important for:

`POST /api/stocks/{ticker}/fundamentals/refresh`

because it needs three requests:

1. OVERVIEW
2. CASH_FLOW
3. BALANCE_SHEET

## Apply

Extract this ZIP into your existing project root and replace the matching file.

Then restart Uvicorn.

No database reset is needed.
No `.env` change is needed.

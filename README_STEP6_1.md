# Step 6.1 Patch — Security, Quota Protection & Earnings Diagnostics

Apply this patch on top of your working Step 6 project.

## Fixes

### 1. API-key protection

Alpha Vantage error messages are sanitized before being:

- returned through Swagger
- written to job history
- shown in future GUI responses

The configured API key is replaced with `[REDACTED]`.

Because your old key appeared in a screenshot, rotate it before continuing if possible.

### 2. Same-day quota protection

The backend now stores a refresh-attempt record per ticker.

By default, the scheduled/manual daily job will NOT call Alpha Vantage again for a ticker
that it already attempted on the same Singapore calendar day.

This prevents accidental repeated clicks from burning the 25-request/day quota.

A manual daily run supports:

`force = false` (default)

Only use `force = true` when you intentionally want to bypass the protection.

### 3. Earnings diagnostics

The earnings refresh now reports:

- total calendar rows received
- blue-chip rows matched
- number of unique calendar symbols
- a sample of returned symbols
- a diagnostic message when zero blue-chip matches are found

Symbol normalization also handles common punctuation variants such as:

- `BRK-B`
- `BRK/B`
- `BRK.B`

## Install

Extract the ZIP into your existing inner project root and replace matching files.

Then restart:

```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API version should now show:

`0.6.1`

## Recommended first tests

### Safe test 1 — scheduler

`GET /api/jobs/status`

### Safe test 2 — alert generation

`POST /api/jobs/alerts/run`

### Safe test 3 — daily run quota guard

Run:

`POST /api/jobs/daily/run?force=false`

If the same tickers were already attempted today, the job should report many as skipped
instead of spending more API calls.

### Earnings diagnostics

When your Alpha Vantage daily quota has reset:

`POST /api/earnings/refresh?horizon=3month`

The response now includes diagnostics.

## New database table

`market_refresh_state`

This stores:
- ticker
- last attempt date
- status
- newest stored market date
- sanitized detail
- update time

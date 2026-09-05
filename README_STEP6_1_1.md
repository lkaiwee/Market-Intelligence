# Step 6.1.1 Patch — Global Alpha Vantage Daily-Quota Lock

Apply this patch on top of Step 6.1.

## What this fixes

In Step 6.1, per-ticker same-day protection worked only after each ticker had been attempted.
If Alpha Vantage's daily quota was already exhausted, repeated manual runs could still waste
one failed API call on the next unattempted ticker.

Step 6.1.1 adds a global quota lock.

When Alpha Vantage reports its daily request limit has been reached:

1. The backend stores a special quota state for the current Singapore calendar day.
2. All further daily market jobs with `force=false` make ZERO external market-data requests.
3. The lock naturally expires on the next Singapore calendar day.
4. `force=true` bypasses the lock if you intentionally want to retry, for example after
   changing to a different API key.

## Install

Extract the ZIP into the existing inner project root and replace matching files.

Then restart:

```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

No package installation or database reset is required.

The API version becomes `0.6.1.1`.

## Test

Run:

`POST /api/jobs/daily/run?force=false`

If today's Alpha Vantage quota is locked, you should receive something like:

```json
{
  "job_name": "daily_market",
  "status": "SKIPPED",
  "detail": "Alpha Vantage daily quota was already marked exhausted for today; no external market-data requests were made."
}
```

This is the desired behavior.

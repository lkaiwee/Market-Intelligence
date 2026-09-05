# Step 6 Patch — Automation, Alerts & Unified Dashboard

Apply this patch on top of the working Step 5 project.

## New capabilities

- Scheduled daily market refresh and alert generation
- Scheduled weekly earnings refresh
- Persistent alerts in PostgreSQL
- Job run history
- Unified `/api/dashboard` endpoint

## Default schedule

Timezone: `Asia/Singapore`

Daily market job:
- Tuesday through Saturday
- 07:15 Singapore time
- corresponds to Monday-Friday US market closes

Weekly earnings job:
- Sunday
- 18:00 Singapore time

## Default daily API budget

The daily job refreshes:
- SPY + 11 sector ETFs = 12 requests
- MSFT, NVDA, GOOGL, META, AVGO, MU, LRCX, JPM = 8 requests

Total: about 20 Alpha Vantage calls/day.

Fundamentals are not refreshed daily.

## New endpoints

- `GET /api/jobs/status`
- `POST /api/jobs/daily/run`
- `POST /api/jobs/weekly-earnings/run`
- `POST /api/jobs/alerts/run`
- `GET /api/jobs/history`
- `GET /api/alerts`
- `GET /api/dashboard`

## Install

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

The API version should be `0.6.0`.

## Safe first test (no Alpha Vantage calls)

1. `GET /api/jobs/status`
2. `POST /api/jobs/alerts/run`
3. `GET /api/alerts`
4. `GET /api/dashboard`

`POST /api/jobs/alerts/run` only analyzes data already stored in PostgreSQL.

## Manual daily job

`POST /api/jobs/daily/run`

This performs the full scheduled daily refresh and can consume about 20 API requests.

## Manual weekly job

`POST /api/jobs/weekly-earnings/run`

This normally uses one earnings-calendar request.

## Configuration

Defaults work without changing your existing `.env`.

Optional overrides:

```env
SCHEDULER_ENABLED=true
APP_TIMEZONE=Asia/Singapore

DAILY_JOB_DAY_OF_WEEK=tue-sat
DAILY_JOB_HOUR=7
DAILY_JOB_MINUTE=15

WEEKLY_JOB_DAY_OF_WEEK=sun
WEEKLY_JOB_HOUR=18
WEEKLY_JOB_MINUTE=0

DAILY_WATCHLIST=MSFT,NVDA,GOOGL,META,AVGO,MU,LRCX,JPM
DAILY_ALERT_MIN_SCORE=75
```

## Important

The scheduler runs only while FastAPI is running. If the computer is off or Uvicorn is stopped,
local jobs cannot run. A later deployment step can run the backend continuously as a service.

## Alert types

- `INVESTMENT_SETUP`
- `TECHNICAL_SETUP`
- `MARKET_REGIME`
- `ROTATION_LEADER`
- `HIGH_IMPACT_EARNINGS`

Alerts are deduplicated by date + ticker + alert type.

## Step 7

The unified dashboard API created here is designed to feed the actual browser GUI in Step 7.

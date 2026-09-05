# Stock Market Intelligence Dashboard

A local full-stack stock market intelligence system with:

- Daily stock alerts
- Daily money rotation
- Daily blue-chip investment screener
- Weekly earnings calendar
- Technical analysis
- Fundamental analysis
- Automated scheduled jobs
- Persistent PostgreSQL storage
- Next.js web GUI

---

# 1. Current System Version

Backend API version:

```text
0.7.2
```

Frontend:

```text
Next.js
http://localhost:3000
```

Backend:

```text
FastAPI
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Database:

```text
PostgreSQL
Docker
```

---

# 2. Final Architecture

```text
                         WEB BROWSER
                    http://localhost:3000
                              │
                              ▼
                         NEXT.JS GUI
                              │
                              ▼
                         FASTAPI API
                    http://127.0.0.1:8000
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
        PostgreSQL       Yahoo Finance     Alpha Vantage
             │                │                │
             │                │                └─ Optional / legacy
             │                │                   individual fundamentals
             │                │
             │                ├─ Daily stock prices
             │                ├─ Sector ETF prices
             │                ├─ Screener fundamentals
             │                └─ Upcoming earnings
             │
             ▼
       Analysis Engine
             │
     ┌───────┼────────┬───────────────┐
     │       │        │               │
     ▼       ▼        ▼               ▼
 Technical  Fundamental  Rotation   Earnings
 Analysis   Scoring      Scoring    Impact
     │       │        │               │
     └───────┴────────┴───────┬───────┘
                              ▼
                       Opportunity Score
                              │
                              ▼
                           Alerts
                              │
                              ▼
                          Dashboard
```

---

# 3. Project Folder Structure

Expected project structure:

```text
stock-dashboard-v1-step1/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── core/
│   │   ├── providers/
│   │   ├── services/
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── scheduler.py
│   │   └── main.py
│   │
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   └── .venv/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.local
│
├── docker-compose.yml
└── README.md
```

---

# 4. Required Software

Install:

```text
Docker Desktop
Python 3.9+
Node.js 20+
npm
```

Check:

```powershell
python --version
node --version
npm --version
docker --version
```

If Node.js is missing:

```powershell
winget install OpenJS.NodeJS.LTS
```

---

# 5. Start PostgreSQL

From the project root:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1"
```

Start PostgreSQL:

```powershell
docker compose up -d
```

Check:

```powershell
docker ps
```

Expected PostgreSQL container:

```text
stock_dashboard_postgres
```

---

# 6. Backend Setup

Go to backend:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\backend"
```

Allow PowerShell scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Activate virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start FastAPI:

```powershell
uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 7. Frontend Setup

Open a second PowerShell window.

Go to frontend:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\frontend"
```

Install packages:

```powershell
npm install
```

Start frontend:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

---

# 8. Environment File

Backend `.env` example:

```env
APP_NAME=Stock Market Intelligence API

DATABASE_URL=postgresql+psycopg://stockuser:stockpass@localhost:5432/stock_dashboard

ALPHA_VANTAGE_API_KEY=YOUR_API_KEY
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query

YAHOO_HISTORY_PERIOD=2y

SCHEDULER_ENABLED=true
APP_TIMEZONE=Asia/Singapore

DAILY_JOB_DAY_OF_WEEK=tue-sat
DAILY_JOB_HOUR=7
DAILY_JOB_MINUTE=15

SCREENER_JOB_DAY_OF_WEEK=tue-sat
SCREENER_JOB_HOUR=7
SCREENER_JOB_MINUTE=35
SCREENER_FUNDAMENTALS_MAX_AGE_DAYS=7

WEEKLY_JOB_DAY_OF_WEEK=sun
WEEKLY_JOB_HOUR=18
WEEKLY_JOB_MINUTE=0

DAILY_WATCHLIST=MSFT,NVDA,GOOGL,META,AVGO,MU,LRCX,JPM

DAILY_ALERT_MIN_SCORE=75
```

Frontend `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

---

# 9. Data Providers

## Daily Prices

Provider:

```text
Yahoo Finance
```

Used for:

```text
Stocks
SPY
Sector ETFs
Technical analysis
Money rotation
Daily alerts
```

## Screener Fundamentals

Provider:

```text
Yahoo Finance
```

Used for:

```text
Market cap
Revenue
Revenue growth
Earnings growth
Margins
ROE
Forward P/E
Trailing P/E
PEG
Price-to-book
Operating cash flow
Free cash flow
Debt
Cash
```

## Earnings

Provider:

```text
Yahoo Finance
```

Step 7.2 strategy:

```text
Ticker.get_calendar()
        ↓
If missing
        ↓
Ticker.get_earnings_dates()
```

## Alpha Vantage

Still retained for:

```text
Optional individual fundamental refresh endpoint
```

Alpha Vantage free quota:

```text
25 requests/day
```

Daily market scanning no longer depends on this quota.

---

# 10. Blue-Chip Universe

Current curated universe:

## Technology / Internet

```text
AAPL
MSFT
NVDA
GOOGL
GOOG
AMZN
META
```

## Semiconductors

```text
AVGO
AMD
MU
LRCX
AMAT
QCOM
TXN
INTC
TSM
```

## Software / Cloud / Cybersecurity

```text
ORCL
CRM
ADBE
NOW
PANW
CRWD
IBM
```

## Financials

```text
JPM
BAC
WFC
GS
MS
V
MA
BRK.B
```

## Consumer

```text
WMT
COST
HD
MCD
NKE
PG
KO
PEP
```

## Healthcare

```text
LLY
UNH
JNJ
ABBV
MRK
```

## Industrials

```text
CAT
GE
HON
RTX
BA
```

## Energy

```text
XOM
CVX
```

## Communication

```text
NFLX
DIS
```

---

# 11. Technical Analysis

The system calculates:

```text
SMA20
SMA50
SMA200

EMA9
EMA20

RSI14

MACD
MACD Signal
MACD Histogram

ATR14
ATR %

Average Volume 20
Volume Ratio

52-week High
52-week Pullback
```

Yahoo Finance provides approximately:

```text
2 years
```

of daily price history.

---

# 12. Technical Score

Maximum:

```text
100
```

Score components:

```text
Trend Alignment       25
Momentum              25
Pullback Setup        25
Volume / Volatility   15
Price Confirmation    10
```

---

# 13. Fundamental Score

The investment system evaluates:

```text
Revenue growth
Earnings growth
Profit margin
Operating margin
ROE
Free cash flow
Debt
Cash
Forward P/E
PEG
Price-to-book
```

---

# 14. Investment Opportunity Score

The investment screener combines:

```text
Technical Score
Fundamental Score
Valuation Score
Leadership Score
```

Example:

```text
NVDA

Technical      88
Fundamental    86
Valuation      60
Leadership    100

Opportunity    82
```

---

# 15. Money Rotation

Main ETFs:

```text
SPY   S&P 500 benchmark

XLK   Technology
XLC   Communication Services
XLY   Consumer Discretionary
XLF   Financials
XLI   Industrials
XLE   Energy
XLV   Health Care
XLU   Utilities
XLP   Consumer Staples
XLRE  Real Estate
XLB   Materials
```

Optional themes:

```text
SOXX   Semiconductors
IGV    Software
CIBR   Cybersecurity
IWM    Small Caps
QQQ    Nasdaq 100
```

---

# 16. Rotation Score

Calculated using:

```text
1-day return
5-day return
20-day return

Relative strength vs SPY

20-day momentum

Position vs 20-day average
```

Classification:

```text
75-100  STRONG_INFLOW

60-74   INFLOW

45-59   NEUTRAL

30-44   OUTFLOW

0-29    STRONG_OUTFLOW
```

---

# 17. Market Regime

Growth groups:

```text
XLK
XLC
XLY
```

Cyclical groups:

```text
XLF
XLI
XLB
```

Defensive groups:

```text
XLU
XLP
XLV
```

Possible output:

```text
RISK_ON
NEUTRAL
RISK_OFF
```

---

# 18. Alerts

Alert types:

```text
INVESTMENT_SETUP
TECHNICAL_SETUP
MARKET_REGIME
ROTATION_LEADER
HIGH_IMPACT_EARNINGS
```

Alerts are stored in PostgreSQL.

Deduplication:

```text
date
ticker
alert type
```

---

# 19. Earnings Impact Score

Classification:

```text
10  VERY_HIGH
9   HIGH
8   ELEVATED
7   NORMAL
```

Example:

```text
NVDA   10
MSFT   10
META   10
GOOGL  10
AVGO   10

MU      9
LRCX    9
ORCL    9
JPM     9
```

---

# 20. Earnings Related Tickers

Example:

```text
NVDA earnings

AMD
AVGO
MU
LRCX
AMAT
TSM
SMH
SOXX
```

Example:

```text
MSFT earnings

GOOGL
AMZN
ORCL
CRM
NVDA
QQQ
```

---

# 21. Scheduler

Timezone:

```text
Asia/Singapore
```

## Daily Market Job

Schedule:

```text
Tue-Sat
07:15 SGT
```

Corresponds approximately to:

```text
Monday-Friday US session closes
```

Purpose:

```text
Refresh SPY
Refresh sector ETFs
Refresh watchlist
Generate rotation
Generate alerts
```

## Daily Screener Job

Schedule:

```text
Tue-Sat
07:35 SGT
```

Purpose:

```text
Refresh blue-chip prices
Refresh missing/stale fundamentals
Recalculate investment ranking
```

## Weekly Earnings Job

Schedule:

```text
Sunday
18:00 SGT
```

Purpose:

```text
Refresh upcoming 3-month earnings
Generate high-impact earnings alerts
```

Important:

```text
Scheduler only runs while FastAPI is running.
```

---

# 22. Important API Endpoints

## Health

```text
GET /api/health
```

## Daily Stock Prices

```text
POST /api/stocks/{ticker}/refresh
```

Example:

```text
POST /api/stocks/MSFT/refresh
```

## Stored Prices

```text
GET /api/stocks/{ticker}/prices
```

Example:

```text
GET /api/stocks/MSFT/prices?limit=30
```

## Technical Analysis

```text
GET /api/stocks/{ticker}/analysis
```

Example:

```text
GET /api/stocks/MSFT/analysis
```

## Individual Fundamentals

```text
POST /api/stocks/{ticker}/fundamentals/refresh
```

Example:

```text
POST /api/stocks/MSFT/fundamentals/refresh
```

## Investment Analysis

```text
GET /api/stocks/{ticker}/investment-analysis
```

## Technical Screener

```text
GET /api/screener
```

## Full Investment Screener

```text
GET /api/investment-screener
```

## Blue-Chip Universe

```text
GET /api/screener/universe
```

## Refresh Full Screener

```text
POST /api/screener/refresh
```

Recommended:

```text
force_fundamentals=false
```

## Rotation Universe

```text
GET /api/rotation/universe
```

## Refresh Rotation

```text
POST /api/rotation/refresh
```

## Rotation Report

```text
GET /api/rotation
```

## Earnings Universe

```text
GET /api/earnings/universe
```

## Refresh Earnings

```text
POST /api/earnings/refresh
```

Recommended:

```text
horizon=3month
```

## Upcoming Earnings

```text
GET /api/earnings/upcoming
```

Example:

```text
GET /api/earnings/upcoming?days=90&min_impact=0
```

## Weekly Earnings

```text
GET /api/earnings/weekly
```

## Alerts

```text
GET /api/alerts
```

## Generate Alerts

```text
POST /api/jobs/alerts/run
```

## Daily Market Job

```text
POST /api/jobs/daily/run
```

Recommended:

```text
force=false
```

## Daily Screener Job

```text
POST /api/jobs/screener/run
```

Recommended:

```text
force_fundamentals=false
```

## Weekly Earnings Job

```text
POST /api/jobs/weekly-earnings/run
```

## Job Status

```text
GET /api/jobs/status
```

## Job History

```text
GET /api/jobs/history
```

## Unified Dashboard

```text
GET /api/dashboard
```

---

# 23. GUI Pages

## Dashboard

```text
http://localhost:3000/
```

Displays:

```text
Market regime
Risk-on score
Rotation leaders
Latest alerts
Investment opportunities
Technical watchlist
Upcoming earnings
Scheduler status
```

## Alerts

```text
http://localhost:3000/alerts
```

## Money Rotation

```text
http://localhost:3000/rotation
```

## Investment Screener

```text
http://localhost:3000/screener
```

## Earnings

```text
http://localhost:3000/earnings
```

## System

```text
http://localhost:3000/system
```

## Stock Detail

Example:

```text
http://localhost:3000/stocks/MSFT
```

---

# 24. First Full Data Population

After installing everything, run in this order.

## Step 1

Open:

```text
http://localhost:3000/screener
```

Click:

```text
Update Blue-Chip Screener
```

First run may take:

```text
1-3 minutes
```

because it fills missing fundamentals.

## Step 2

Open:

```text
http://localhost:3000/earnings
```

Click:

```text
Refresh Upcoming Earnings
```

## Step 3

Open:

```text
http://localhost:3000/rotation
```

Click:

```text
Refresh rotation data
```

## Step 4

Open:

```text
http://localhost:3000/alerts
```

Click:

```text
Generate from stored data
```

## Step 5

Open:

```text
http://localhost:3000/
```

Confirm dashboard sections populate.

---

# 25. Earnings Step 7.2 Fix

The current earnings logic uses:

```text
Known blue-chip ticker
        ↓
Yahoo Ticker.get_calendar()
        ↓
If no usable date
        ↓
Yahoo Ticker.get_earnings_dates()
        ↓
Select earliest upcoming date
        ↓
Save to PostgreSQL
```

This replaces the less reliable whole-market calendar parsing.

---

# 26. Earnings Troubleshooting

Run:

```text
POST /api/earnings/refresh?horizon=3month
```

Healthy response should look roughly like:

```json
{
  "horizon": "3month",
  "received_market_events": 53,
  "stored_blue_chip_events": 20,
  "unique_market_symbols": 53,
  "matched_blue_chip_symbols": [
    "AAPL",
    "MSFT",
    "NVDA"
  ],
  "diagnostic": "Checked 53/53 blue-chip tickers. Found 20 upcoming earnings events."
}
```

If:

```text
stored_blue_chip_events = 0
```

check:

```text
diagnostic
```

The old stored earnings calendar is preserved if Yahoo temporarily fails.

---

# 27. Screener Troubleshooting

If full investment table only contains IBM or a few stocks:

Run:

```text
POST /api/screener/refresh
```

with:

```text
force_fundamentals=false
```

The first refresh should populate fundamentals for the blue-chip universe.

Check:

```text
GET /api/investment-screener
```

---

# 28. Verify PostgreSQL Price Data

Connect:

```powershell
docker exec -it stock_dashboard_postgres psql -U stockuser -d stock_dashboard
```

Run:

```sql
SELECT
    ticker,
    MAX(trade_date) AS latest_date,
    COUNT(*) AS rows
FROM daily_prices
GROUP BY ticker
ORDER BY ticker;
```

Exit:

```sql
\q
```

---

# 29. Verify Fundamental Data

Inside PostgreSQL:

```sql
SELECT
    ticker,
    market_cap,
    revenue_ttm,
    forward_pe,
    free_cash_flow_ttm,
    updated_at
FROM stock_fundamentals
ORDER BY ticker;
```

---

# 30. Verify Earnings Data

Inside PostgreSQL:

```sql
SELECT
    ticker,
    company_name,
    report_date,
    eps_estimate,
    impact_score
FROM earnings_events
ORDER BY report_date, impact_score DESC;
```

---

# 31. Verify Alerts

Inside PostgreSQL:

```sql
SELECT
    alert_date,
    ticker,
    alert_type,
    severity,
    score,
    title
FROM alerts
ORDER BY alert_date DESC, score DESC;
```

---

# 32. Verify Scheduler History

Inside PostgreSQL:

```sql
SELECT
    id,
    job_name,
    status,
    started_at,
    finished_at,
    detail
FROM job_runs
ORDER BY id DESC
LIMIT 30;
```

---

# 33. Common Commands

## Start Database

```powershell
docker compose up -d
```

## Stop Database

```powershell
docker compose down
```

## Start Backend

```powershell
cd backend

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload
```

## Start Frontend

```powershell
cd frontend

npm run dev
```

---

# 34. API Key Security

Never expose the full Alpha Vantage key.

The backend sanitizes:

```text
API key
apikey=
rate-limit messages
```

Example:

```text
We have detected your API key as [REDACTED]
```

---

# 35. Update Alpha Vantage API Key

Open:

```powershell
notepad .env
```

Update:

```env
ALPHA_VANTAGE_API_KEY=YOUR_NEW_KEY
```

Restart Uvicorn afterward.

---

# 36. Check Which API Key FastAPI Loads

Masked check:

```powershell
python -c "from app.core.config import get_settings; k=get_settings().alpha_vantage_api_key; print(k[:4] + '...' + k[-4:] + '  length=' + str(len(k)))"
```

Do not paste the full key into screenshots or chat.

---

# 37. Same-Day Refresh Protection

The backend stores:

```text
market_refresh_state
```

Fields:

```text
ticker
last_attempt_date
status
newest_market_date
detail
updated_at
```

Normal daily refresh:

```text
force=false
```

Use:

```text
force=true
```

only when intentionally overriding same-day protection.

---

# 38. Current Main Data Flow

```text
Daily

Yahoo Finance
     ↓
Prices
     ↓
PostgreSQL
     ↓
Technicals
     ↓
Rotation
     ↓
Screener
     ↓
Alerts
     ↓
Dashboard
```

Weekly:

```text
Yahoo Finance
     ↓
Upcoming Earnings
     ↓
PostgreSQL
     ↓
Earnings Impact
     ↓
Alerts
     ↓
Dashboard
```

---

# 39. Recommended Daily Workflow

Normally no manual action is required if FastAPI remains running.

Automatic schedule:

```text
07:15 SGT
Daily market / rotation

07:35 SGT
Blue-chip screener

Sunday 18:00 SGT
Earnings calendar
```

Manual checks:

```text
Dashboard
Alerts
Screener
Rotation
Earnings
System
```

---

# 40. Important Limitation

The scheduler is inside FastAPI.

If:

```text
PowerShell closes
PC shuts down
FastAPI stops
```

then scheduled jobs do not run.

For continuous operation, later deploy using:

```text
Docker restart policy
Windows Service
Cloud VPS
AWS / Azure / DigitalOcean
```

---

# 41. Current Completed Features

```text
Market Data Collection                  ✅

Yahoo Daily Prices                      ✅

Technical Analysis                      ✅

Fundamental Analysis                    ✅

Blue-Chip Investment Screener           ✅

Money Rotation                          ✅

Risk-On / Risk-Off                      ✅

Daily Alerts                            ✅

Weekly Earnings                         ✅

Earnings Impact Mapping                 ✅

Scheduled Jobs                          ✅

Job History                             ✅

Quota Protection                        ✅

API-Key Redaction                       ✅

PostgreSQL Persistence                  ✅

Unified Dashboard API                   ✅

Next.js Web GUI                         ✅

Stock Detail Pages                      ✅
```

---

# 42. Recommended Future Enhancements

Possible future steps:

```text
Portfolio holdings page
Position sizing
PnL tracking
Watchlist editor
Email alerts
Telegram alerts
Discord alerts
Push notifications
Charting with candlesticks
Backtesting
AI-generated daily market summary
Sector heatmap
Economic calendar
Options data
News sentiment
Deployment to cloud
Authentication
Multi-user support
```

---

# 43. Quick Start Checklist

```text
[ ] Docker Desktop running

[ ] docker compose up -d

[ ] Backend virtual environment activated

[ ] uvicorn app.main:app --reload

[ ] Frontend npm run dev

[ ] http://localhost:3000 loads

[ ] Update Blue-Chip Screener completed

[ ] Refresh Upcoming Earnings completed

[ ] Rotation data populated

[ ] Alerts generated

[ ] /api/dashboard returns 200
```

---

# 44. Main URLs

Frontend:

```text
http://localhost:3000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Dashboard:

```text
http://localhost:3000/
```

Screener:

```text
http://localhost:3000/screener
```

Rotation:

```text
http://localhost:3000/rotation
```

Earnings:

```text
http://localhost:3000/earnings
```

Alerts:

```text
http://localhost:3000/alerts
```

System:

```text
http://localhost:3000/system
```

---

# 45. Final System Summary

You now have a local stock market intelligence platform that:

```text
Collects market data

Stores data in PostgreSQL

Calculates technical indicators

Scores blue-chip fundamentals

Ranks investment opportunities

Tracks sector money rotation

Detects market regime

Monitors upcoming earnings

Generates alerts

Runs automatic daily/weekly jobs

Displays everything in a browser GUI
```

The project is now at:

```text
Step 7.2
```

with the Yahoo ticker-based earnings reliability fix.

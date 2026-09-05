# Step 3 Patch — Fundamentals, Valuation & Investment Screener

Apply this patch on top of the working Step 2 project.

## New endpoints

- `POST /api/stocks/{ticker}/fundamentals/refresh`
- `GET /api/stocks/{ticker}/fundamentals`
- `GET /api/stocks/{ticker}/investment-analysis`
- `GET /api/investment-screener`

## What Step 3 adds

### Fundamental quality score /100

Uses:
- Free cash flow
- Free cash flow margin
- Revenue growth
- Earnings growth
- Operating margin
- Return on equity
- Debt/equity
- Net cash / net debt

### Valuation score /100

Uses:
- Forward P/E
- PEG
- Price/book
- Free-cash-flow yield

### Leadership score /100

This first version uses a transparent market-cap proxy:
- >= $500B: 100
- >= $200B: 90
- >= $100B: 80
- >= $50B: 70
- >= $10B: 55
- below $10B: 35

This is deliberately called a proxy. True industry leadership will later use peer ranking,
market share, and relative strength.

### Opportunity score /100

- Technical: 40%
- Fundamental quality: 35%
- Valuation: 15%
- Leadership: 10%

The score is a ranking tool, not an automatic buy recommendation.

## Installation

Extract this ZIP into the inner existing project folder and replace matching files.

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

## First test with IBM

You already have IBM price history.

Run:

`POST /api/stocks/IBM/fundamentals/refresh`

Then:

`GET /api/stocks/IBM/fundamentals`

Then:

`GET /api/stocks/IBM/investment-analysis`

## Build a multi-stock investment screener

For each stock:

1. Refresh price data:
   `POST /api/stocks/MSFT/refresh`

2. Refresh fundamentals:
   `POST /api/stocks/MSFT/fundamentals/refresh`

Suggested initial universe:

- MSFT
- NVDA
- GOOGL
- META
- AVGO
- MU
- LRCX
- JPM
- IBM

Then run:

`GET /api/investment-screener`

## API usage note

Fundamental data is stored in PostgreSQL. Do not repeatedly refresh it during the same day.
Fundamentals normally change around earnings/financial-report updates, so later we will schedule
fundamental refreshes much less frequently than price refreshes.

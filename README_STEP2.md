# Step 2 Patch — Technical Analysis + Screener

Apply this patch on top of your existing Step 1 project.

Extract the ZIP into the inner `stock-dashboard-v1-step1` folder and allow Windows to replace existing files.

## What Step 2 adds

- `GET /api/stocks/{ticker}/analysis`
- `GET /api/screener`

Indicators:
- SMA 20 / 50 / 200
- EMA 9 / 20
- RSI 14
- MACD + signal + histogram
- ATR 14
- 20-day average volume
- volume ratio
- available-period high and pullback
- true 52-week high/pullback when 252 bars exist
- trend
- technical score /100
- technical signal

## Install after patching

```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Refresh Swagger:

`http://127.0.0.1:8000/docs`

Then test:

`GET /api/stocks/IBM/analysis`

After refreshing more stocks, test:

`GET /api/screener`

## Important history limitation

The current Alpha Vantage compact response gives about 100 daily bars. That is enough for RSI,
MACD, SMA20, SMA50, EMA and ATR. SMA200 needs 200 bars and a true 52-week high uses 252 bars.
Those fields are returned as null until enough data exists rather than being guessed.

# Stock Dashboard — V1 Step 1

This is the first backend milestone for a personal market-intelligence dashboard.

## Included

- FastAPI REST API
- PostgreSQL persistence
- Alpha Vantage market-data provider
- Provider abstraction for future Polygon/FMP/etc.
- Stock and daily OHLCV models
- Endpoint to fetch and save daily price history
- Endpoint to read stored price history
- FastAPI interactive documentation

## 1. Requirements

Install:

- Python 3.11+
- Docker Desktop

## 2. Start PostgreSQL

From the project root:

```bash
docker compose up -d
```

## 3. Create the Python environment

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Configure environment variables

Copy `.env.example` to `.env` and put your Alpha Vantage API key in it.

Windows:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

## 5. Run the backend

From `backend/`:

```bash
uvicorn app.main:app --reload
```

Open:

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

## 6. Test market-data collection

In Swagger, run:

`POST /api/stocks/{ticker}/refresh`

Example:

`POST /api/stocks/IBM/refresh`

Then read stored candles:

`GET /api/stocks/IBM/prices?limit=30`

For your intended universe you will eventually refresh tickers such as:

- MSFT
- NVDA
- GOOGL
- META
- AVGO
- MU
- LRCX
- JPM

## Next milestone

V1 Step 2 will add:

- RSI
- SMA/EMA 20, 50 and 200
- 52-week-high pullback
- ATR
- volume comparison
- relative strength
- technical score
- opportunity score
- daily screener output

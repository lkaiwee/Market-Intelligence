# Step 7 — Web GUI

This patch adds the actual browser frontend.

## Architecture

```text
Browser
  |
  v
Next.js frontend :3000
  |
  v
FastAPI backend :8000
  |
  v
PostgreSQL
```

## Pages

- Dashboard
- Alerts
- Money Rotation
- Investment Screener
- Earnings
- System

## Installation

Extract this ZIP into the existing inner project root and replace matching backend files.

Your project root should then contain:

```text
backend/
frontend/
docker-compose.yml
```

### Backend

```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend:
`http://127.0.0.1:8000`

Swagger:
`http://127.0.0.1:8000/docs`

### Frontend

Open a SECOND PowerShell window:

```powershell
cd "C:\Users\admin\Documents\stock-dashboard-v1-step1\stock-dashboard-v1-step1\frontend"
npm install
npm run dev
```

Frontend:
`http://localhost:3000`

## Requirements

- Node.js 20+ recommended
- npm

Check:

```powershell
node --version
npm --version
```

If Node is missing:

```powershell
winget install OpenJS.NodeJS.LTS
```

Then close and reopen PowerShell.

## Environment

The frontend includes:

`.env.local.example`

Default API:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Create `.env.local` if you want to override it.

## First launch

1. Keep Docker/PostgreSQL running.
2. Keep FastAPI running on port 8000.
3. Start Next.js on port 3000.
4. Open `http://localhost:3000`.

The GUI reads existing PostgreSQL data through FastAPI.
It does not automatically consume external API quota just by loading pages.

## GUI actions

The System page includes buttons for:

- Generate alerts from stored data
- Daily market refresh
- Weekly earnings refresh

Daily refresh uses `force=false` from the GUI.

## Notes

The current GUI is a local single-user dashboard.
Authentication, remote deployment, notifications and portfolio tracking can be added later.

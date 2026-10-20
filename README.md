# NeuroOps AI — Customer Complaint Intelligence Platform

Phase 2 stores imported customer complaints in PostgreSQL and displays database-backed dashboard data. LLM, RAG, AI Research, AI Agent, and report generation are not implemented.

## Project structure

- `frontend/` — React dashboard, API client, loading/empty/error states, and frontend tests.
- `backend/app/` — FastAPI routes, Complaint model, CSV validation, and PostgreSQL access.
- `backend/migrations/` — Alembic database migration history.
- `backend/tests/` — health, CSV validation, import, storage, and analytics tests.
- `docker-compose.yml` — frontend, API, and PostgreSQL services.

## Local setup

Requirements: Node.js 20+, Python 3.10+, and PostgreSQL 16+ or Docker Desktop.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Set DATABASE_URL and IMPORT_API_KEY in .env before the next two commands.
alembic upgrade head
uvicorn app.main:app
```

The API runs at `http://127.0.0.1:8000`, documentation is at `/docs`, and health is at `/api/health`. Add `--reload` in a normal local terminal if you want automatic restarts.

### Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite normally runs at `http://localhost:5173`. The dashboard fetches current complaints and analytics from the FastAPI API through the Vite proxy.

### Docker Compose

Set a local `IMPORT_API_KEY` with at least 32 characters, then run:

```powershell
$env:IMPORT_API_KEY = "replace-this-with-a-local-secret-of-at-least-32-characters"
docker compose up --build
```

Compose waits for PostgreSQL, applies `alembic upgrade head`, then starts FastAPI. Open `http://localhost:8080`. Stop services with `docker compose down`; PostgreSQL data persists in its named volume.

## CSV import API

`POST /api/complaints/import` accepts a raw UTF-8 CSV request body. It requires `Content-Type: text/csv` and an `X-Import-Key` header that matches `IMPORT_API_KEY`. The import has a 2 MiB file limit and a 5,000 data-row limit. The API never saves the uploaded file to disk.

The required unique columns are `complaint_id`, `title`, `category`, `status`, `priority`, `channel`, and `received_date`. Column order does not matter.

- `complaint_id`: letters, numbers, underscores, and hyphens
- `status`: `open`, `in_progress`, or `resolved`
- `priority`: `low`, `medium`, or `high`
- `received_date`: `YYYY-MM-DD`

An invalid row is skipped and returned with its CSV row number and field errors. A duplicate `complaint_id` is skipped, leaving its original database record unchanged. Valid rows still import when other rows fail validation.

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/complaints/import" `
  -Headers @{ "X-Import-Key" = $env:IMPORT_API_KEY; "Content-Type" = "text/csv" } `
  -InFile .\complaints.csv
```

The dashboard calls `GET /api/complaints`, `/api/analytics/categories`, `/api/analytics/status`, and `/api/analytics/trends`.

## Important implementation choices

- The Complaint model has a database primary key on `complaint_id` plus constraints for status and priority. The migration makes those protections reproducible across environments.
- CSV parsing is separate from HTTP and database code. It decodes UTF-8, validates the exact header, then validates each record before attempting storage.
- PostgreSQL handles duplicates with `ON CONFLICT DO NOTHING`, which also protects concurrent imports from overwriting a record.
- Search values are escaped before the parameterized `ILIKE` query so `%` and `_` remain literal text.
- The dashboard uses database values only. It shows loading, empty, and API-error states instead of presenting sample figures as real data.
- The API health endpoint confirms the process is available. The dashboard data request is the database readiness check.

## Checks

```powershell
cd backend
pytest

cd ..\frontend
npm test
npm run build
```

## Environment variables

Copy `backend/.env.example` only when no `.env` file exists. Existing environment variables take priority over `.env` values. Keep `DATABASE_URL` and `IMPORT_API_KEY` private and out of version control.

## Next phase

Build Complaint Analysis with evidence links, human review states, and measured category quality before adding any LLM feature.

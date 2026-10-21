# NeuroOps AI — Customer Complaint Intelligence Platform

Phase 3 adds operator-triggered AI complaint classification and sentiment, with rule-based suggested priority. Original complaint records and analytics stay unchanged. RAG, AI Research, AI Agent, and report generation are not implemented.

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

## Phase 3: complaint intelligence

### Configure and migrate

Add `OPENAI_API_KEY` and `LLM_MODEL` to your existing **backend** `.env` (do not replace it).
Select an OpenAI model available to your account that supports strict JSON schema.
Real requests require a funded API account and may incur charges. Tests mock the provider
and require no real key or paid requests. No automatic analysis runs on import or page load.
The integration follows [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).

From `backend`, with the virtual environment activated:

```powershell
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app
```

Migration `0002` adds `complaint_analyses`, linked by complaint ID, without altering
or deleting existing complaints. Every attempt is appended, including failures.
The dashboard displays the latest attempt; previous attempts remain in the database.
Back up your database before migrations. Downgrading `0002` deletes analysis history only.
For Compose, set `OPENAI_API_KEY`, `LLM_MODEL`, and optionally `AI_RULES_JSON` in the
shell or root `.env`; Compose does not automatically read `backend/.env`.

### APIs

Classification uses the existing `X-Import-Key` operator credential. Keep this key
and the provider key on the backend/operator machine; never add them to `VITE_` variables.
Single requests return the stored analysis. Batches accept 1–5 IDs, deduplicate them,
and return independent results, including `not_found` and failure statuses.

```powershell
# Set IMPORT_API_KEY in this operator shell to match your backend configuration.
$headers = @{ "X-Import-Key" = $env:IMPORT_API_KEY }
Invoke-RestMethod -Method Post -Headers $headers `
  -Uri "http://127.0.0.1:8000/api/complaints/CMP-1/classify"

Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" `
  -Uri "http://127.0.0.1:8000/api/complaints/classify-batch" `
  -Body '{"complaint_ids":["CMP-1","CMP-2"]}'
```

Reload the dashboard after classification to see category, sentiment, suggested
priority, and completed/failed/not-analyzed status next to original fields.
Classification is operator API-only in this phase; browser users need no secret.
Batch HTTP 200 means the batch was processed, **not** that every item succeeded.
Single failures use 503 for missing configuration/provider authentication,
429 for rate limits, 504 for timeouts, 502 for provider/invalid output errors,
422 for insufficient text, and 404 for missing complaints.
Provider response bodies, credentials, and prompts are never exposed in errors.
There are no automatic retries (to avoid surprise charges). An explicit retry
creates a new attempt and may incur another charge.

### Rules, privacy, and limits

- `intelligence.py` owns the provider call and Pydantic output validation. Only an
  allowed category and Positive/Neutral/Negative sentiment are accepted; extra
  fields such as model-provided confidence are rejected.
- `analysis_routes.py` orchestrates validated single/batch requests and stores
  results. `ComplaintAnalysis` records provider/model versions, prompt/privacy
  versions, the rules snapshot, timestamp, status, and safe error code.
- Optional `AI_RULES_JSON` configures categories and priority rules; see `.env.example`.
  Defaults include Delivery Delay, Refund Issue, Damaged Product, Wrong Item,
  Product Quality, Customer Support, and Other.
- Priority precedence: a configured safety keyword yields **high**; otherwise
  Negative sentiment yields `negative_priority` (default **medium**); otherwise
  `default_priority` (default **low**). Safety keywords must be members of the
  fixed privacy vocabulary. Negation is deliberately not interpreted: “not unsafe”
  still triggers review. This is a transparent triage heuristic, not verified urgency.
- No confidence probabilities are computed or displayed. All results are marked
  **AI suggestion · Unverified**; human verification is not implemented.
- Only generic words from a fixed complaint vocabulary, in original order, are
  transmitted. Contact/URL spans are removed first. IDs, channel, dates, original
  labels, numbers, and arbitrary free text are not sent. The provider receives no
  tools. `store: false` is sent; this is not a guarantee of zero provider retention.
- This conservative filter loses names, context, unsupported words, and non-English
  text. It is unsuitable for precise multilingual analysis. Generic words can still
  coincide with names; this is data minimization, not a certified anonymizer.
- Existing records have only a short title; results cannot establish root causes.
  Accuracy has not been measured against human-labeled data.
- Calls run sequentially with a 20-second HTTP timeout per provider call and at most
  five complaints per batch. No job queue, global spend quota, user login, or
  distributed rate limiter exists yet. Keep deployment local/trusted; public
  deployment requires access control for the existing read APIs and spend controls.
- Existing category charts and metrics summarize imported fields, not AI suggestions.

### Optional PostgreSQL integration check

```powershell
cd backend
$env:TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/TEST_DATABASE"
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py -q
Remove-Item Env:TEST_POSTGRES_URL
```

Use a disposable test database. Tests create a uniquely named schema, run migrations,
exercise mocked classification/storage/APIs, and drop only their own schema.
Without this variable, tests run against in-memory SQLite. No paid calls are used.

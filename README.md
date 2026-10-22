# NeuroOps AI — Enterprise Complaint Intelligence & AI Operations Platform

[![Verification](https://img.shields.io/badge/Phase_8_Audit-PASS-success)](#phase-8-final-validation--portfolio-readiness)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-cyan)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-blue)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://www.postgresql.org/)

**Phase 8 validation complete:** Full-stack regression testing, live HTTP smoke testing on PostgreSQL, production TypeScript/Vite bundling, role-based access control, and portfolio documentation are fully audited and passing. See [PHASE8_FINAL_AUDIT.md](file:///C:/Users/mayank%20singh/Desktop/neuroops-ai/PHASE8_FINAL_AUDIT.md) for actual test counts and exact command executions, and [PORTFOLIO_GUIDE.md](file:///C:/Users/mayank%20singh/Desktop/neuroops-ai/PORTFOLIO_GUIDE.md) for system architecture, interview questions, and a 5-minute demonstration script.

Docker container execution, TLS termination, backup restoration drills, and live paid-provider validation remain unverified and are explicit blockers for public deployment.

---

## Implemented Features Overview

1. **Complaint Ingestion & Relational Storage:**
   - UTF-8 streaming CSV validation (2 MiB / 5,000 rows max).
   - Idempotent deduplication (`ON CONFLICT DO NOTHING`) and row-level validation reporting.
   - Real-time operational dashboard with status, category distributions, and daily volume trends.

2. **Data-Minimized AI Complaint Intelligence:**
   - Deterministic domain text minimization (`minimize_text()`) to strip customer PII before model calls.
   - Strict OpenAI Structured Outputs via Pydantic schemas (`temperature=0`).
   - Append-only audit history of triage attempts with rule snapshots and error codes.

3. **Grounded Company Knowledge Base (RAG):**
   - Bounded PDF/TXT ingestion (5 MiB / 20 pages max).
   - Multi-tenant workspace key isolation.
   - Vector chunk search with cosine similarity.
   - Quote-level citation grounding: claims are rejected if citations do not match chunk passages verbatim.

4. **Bounded Autonomous Investigation Agent:**
   - Multi-step ReAct planning loop with typed tools (`get_complaint`, `search_knowledge`, `summarize_findings`).
   - Hard execution guardrails: step count caps (`max_steps=6`), strict deadlines (`timeout=60s`), and cooperative cancellation.
   - Background sweeper cleans up stale or crashed runs without replaying paid calls.

5. **LLM Evaluation & Human-in-the-Loop Review:**
   - Deterministic rubrics (exact match, citation precision, length limits) for zero-cost baseline benchmarking.
   - Blinded pairwise LLM judging with position-swap debiasing.
   - Auditable reviewer role with append-only feedback (`approve`, `reject`, `correct`).

6. **Production Security, RBAC & Telemetry:**
   - Per-user SHA-256 hashed Bearer tokens with discrete RBAC (`viewer`, `operator`, `reviewer`, `admin`).
   - Fail-closed configuration: missing auth config rejects startup in production mode.
   - Correlated request tracing via `X-Request-ID` and privacy-preserving structured request logging.
   - Sanitized 422/500 responses omitting customer inputs, SQL strings, and stack traces.

## Project structure

- `frontend/` — React dashboard, API client, loading/empty/error states, and frontend tests.
- `backend/app/` — FastAPI routes, Complaint model, CSV validation, and PostgreSQL access.
- `backend/migrations/` — Alembic database migration history.
- `backend/tests/` — health, CSV validation, import, storage, and analytics tests.
- `backend/app/knowledge_*.py` — workspace authorization, document processing, provider adapters, retrieval, and question answering.
- `backend/app/agent_*.py` — typed planning/tools, bounded execution, run history, workspace-scoped APIs, and provider deadlines.
- `frontend/src/components/AgentWorkspace.tsx` — investigation form, history, cancellation, timeline, and evidence report.
- `backend/app/evaluation_*.py` — evaluation contracts, metric rubric, judge adapter, storage, reviewer authorization, reporting APIs, and body limits.
- `frontend/src/components/Evaluation*.tsx` — dataset creation, evaluation dashboard, side-by-side responses, and human reviews.
- `backend/examples/evaluation_cases.csv` — explicitly synthetic, optional sample cases; never imported automatically.
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

Compose now requires the root `.env` configuration and production authentication.
See **Phase 7: production operations** below for the complete setup. In particular,
set unique database/workspace/import secrets and hashed user access tokens before running:

```powershell
docker compose up --build
```

Compose waits for PostgreSQL, runs the separate migration service, then starts FastAPI
and the frontend after readiness succeeds. Open `http://localhost:8080`. Only the
frontend port is published on loopback. Stop services with `docker compose down`;
PostgreSQL data persists in its named volume. Do not add `-v` unless deliberately deleting data.

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

## Phase 4: RAG company Knowledge Base

### Setup and access

Install backend dependencies, configure the variables below in the existing backend
`.env`, and apply the new migration. Existing secrets are not replaced.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app
```

In a second terminal, run `npm run dev` from `frontend`. Open **Knowledge Base** in
the sidebar. Connect with a workspace access key supplied by the administrator,
upload a PDF/TXT document, then ask a question. Uploads process synchronously; the
page shows progress and polls persisted processing status while needed. Re-upload
the same failed file to retry. A crashed processing attempt can be reclaimed by
re-uploading after its 15-minute lease expires. No partial chunks become searchable.

Generate a random capability key for each workspace, for example with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`, then configure:

```dotenv
# Replace this example value with a newly generated random key.
KB_WORKSPACE_KEYS_JSON={"company":"replace_with_a_random_workspace_key_of_32_plus_characters"}
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=YOUR_AVAILABLE_EMBEDDING_MODEL
OPENAI_API_KEY=YOUR_BACKEND_API_KEY
RAG_LLM_MODEL=YOUR_AVAILABLE_STRUCTURED_OUTPUT_MODEL
# Optional: authorize exactly one workspace to view the existing complaint aggregates.
KB_ANALYTICS_WORKSPACE=company
```

`RAG_LLM_MODEL` falls back to `LLM_MODEL` if omitted. Models must be available to
your provider account. OpenAI embedding and answer calls can incur charges; no
live provider calls run during automated tests. See the official documentation for
[embeddings](https://developers.openai.com/api/docs/guides/embeddings) and
[structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).

Alternative embedding provider: set `EMBEDDING_PROVIDER=ollama`, install and pull a
semantic embedding model in a separately managed Ollama service, set
`EMBEDDING_MODEL` to that model, and use
`OLLAMA_EMBED_URL=http://127.0.0.1:11434/api/embed`. The backend implements the
[Ollama embedding API](https://docs.ollama.com/api/embed) with truncation disabled.
This avoids a paid embedding call; answering still uses OpenAI. Ollama setup and
model downloads are not performed automatically. Only loopback/Docker host HTTP
endpoints or administrator-configured HTTPS endpoints are accepted; redirects are disabled.

For Docker Compose, put these values in the root `.env` or export them in your
shell. The backend's local `.env` is not copied into the image. Compose defaults
Ollama's URL to `http://host.docker.internal:11434/api/embed` for Docker Desktop;
configure networking yourself on other hosts. Nginx allows uploads up to the
backend's hard maximum of 10 MiB and has a 300-second API response timeout.

Workspace IDs are derived from the server's key mapping, never accepted from a
question or upload. Every document list, status lookup, and retrieval query is
scoped by that workspace. A key grants read/upload/ask access to its workspace;
this is a small-installation capability scheme, not individual user login or RBAC.
Rotate keys in server configuration to revoke them. Use HTTPS outside localhost.
The browser stores the workspace key only in component memory, clears results on
disconnect, and never receives provider credentials. No localStorage or query-string
credentials are used. Existing complaint read APIs remain installation-wide.

### Storage and repeatable ingestion

Migration `0003` creates `knowledge_documents` and `knowledge_chunks`; no complaint
rows are changed. Metadata includes workspace, sanitized filename, SHA-256 content
checksum, processing status, safe error code, timestamps, indexing configuration,
and embedding dimension. Each chunk has a unique document/chunk index, source page
for PDF (1-based), extracted passage, and normalized embedding vector.

Repeated identical bytes with the same embedding/chunk configuration return the
existing document. Failed attempts can retry without creating duplicate chunks.
Database uniqueness constraints and PostgreSQL advisory locks protect simultaneous
uploads and capacity checks. Chunk insertion and ready status commit together.
Changing file content, provider/model/endpoint, chunk size, or overlap creates a new
document version. Raw files are not saved; extracted text and vectors are stored.
There is no delete or document editing API in this phase.

PDF extraction uses `pypdf` with strict parsing, decoding limits, at most 100 pages,
and 200,000 extracted characters. Scanned/image-only, encrypted, malformed, empty,
or unsupported PDFs fail clearly. TXT must be UTF-8; binary/control-character
content is rejected. PDF page boundaries are preserved when chunking. Chunking uses
characters with overlap, not tokens, so it can split words or sentences.

### Vector-search choice

The inspected local PostgreSQL 16 installation does not include pgvector. This
phase stores vectors as JSON in PostgreSQL and performs **exact cosine similarity**
over a bounded workspace corpus in Python. This is semantic search over actual
provider embeddings, not keyword matching. It needs no extension or separate
database and works in the existing PostgreSQL container. It scans all eligible
vectors and is intentionally limited to 1,000 chunks by default (hard maximum 2,000).

For larger corpora, migrate the embedding column to pgvector `vector(N)`, install
the extension on the PostgreSQL server and run `CREATE EXTENSION vector` with an
authorized administrator, then add a cosine index. That requires an extension-enabled
database image; ordinary `postgres:16-alpine` does not install it. No extension or
database image is silently changed here.

Queries compare only vectors with the current embedding profile. Keep model
configuration stable, preferably pinned to a version. If it changes, re-upload
documents and use `document_ids` to select the new versions. Old versions remain
stored and are excluded from the current profile's search; if none are compatible,
the API returns an explicit configuration-change error. Matching dimensions alone
does not make different embedding models compatible.

### Limits

| Variable | Default | Allowed range / behavior |
|---|---:|---|
| `KB_UPLOAD_BYTES` | 5242880 | 1 KiB–10 MiB; streamed check plus declared length check |
| `KB_CHUNK_SIZE` | 1000 | 100–2000 characters |
| `KB_CHUNK_OVERLAP` | 150 | 0 through chunk size minus one |
| `KB_WORKSPACE_CHUNKS` | 1000 | 1–2000 total stored chunks per workspace |
| `KB_WORKSPACE_DOCUMENTS` | 100 | 1–100 document versions including failed attempts |
| `KB_MIN_SIMILARITY` | 0.3 | -1 through 1; retrieval cutoff, not confidence |
| `KB_REQUESTS_PER_MINUTE` | 10 | 1–60 upload/question requests per workspace, per API process |

There are at most 200 chunks per document, 16 texts per embedding request, five
retrieved chunks per answer, 10 optional document IDs, 1,000 question characters,
and 8 KiB per question JSON body. Each provider call has a 25-second HTTP timeout;
there are no automatic retries. Duplicate uploads also count toward the request
limit. Failed uploads retain status metadata and count toward the document limit.

### API examples

Use a workspace key matching server configuration in your operator terminal:

```powershell
$headers = @{ "X-Workspace-Key" = $env:KB_WORKSPACE_KEY }
Invoke-RestMethod -Headers $headers -Uri "http://127.0.0.1:8000/api/knowledge/documents"

# Raw file body, not multipart/form-data.
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/pdf" `
  -Uri "http://127.0.0.1:8000/api/knowledge/documents?filename=returns.pdf" `
  -InFile .\returns.pdf

Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" `
  -Uri "http://127.0.0.1:8000/api/knowledge/ask" `
  -Body '{"question":"What does the returns policy say about damaged items?","top_k":4,"include_analytics":false}'
```

Use `text/plain` and a `.txt` filename for TXT. `GET /api/knowledge/documents/{id}`
returns processing status; another workspace receives 404. The document list
supports `limit` (1–100) and `offset`. Questions optionally accept `document_ids`;
IDs from another workspace never widen retrieval scope.

An answered response contains AI explanation `claims`, each linked by `citation_id`
to a server-built source containing the document name, page (or null for TXT), chunk
index, exact quoted passage, and semantic similarity score. Citations are accepted
only if their chunk was retrieved and their quote is a contiguous substring of that
chunk. The model cannot supply a filename or page number. The frontend renders
quotations separately from explanations as escaped text, never provider-generated HTML.

With no qualifying chunks, or when the model says the context cannot answer the
question, the API returns `status=insufficient_evidence` and the explicit message:
“The available documents do not provide enough information to answer this question.”
It returns no unsupported answer or citation. Invalid citations return a safe 502
error. Missing credentials/configuration return 503; provider failures 502; rate
limits 429; provider timeout 504; invalid files/questions 422; unsupported types 415;
oversized bodies 413; capacity/profile conflicts 409. No raw provider error is exposed.

### Complaint analytics alongside evidence

`include_analytics=true` is permitted only for `KB_ANALYTICS_WORKSPACE`, which
explicitly assigns the installation's existing complaint aggregates to one workspace.
Other workspaces receive 403. This returns fixed SQL aggregate results: total
complaints, status counts, and the top 20 imported categories with counts.
These appear in `calculated_analytics`, clearly separated from document-derived
claims. No SQL generation, arbitrary code, complaint titles, or personal complaint
data are sent to the LLM. The language model does not paraphrase or invent these
numbers; the UI displays database values directly. Analytics can be returned even
when document evidence is insufficient.

### Security and remaining limitations

- Uploading company documents deliberately sends extracted text to the configured
  embedding provider; question text and retrieved passages go to the answer LLM.
  This differs from Phase 3's restricted complaint vocabulary. Upload only material
  you may share with those providers and remove unnecessary sensitive information.
  OpenAI answer calls use `store: false`, which is not a zero-retention guarantee.
- Document passages and questions enter a data-only JSON user message. System
  instructions prohibit following document instructions, making up facts, using
  outside knowledge, or executing tools. The answer schema and citation checks
  constrain output. Prompt injection cannot expand database scope or execute code.
  These controls cannot guarantee that every generated paraphrase follows its quote;
  users must review evidence. There is no claim of perfect injection resistance.
- Retrieval thresholds and model quality have not been evaluated against a labeled
  company dataset. Cosine similarity is not calibrated confidence. Relevance alone
  does not prove that a passage answers a question, so the LLM must also judge
  sufficiency. No live paid-provider validation was performed during development.
- Ingestion is synchronous with bounded PDF decoding and text/page limits. It is
  not a fully sandboxed parsing service or durable background job queue. A future
  deployment handling hostile files should add isolated workers and hard CPU/memory
  budgets. Very slow requests can outlast the browser/proxy timeout; refresh status
  before retrying. Interrupted work is recoverable through the processing lease.
- Request limiting is per process and in memory; multiple API workers require a
  shared limiter and spend controls. Static workspace keys provide no user-level
  audit trail. The existing global complaint APIs still need broader deployment
  access control. The Knowledge Base is suitable for trusted local evaluation.
- The PostgreSQL advisory lock provides concurrent capacity protection in production.
  SQLite is used only for fast automated tests. Phase 5 adds the bounded agent below.

### Phase 4 checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
# Optional: disposable PostgreSQL database; schemas are created and cleaned per test.
$env:TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/TEST_DATABASE"
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py tests/test_knowledge.py -q
Remove-Item Env:TEST_POSTGRES_URL
cd ..\frontend
npm test
npm run build
```

Tests mock embedding and answering providers. Coverage includes TXT/PDF extraction,
overlapping chunks, invalid uploads, streaming limits, duplicate and failed retries,
actual migrations over populated Phase 2 data, semantic ranking, workspace isolation,
quoted citations, fabricated citation rejection, insufficient evidence, provider
failures, and frontend connection/upload/question/error states.

## Phase 5: controlled complaint investigations

Open **AI Agent** in the sidebar to use **Agent Workspace**. Connect with an existing
Knowledge Base workspace key, enter a general investigation task, and approve sharing
the task and relevant passages with the configured providers. The key is held only in
browser memory and worker memory. Run history can be reopened with the same workspace
key after a refresh. History shows the latest 20 runs; the API supports pagination.

### Setup and configuration

No new dependency or paid service is required. Planning uses the existing OpenAI
Chat Completions integration with strict structured output. Live planning, embeddings,
and document explanations can incur usage charges on the configured provider accounts.
Automated tests mock these calls and require no real key or paid request.

Add these settings to your existing **backend/.env** without replacing its secrets:

```dotenv
# Required existing settings: DATABASE_URL, KB_WORKSPACE_KEYS_JSON, OPENAI_API_KEY,
# LLM_MODEL; EMBEDDING_MODEL and RAG_LLM_MODEL for document investigations.
# Only the designated workspace may read installation-wide complaint aggregates.
KB_ANALYTICS_WORKSPACE=operations
# Optional: empty means use LLM_MODEL.
AGENT_LLM_MODEL=
AGENT_MAX_STEPS=4
AGENT_TIMEOUT_SECONDS=90
AGENT_RETRIES=1
```

The workspace name must match an entry in `KB_WORKSPACE_KEYS_JSON`. Keep provider
credentials out of frontend variables. Use a model that supports strict JSON schema;
see [OpenAI structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
Compose passes these settings from its shell/root environment; backend/.env is for
local Python execution and is not automatically Compose's substitution file.

Apply migration `0004` and start the existing apps:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app
# Separate terminal, from project root:
cd frontend
npm run dev
```

Migration `0004` creates `agent_runs` and `agent_steps`. It does not alter or delete
complaints, classification history, documents, or chunks. The run records hold task,
workspace, status, deadline, errors, and final report. Steps hold validated arguments,
status, attempt count, and actual output. Stored evidence snapshots allow later review;
treat these tables as sensitive company data and apply your normal retention policy.

### Architecture in plain language

1. **Validate and admit:** the API authenticates the workspace, limits the request body
   to 8 KiB and task to 1,000 characters, requires provider consent, and persists a run.
2. **Plan:** the LLM returns booleans selecting analytics and/or knowledge, a reason,
   trend days, and retrieval count. Pydantic rejects malformed output. Python builds
   the actual tool calls in a fixed order. The LLM cannot supply executable tools.
3. **Execute:** a FastAPI background worker runs each tool, commits its status, and
   checks the original workspace capability before and after every attempt. Each
   database transaction uses its own session; remote calls do not hold run-row locks.
4. **Report:** numeric facts are copied directly from existing aggregate services.
   Document explanations reuse Phase 4's answer service, including source-ID and
   exact-quotation checks. The frontend separates facts, AI interpretations, and quotes.
5. **Review:** the user sees every step and any stable error code. A completed workflow
   may produce an `insufficient_evidence` report; completion never means verified truth.

| Registered tool | Validated arguments | Output and authorization |
| --- | --- | --- |
| `complaint_analytics` | `days`: integer 1–366 | Existing total/status/category counts and recent daily trends. Only `KB_ANALYTICS_WORKSPACE`. Counts/categories cover all imported complaints; only trends use the day window. |
| `knowledge_retrieval` | `question`: 3–1,000 characters; `top_k`: integer 1–5 | Existing semantic retrieval scoped to the authenticated workspace; actual passages and document/page/chunk metadata. |
| `report_generation` | Empty object | Copies preceding tool results and invokes the existing grounded explanation service when documents were requested. Checks analytics permission again. |

All argument models forbid additional fields. `planning` is a persisted orchestration
step, not a callable model tool. At most four steps run: planning → analytics →
retrieval → report, with unneeded data steps omitted. `AGENT_MAX_STEPS` allows 2–4;
plans exceeding the configured limit fail rather than silently dropping requested tools.

The planner rejects requests for unsupported filters, individual customer data,
external actions, arbitrary code/SQL, or tools beyond the registry. Model decisions
can be imperfect; the backend allowlist prevents such capabilities from executing.
No complaint text or customer records are sent by the analytics tool. Task text is
best-effort redacted for emails, URLs, and long numbers before storage/model use;
this is not complete PII detection. Do not enter names, order IDs, or other personal data.
Relevant document text is sent under the same sharing rules as Phase 4.

### API examples

The following PowerShell examples use an existing workspace key from your shell;
they do not print it. Creating a run explicitly authorizes provider usage.

```powershell
$headers = @{ 'X-Workspace-Key' = $env:NEUROOPS_WORKSPACE_KEY }
$body = @{
  task = 'Summarize overall complaint categories and the last 30 days of trends, then find our refund policy.'
  provider_consent = $true
} | ConvertTo-Json
$run = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/agent/runs' -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/runs/$($run.id)" -Headers $headers
# After status is completed:
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/runs/$($run.id)/result" -Headers $headers
# Optional cancellation while queued/running:
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/agent/runs/$($run.id)/cancel" -Headers $headers
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/agent/runs?limit=20&offset=0' -Headers $headers
```

Creation returns **202**. Status is `queued`, `running`, `completed`, `failed`,
`cancelled`, or `timed_out`. The result endpoint returns **409** until completed.
Another workspace receives **404** for inspection, result, or cancellation. Errors
contain stable codes, not provider payloads, database details, or credentials.

Supported example tasks:

- “Summarize overall complaint statuses and the last 14 days of trends.”
- “Find the documented refund submission window.”
- “Summarize overall complaint categories and find our escalation policy.”

“Refund customer 123 and email them” is unsupported. No external action, customer
mutation, shell, Python execution, SQL generation, or unrestricted file tool exists.
Any future external or irreversible tool requires a separate explicit human approval
flow before execution; this phase does not introduce such tools or an approval bypass.

### Bounds, cancellation, and limitations

- Default execution acceptance deadline: **90 seconds**, configurable 5–180. It includes
  planning and queue time. Every attempt checks the deadline, provider I/O timeouts use
  the remaining budget capped at 25 seconds, and late outputs are discarded. PostgreSQL
  tool queries use a statement timeout of at most five seconds. Cancellation is
  cooperative: a request already sent to a provider cannot be recalled or unbilled.
  HTTPX timeouts are I/O timeouts, not a hard process kill; a pathological request or
  stuck database connection can outlive the deadline. No later output is accepted.
- Only rate limits, network unavailability, and provider timeouts receive one retry
  by default (configurable 0–1), with a short bounded delay. Invalid output, unsupported
  tasks, permission failures, and fabricated citations are not retried.
- Admission permits at most two live runs per workspace and eight globally, serialized
  with a PostgreSQL advisory lock. A per-process limiter allows five submissions per
  minute per workspace. These are guardrails, not a distributed billing quota.
- FastAPI BackgroundTasks is **not a durable job queue**. Restarted work is not resumed;
  an orphaned run becomes timed out when read after its deadline. Submit a new run to
  retry. Process-level worker isolation and a durable queue are future production work.
- Static workspace keys provide workspace access, not individual user identity. Legacy
  complaint GET APIs still need broader deployment authentication. Do not expose this
  local evaluation deployment publicly without that control.
- Retrieved documents and tool outputs are treated as data, not instructions. They
  cannot expand the tool registry or authorization. Prompt injection may still affect
  model wording or planning choices; exact citations do not verify an interpretation.
- Reports use original imported categories, not Phase 3 AI labels. Existing complaint
  classification remains available independently and is not automatically rerun.
- No calibrated confidence, proven root cause, or human verification is claimed.
  `recommendations` is intentionally empty: this version generates cited document
  interpretations and a fixed human-review next step, not speculative operational advice.
  Counts are never rewritten by an LLM. Live-provider quality has not been evaluated
  on a labeled company dataset.

### Phase 5 checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
# Optional disposable PostgreSQL database; tests create and remove their own schemas:
$env:TEST_POSTGRES_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/TEST_DATABASE'
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py tests/test_knowledge.py tests/test_agent.py -q
Remove-Item Env:TEST_POSTGRES_URL
cd ..\frontend
npm test
npm run build
```

Agent tests cover successful multi-step execution, actual aggregate queries, migrations
over existing complaints, scoped run access, revoked credentials, tool authorization,
invalid arguments/plans, missing configuration/data, insufficient evidence, fabricated
citations, transient retries, sanitized errors, deadlines, cancellation during retrieval,
duplicate dispatch, and admission limits. Frontend tests cover consent, timeline polling,
reports/citations, cancellation, errors, empty results, and stale-response protection.

## Phase 6: evaluation and model comparison

Open **LLM Evaluation** to use **Evaluation Workspace**. This phase evaluates supplied
responses; it does not generate candidate answers, train models, or automatically
change production complaints. Use responses from Phase 3 classification, Phase 4 RAG,
Phase 5 agent results, or other model experiments. Label the source in case metadata.
For classification, supply the model's JSON as the response and a human reference JSON
when available. For RAG/agents, reuse their actual chunk IDs as expected evidence.
Evaluation storage is independent of the production data tables.

### Setup

No new Python/JavaScript packages or paid services are required. Deterministic checks
are local and need no provider key. Optional judge calls reuse the existing backend
OpenAI adapter and account; usage can incur charges. Evidence search reuses the existing
embedding provider and workspace-scoped RAG retrieval.

Add settings to the existing backend `.env`, preserving its current secrets:

```dotenv
EVAL_JUDGE_PROVIDER=openai
# Empty falls back to LLM_MODEL; use a strict JSON-schema-capable model.
EVAL_JUDGE_MODEL=
# Replace placeholders with distinct random secrets of at least 32 characters.
EVAL_REVIEWER_KEYS_JSON={"operations":{"reviewer-alice":"replace-with-a-distinct-random-secret-at-least-32-characters"}}
```

`operations` must be an existing Knowledge Base workspace. Every endpoint requires its
`X-Workspace-Key`. Writing a human review additionally requires `X-Reviewer-Key` mapped
to a reviewer ID in that same workspace. Reviewer identity is derived on the backend,
never accepted as a user-supplied name. Keys stay in browser memory; the review key is
cleared after successful submission. This is capability-based authorization, not a
full identity/SSO service. Operators must provision and rotate reviewer keys securely.

Apply the additive migration and start the existing applications:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app
# Separate terminal from project root:
cd frontend
npm run dev
```

Migration `0005` creates `evaluation_cases`, `evaluations`, `evaluation_reviews`, and
`evaluation_comparisons`. It leaves complaints, classifications, documents, and agent
runs intact. Cases and evaluations have no update/delete API. Reviews append new
records; they never replace automated scores. A corrected evaluation remains auditable.

### Dataset and CSV format

Cases contain a question, supplied response, supplied model/provider labels, optional
reference, expected evidence, instructions, policy, deterministic rules, and metadata.
Model labels and references are user claims, not independently verified facts.

- Required CSV columns: `question`, `response`, `model`.
- Optional columns: `dataset`, `provider`, `reference`, `instructions`, `policy`,
  `evidence_chunk_ids`, `citations`, `rules`, `metadata`.
- The final four columns contain JSON. Metadata is a map of string keys to string values.
- UTF-8 (BOM accepted), raw `text/csv`, at most **1 MiB / 500 data rows**.
- Unknown/duplicate/missing required headers and malformed files are rejected before
  any import. Invalid individual rows are skipped; valid rows are stored in one
  transaction. The response reports inserted/duplicate/invalid counts and the first
  50 row errors. Row numbers are logical CSV record numbers with the header as row 1.
- Exact duplicate cases are skipped using a workspace-scoped canonical fingerprint.
  Different responses or metadata create separate cases. Existing cases are not changed.
- JSON requests are limited to 64 KiB before parsing; a case has a 48,000-byte limit,
  a 2,000-character question, 8,000-character response/reference, five evidence chunks,
  ten citation entries, and twenty metadata entries. Workspace capacity is 1,000 cases.
- Evidence IDs must resolve to **ready documents in the authenticated workspace**.
  The server snapshots actual passage text and document/page metadata. Arbitrary text
  cannot masquerade as a verified company passage. Selection does not guarantee relevance.

`backend/examples/evaluation_cases.csv` contains two **synthetic** responses for a
fictional refund policy. Both use `metadata.sample="true"`, which the case list displays
as sample data. The file is never automatically imported and is not company evidence.

Example rules and citation representation:

```json
{
  "rules": {"max_words":100,"required_terms":["refund"],"json_object":false,"require_citations":true},
  "evidence_chunk_ids": ["actual-workspace-chunk-uuid"],
  "citations": [{"chunk_id":"actual-workspace-chunk-uuid","quote":"An exact excerpt from that chunk."}],
  "metadata": {"source":"phase4-rag","sample":"false"}
}
```

Replace the example ID with an actual UUID and include `[source:UUID]` in the supplied
response. The optional **Search workspace evidence** button uses existing semantic
retrieval; it requires provider consent. You can instead copy chunk IDs from existing
RAG/agent sources without a new search call.

### Metric definitions — rubric `eval-v1`

Scores are reported per method and metric, normalized to 0–1 (the UI displays percent).
They are **rubric scores, not calibrated probabilities**. There is no combined quality
score. Every saved result includes the complete rubric, evaluator/provider/model,
prompt version, timestamp, safe error code, and any later review history.

| Metric | Deterministic measurement | Optional LLM judgment |
| --- | --- | --- |
| Correctness | Reference exact match after Unicode NFKC normalization, case-folding, and collapsing whitespace: equal = 1, otherwise 0. No reference = not assessed. This is only a lexical proxy; equivalent paraphrases can score 0. | Semantic consistency with supplied reference or selected evidence. Neither available = not assessed, even if the judge returns a score. |
| Relevance | No lexical-overlap score is presented as semantic relevance. | Whether the response addresses the question without irrelevant content. |
| Instruction following | Passed configured checks / total configured checks: max whitespace-delimited word count, each required case-insensitive substring, and valid JSON object. No checks = not assessed. | Compliance with supplied instructions/rules. None supplied = not assessed. |
| Groundedness | No string-matching score is presented as factual entailment. | Whether substantive response claims are supported by selected passages. No evidence = not assessed. |
| Citation validity | Valid distinct source markers / all distinct asserted sources. Valid means a `[source:ID]` marker, selected workspace evidence, and an explicit exact-substring quote all agree. Extra citation metadata counts as an invalid asserted source. Required but absent citations = 0; absent and not required = not assessed. This verifies source/quote integrity, not that a claim follows from a passage. | Citation integrity is not delegated to the judge. Groundedness is assessed separately. |
| Safety/policy | Narrow credential-pattern screen: 0 for a token matching `sk-` plus 16+ characters, an AWS-style access ID, or a private-key header; otherwise 1. Absence of a match does not prove safety. | Compliance with the explicitly supplied policy. No policy = not assessed. This is not a universal safety certification. |

The judge uses integers: **0** fails/contradicts support, **1** major problems,
**2** partial with material omissions, **3** mostly meets with minor issues,
**4** fully meets on supplied context. Stored normalized score = integer / 4.
The judge may return null when evidence is insufficient. Missing required evaluation
context always forces null on the backend. Missing data is never turned into a zero
or a fabricated perfect score. Reasons accompany each assessment.

The judge receives a fixed rubric and JSON data, with instructions to treat questions,
candidate answers, references, policies, and document passages as untrusted. Pydantic
rejects extra fields, wrong types, out-of-range scores, refusals, and malformed output.
No model tools, arbitrary SQL, code execution, or production writes are available.
These constraints cannot guarantee an unbiased, prompt-injection-proof, or objectively
correct judge. References and policies themselves require human validation.

### Evaluation and human-review workflow

1. Connect to the workspace; create a case or import the sample/your own CSV.
2. Select a case. Run local deterministic checks, or enable the LLM judge and explicitly
   approve provider sharing. Only relevant evaluation fields are sent; model labels,
   arbitrary metadata, reviewer information, and credentials are excluded.
3. Inspect separate deterministic and LLM tables, not-assessed values, evidence, and
   evaluator metadata. Judge failures preserve deterministic scores and an error code.
4. A reviewer supplies a separate reviewer key, chooses approve/reject/correct, and
   writes feedback. Corrections map metric names to a 0–1 score (or null) and reason.
   Corrections are separate human opinions; they do not change the automated result,
   dashboard distributions, comparison snapshots, or any model weights.
5. New evaluations create new attempts. Each case supports up to 20 attempts and each
   attempt up to 20 reviews. History is visible in the case panel.

Sample API calls (workspace/reviewer secrets come from your shell, not source code):

```powershell
$headers = @{ 'X-Workspace-Key' = $env:NEUROOPS_WORKSPACE_KEY }
$created = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/evaluation/cases' -Headers $headers -ContentType 'application/json' -Body (@{
  dataset='synthetic-demo'; model='supplied-model-a'; question='What is the sample refund window?'
  response='Thirty days.'; reference='Thirty days.'; metadata=@{sample='true'}
} | ConvertTo-Json)
$evaluation = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/evaluation/cases/$($created.case.id)/evaluate" -Headers $headers -ContentType 'application/json' -Body '{"use_judge":false}'
$reviewHeaders = @{ 'X-Workspace-Key'=$env:NEUROOPS_WORKSPACE_KEY; 'X-Reviewer-Key'=$env:NEUROOPS_REVIEWER_KEY }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/evaluation/results/$($evaluation.id)/reviews" -Headers $reviewHeaders -ContentType 'application/json' -Body '{"decision":"approve","feedback":"Reviewed against the supplied synthetic reference."}'
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/evaluation/cases/import' -Headers $headers -ContentType 'text/csv' -InFile 'backend/examples/evaluation_cases.csv'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/evaluation/summary?dataset=synthetic-demo' -Headers $headers
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/evaluation/export?format=json&dataset=synthetic-demo' -Headers $headers -OutFile 'evaluation-results.json'
```

### Model comparison

Select **two to four** cases and compare their supplied responses and latest available
metric results side by side. The cases must share the normalized question, reference,
instructions, rules, policy, and expected evidence. Use **Use question for another model**
to prefill this context. Responses are supplied; this phase never silently runs models
or claims their labels are authenticated. Unevaluated responses show “Not evaluated.”

Optional pairwise judging requires exactly **two** responses and provider consent.
The rubric considers correctness where assessable, relevance, instruction following,
groundedness where assessable, and supplied policy. Labels are blinded; initial order
is randomized; the judge runs twice with reversed order. Matching preferences are
reported for this case only; disagreement becomes **inconclusive**. Tie and insufficient
are valid outcomes. Reasons, both orders, provider/model, prompt version, rubric, and
timestamp are retained. This costs two judge requests. It does not remove all position,
verbosity, self-preference, dataset, or rubric bias and never establishes a universal winner.

`POST /api/evaluation/comparisons` accepts
`{"case_ids":["UUID-A","UUID-B"],"use_judge":true,"provider_consent":true}`.
`GET /api/evaluation/comparisons` lists workspace snapshots (limit/offset supported).
Each workspace supports 200 comparison snapshots. Snapshots do not change when later
evaluations or reviews are added; create a new comparison to include new results.

### Dashboard, filters, and exports

The dashboard derives volumes, metric distributions, and failure indicators from
stored automated evaluations. It shows assessed and not-assessed denominators, means
excluding nulls, and zero/partial/full-score buckets **separately per method/metric**.
Repeated attempts count separately; distinct-case counts reveal the difference.
Model-label counts are descriptive, not rankings. Human corrections remain separate.

`GET /api/evaluation/cases`, `/results`, `/summary`, and `/export` support exact `dataset`,
`model`, `status` (`completed`/`failed`), `start`, and `end` filters. Dates are inclusive
UTC calendar dates. Dashboard/results/export date filters apply to evaluation time;
case-list dates apply to case creation. A case-list status filter matches any attempt,
while its card shows the latest attempt. Lists support `offset` and bounded `limit`.

Exports support CSV and JSON and include original responses, automated scores, rubric,
evaluator, evidence context, errors, and full review history. Exports over 1,000
evaluations are refused with a request to narrow filters; no silent truncation occurs.
CSV cells that could be interpreted as spreadsheet formulas are prefixed with an
apostrophe. JSON preserves the exact stored strings. Exports contain sensitive business
data and are authorized by workspace; responses use `Cache-Control: no-store`.

### Reliability and remaining limitations

- Judge rate limiting is ten costly actions/minute/workspace/process (a pairwise action
  makes two calls). Existing provider timeouts cap each I/O operation at 25 seconds;
  an evaluation/comparison shares a 60-second acceptance deadline. No automatic judge
  retry is performed. Missing credentials, rate limits, timeouts, provider failures,
  and invalid output are saved as failed attempts with safe error codes.
- These endpoints are synchronous and bounded. A browser/network failure after a save
  may leave a completed attempt; refresh history before retrying. PostgreSQL advisory
  locks serialize case creation/history caps; this is not a distributed task queue.
- No paid-provider quality benchmark was run. Mocked tests verify contracts, score
  calculations, authorization, and error handling—not model quality on company data.
- Evidence snapshots preserve what was evaluated; they are not automatically refreshed
  when company documents change. Scores from different rubrics, judge models, or data
  populations must not be treated as directly interchangeable; inspect saved metadata.
- The shared rubric is versioned in code. Arbitrary client-provided rubric code or
  executable scoring logic is not supported. The configured judge provider currently
  supports OpenAI only; other identifiers fail closed. Local checks work without it.
- De-identify inputs before opting into provider sharing. Original supplied responses
  are preserved for audit; evaluation does not automatically redact them because that
  would change what is measured. `store:false` is not a zero-retention guarantee.
- Workspace/reviewer capabilities need secure distribution and rotation. The legacy
  global complaint APIs still need broader deployment authentication before public use.
- No automatic model training, fine-tuning, production feedback mutation, or universal
  model-winner claims are implemented.

### Phase 6 checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
# Optional isolated test database; fixtures create and remove their own schemas:
$env:TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/TEST_DATABASE'
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py tests/test_knowledge.py tests/test_agent.py tests/test_evaluation.py -q
Remove-Item Env:TEST_POSTGRES_URL
cd ..\frontend
npm test
npm run build
```

## Phase 7: production operations

See `PRODUCTION_READINESS.md` for the audit, PASS/FAIL/NOT VERIFIED checklist,
exact verification commands, and remaining deployment blockers. **This project has
not been deployed or certified production-secure.** Existing Phase 1–6 functionality
is preserved; local development stays compatible, while production requires user
authentication in addition to the existing capability keys.

### Access control and roles

Set `APP_ENV=production` for any non-local deployment. Production cannot disable
authentication via `AUTH_REQUIRED=false`. Unknown environment names also require
authentication. For local authentication testing, use `AUTH_REQUIRED=true` with the
development environment. Never expose unauthenticated development mode publicly.

`AUTH_USERS_JSON` maps user IDs to a role, workspace, and SHA-256 digest of a random
32–512 character access token. Tokens are high-entropy credentials, **not passwords**.
Do not use memorable passwords with unsalted SHA-256. Generate a token and digest
in your own trusted terminal, transfer the token securely to its user, and store only
the digest in backend configuration. Do not paste tokens into source control, logs,
screenshots, or chat. Example generation command (intentionally prints the new token
only in your terminal):

```powershell
python -c "import secrets,hashlib; t=secrets.token_urlsafe(36); print('User token:',t); print('SHA256:',hashlib.sha256(t.encode()).hexdigest())"
```

Configuration shape (replace the placeholder with the actual lowercase digest):

```dotenv
APP_ENV=production
AUTH_USERS_JSON={"alice":{"token_sha256":"64_lowercase_hex_sha256_digest","role":"operator","workspace":"operations"}}
KB_ANALYTICS_WORKSPACE=operations
```

| Role | Allowed actions |
| --- | --- |
| viewer | Read authorized workspace data and installation complaints only when assigned to the analytics workspace. |
| operator | Viewer access plus imports, classification, document uploads/questions, evaluation creation/execution, and agent execution/cancellation. Cannot write human reviews. |
| reviewer | Read access plus human reviews. Cannot create/run/upload data. |
| admin | All actions within their assigned workspace, plus operational metrics. Does not bypass workspace isolation. |

Protected requests carry `Authorization: Bearer USER_ACCESS_TOKEN`. Existing
`X-Workspace-Key`, `X-Import-Key`, and `X-Reviewer-Key` requirements remain in place.
The authenticated workspace must match the workspace capability; an admin token
cannot read another workspace. A review requires both reviewer/admin role and the
separate reviewer key. Provider keys never appear in the frontend.

The frontend checks `/api/auth/config` and displays a sign-in form when required.
The user token stays in memory and is attached only by the API transport. Sign-out
unmounts workspace screens and clears the token; reload requires signing in again.
Configuration failure keeps the application behind the access screen. Tokens are
not stored in localStorage, sessionStorage, cookies, URLs, or source files.

Rotate access by replacing/removing the configured digest and restarting the deployed
processes. New requests revalidate it; active agent/evaluation operations recheck the
principal before accepting output. Static tokens currently have no automatic expiry,
MFA, account-recovery flow, or enterprise SSO. Use a managed identity-aware ingress
and short credential-rotation procedures where those are required.

### Docker configuration and safe startup

The root `.env.example` is for Compose; `backend/.env.example` is for direct Python
execution. Never overwrite an existing `.env` to upgrade configuration.

```powershell
# Project root; Docker Desktop/Engine and Compose v2 must already be installed.
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env locally before proceeding.
docker version
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Set unique `POSTGRES_PASSWORD`, `DATABASE_URL`, access-token hashes, workspace keys,
and import/reviewer credentials. The database URL must use hostname `db` inside
Compose, database/user `neuroops`, and the same password as `POSTGRES_PASSWORD`.
URL-encode special password characters in the URL. Existing PostgreSQL volumes keep
their original password; changing an environment variable does not rotate a stored
database user's password. Rotate the role explicitly with a database administrator.

Compose runs four services: persistent PostgreSQL, a one-shot migration process,
FastAPI, and Nginx/static React. The migration service applies `alembic upgrade head`
before API readiness. Only `127.0.0.1:8080` is published; database/API ports are internal.
Compose always sets `APP_ENV=production`, even if the root file says development.
The backend and frontend use non-root images/users, read-only roots, bounded temporary
storage, dropped capabilities, no-new-privileges, process limits, memory limits, and
rotating container logs. Frontend health checks the static server; backend readiness
checks the database and schema. Docker execution has **not** been verified here.

Open `http://localhost:8080` and use your assigned access token. Check public probes:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health
Invoke-RestMethod http://127.0.0.1:8080/api/ready
docker compose logs --tail 100 backend migrate
docker compose down
```

Do not run `docker compose config` without `--quiet` in shared logs: resolved
configuration can expose secrets. Docker environment variables are visible to host
administrators; use your hosting platform's secret injection and restrict Docker access.
`docker compose down` preserves the named database volume. `down -v` deletes it.

### Database migrations and deployment sequence

Revision `0006` adds the evaluation running/deadline fields and composite history/
workspace indexes. It does not change original complaint contents. PostgreSQL pool
capacity is bounded (5 connections plus 5 overflow), pool wait/connect timeout is five
seconds, statements time out after 15 seconds, lock waits after five seconds, and idle
transactions after 120 seconds. Agent tool statements retain their shorter deadline.

For an existing deployment, take and verify a backup, stop new work, allow active
requests to drain, and use one migration process. Never run schema changes concurrently
from every API replica. For Compose upgrades:

```powershell
docker compose stop frontend backend
docker compose build
docker compose run --rm migrate
docker compose up -d
docker compose ps
```

For direct Python execution, activate the backend virtual environment, configure the
database and access settings, then run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers --limit-concurrency 64 --timeout-graceful-shutdown 30
```

Readiness returns 503 until schema `0006` and authentication configuration are ready.
Do not downgrade a live database as a routine rollback. Restore a verified backup or
deploy backward-compatible code after assessing the migration. Test downgrade/restore
procedures independently before production; backup restore was not verified here.

The bundled PostgreSQL bootstrap account owns schema migrations and is a superuser
under the official image's initialization behavior. **Before public production use,
provision a separate least-privilege runtime role and migration role**, point the API
at the runtime credentials, and keep migration credentials out of the API environment.
The bundled single-host Compose is a staging/local deployment baseline, not a complete
managed-database security policy. Prefer managed PostgreSQL with encrypted connections,
restricted networking, backups, and audited role management for public deployments.

### Job reliability and restart behavior

Evaluation attempts are committed as `running` before the judge call; capacity is
reserved and the database lock released. Their deadline and original deterministic
checks remain visible even if the process stops. On completion, only a still-running
attempt can accept output; late output is discarded. Unexpected evaluator exceptions
become safe failure codes. The existing synchronous endpoint and response shape remain
compatible, so callers need not migrate to a new queue API.

An authenticated deployment runs a small maintenance loop every 15 seconds. It marks
expired evaluation attempts as failed and expired agent runs/steps as timed out,
including work left by a restarted process. Evaluation routes also expire stale
attempts when read. This is bounded cleanup, **not automatic replay**: retry explicitly
after inspecting history, because replaying provider calls could charge twice.

Agent cancellation remains cooperative; external calls already in flight may finish,
but their outputs are discarded after cancellation/deadline/revocation. Agent retries
remain at most one and only for the existing transient error allowlist. Evaluations
have no automatic retry. Pairwise comparisons remain synchronous and can be lost if
the process stops before their snapshot is saved; inspect comparison history before
resubmitting. A durable distributed queue, hard worker termination, and automatic
continuation are not implemented. Add those only when operational scale warrants it.

### Monitoring, logs, and health

- `GET /api/health`: public process liveness; intentionally does not prove dependency health.
- `GET /api/ready`: public, coarse database/schema/auth-configuration readiness; returns
  a safe 503 code on failure, without connection strings or database errors.
- `GET /api/metrics`: administrator-only when authentication is required; JSON counters
  by response status and total request duration for this API process. Resets on restart.
- `X-Request-ID`: server-generated UUID on responses. Incoming IDs are not trusted.
- Structured `neuroops.requests` logs contain event, request ID, normalized route
  template, method, status, and duration. No request/response bodies, query strings,
  workspace/reviewer tokens, provider keys, complaint content, or raw database exceptions.
- Default Uvicorn access logging is disabled in the container/documented command to
  prevent raw query strings in logs. Nginx access logs are disabled; application logs
  provide the safe request record. Avoid enabling debug/SQL/provider-body logging.
- Errors omit exception details and submitted validation inputs. Use the request ID
  to correlate safe logs; inspect configuration locally rather than logging secrets.

Alert on readiness failures, elevated 5xx/429 rates, rising request duration, and
agent/evaluation timeout counts via their authenticated status APIs. Metrics are basic
operational signals, not a full Prometheus stack or distributed tracing system. If
running multiple API processes, collect each independently and use a shared limiter.

### Uploads, limits, CORS, and edge protection

Existing CSV/PDF/TXT limits and evidence authorization are preserved. Evaluation
JSON is bounded before parsing. PDF extraction has byte/page/text/decoder limits,
but it is not OS-sandboxed against every hostile PDF; production untrusted upload
workloads need isolated parsing workers. Tables/history remain paginated or capped.
New indexes target common workspace/history queries; no load benchmark was performed.

Set `CORS_ORIGINS_JSON` to exact permitted origins. Use `[]` for same-origin Nginx
hosting. Wildcards are rejected. Only the required auth/content headers are allowed;
request IDs are exposed. Production API docs are disabled. Nginx adds CSP, no-sniff,
frame denial, and no-referrer headers. Inline styles remain allowed because the
existing chart/layout components use them; inline scripts are not allowed.

Authenticated request limits are 120/minute/identity/process, alongside existing
workspace provider limits. Nginx adds 10 requests/second/IP with a burst of 40 and 429
responses, body/header timeouts, and a 10 MiB edge body limit. These controls are not
a distributed quota or DDoS service. Put a managed TLS ingress in front of public
deployments, set appropriate proxy rate limits, and keep database/API ports private.
TLS/HSTS and forwarded-client identity must be configured and verified at that ingress.

### Troubleshooting

| Symptom | Check |
| --- | --- |
| Sign-in unavailable | Start the backend; check `/api/auth/config` and readiness. The UI fails closed on configuration errors. |
| 401 | Use the user access token as Bearer auth; check its hash and any required workspace/import key. |
| 403 | Check role and assigned workspace. Reviewer keys do not replace reviewer role. |
| Startup auth error | `AUTH_USERS_JSON` must contain distinct valid hashes, recognized roles, and valid workspace IDs. |
| Readiness 503 | Confirm PostgreSQL connectivity, run migration `0006`, and validate auth configuration. |
| 429 | Respect per-user/workspace/edge limits; avoid blindly retrying paid calls. |
| Evaluation remains running after restart | Wait until its deadline plus maintenance interval, then inspect history; local development expires it on read. |
| Database auth fails after changing `.env` | Existing volume credentials are unchanged; rotate the PostgreSQL role explicitly. |
| Docker command unavailable | Install/start Docker Desktop or use direct local Python/PostgreSQL. Docker checks remain unverified until run. |
| Proxy timeout during document processing | Inspect persisted document status before retrying; existing processing lease handles interrupted ingestion. |

### Verification commands

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
$env:TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:PORT/TEST_DATABASE'
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py tests/test_knowledge.py tests/test_agent.py tests/test_evaluation.py tests/test_operations.py -q
# Requires CREATE DATABASE on an explicitly local disposable PostgreSQL server:
.\.venv\Scripts\python.exe scripts/smoke.py
Remove-Item Env:TEST_POSTGRES_URL
cd ..\frontend
npm test
npm run build
```

The smoke script creates a unique disposable database, applies all migrations, starts
a real Uvicorn process in production mode, checks authorization/readiness over HTTP,
then stops that process and removes only its own database. No paid calls are made.
Do not point tests at a customer database. All Phase 7 changes remain uncommitted.

---

## Phase 8: Final Validation & Portfolio Readiness

### Verified Test Summary

```text
Backend Suite:   157 passed, 1 skipped, 1 warning (11.02s)
Operations Suite: 17 passed, 1 warning (1.50s)
HTTP Smoke Test:  9 of 9 real HTTP checks passed (Uvicorn + PostgreSQL 16)
Migrations:      0001 through 0006 linear and verified
Frontend Suite:  33 passed across 7 test files (7.02s)
Frontend Build:  Vite production bundle built in 4.93s (zero TypeScript errors)
Requirements:    pip check confirmed no broken dependencies
```

- **Skipped Test Explanation:** `test_concurrent_postgres_uploads_share_one_document_version` is designed specifically for PostgreSQL row-level locking (`FOR UPDATE`) and concurrent thread execution. It gracefully skips when running against SQLite.
- **Deprecation Warning Assessment:** `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.` is an informational notice from Starlette regarding future library iterations. It is non-blocking and requires no intervention.

### Portfolio & Documentation Links

- **Audit Report:** [PHASE8_FINAL_AUDIT.md](file:///C:/Users/mayank%20singh/Desktop/neuroops-ai/PHASE8_FINAL_AUDIT.md) — Comprehensive verification matrix, exact commands executed, output logs, blocker details, and Docker instructions.
- **Portfolio & Interview Guide:** [PORTFOLIO_GUIDE.md](file:///C:/Users/mayank%20singh/Desktop/neuroops-ai/PORTFOLIO_GUIDE.md) — Resume summary, architecture flowcharts, deep-dive into major modules, 5-minute live demo script, and 15+ code-defended interview questions.

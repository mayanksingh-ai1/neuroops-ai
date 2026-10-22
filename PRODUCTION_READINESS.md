# NeuroOps AI — Phase 7 production-readiness audit

Date: 2026-10-22, Asia/Calcutta.

**Overall: not ready for unrestricted public deployment.** The application hardening
and regression checks below pass, but Docker execution, TLS, backup restoration,
least-privilege deployment credentials, and live-provider behavior remain outstanding.
No deployment, security certification, commit, or push was performed.

## Audit findings and changes

| Finding | Change / disposition |
| --- | --- |
| Complaint/analytics GET routes were public | Production access middleware now authenticates every non-public endpoint, restricts roles, and confines complaint access to the configured analytics workspace. Development compatibility is explicit. |
| Shared workspace keys lacked user-level roles | Added hashed per-user access tokens and viewer/operator/reviewer/admin roles, supplementing existing workspace/import/reviewer keys. Tokens stay in browser memory. |
| Provider work could outlive credential revocation | Agent/evaluation acceptance rechecks role, workspace, user existence, and credential hash. |
| Evaluations existed only after provider completion | Persist running attempts/deadlines before calls, release capacity locks, preserve failures, and discard expired output. |
| Orphaned agent work expired only on inspection | Production maintenance expires stale run/step and evaluation states every 15 seconds. No automatic paid-call replay. |
| Raw validation errors echoed submitted values | Validation responses omit input objects. Unexpected exceptions use safe codes. |
| No request correlation or readiness | Added generated request IDs, privacy-preserving structured logs, process metrics, and database/schema/auth readiness. |
| Default access logs could expose query strings | Container/documented Uvicorn commands disable access logs; Nginx access logs disabled; safe application logs retained. |
| Fixed Compose database password and published DB/API ports | Password and URL are required environment values; only frontend loopback port is published. |
| Root containers and concurrent migration startup | Non-root backend/frontend, read-only roots, reduced privileges/resources, separate migration service, health/readiness dependency chain. |
| History queries lacked composite indexes | Migration 0006 adds workspace/time, case/time, status/deadline indexes. Pool/statement/lock/idle-transaction waits are bounded. |
| CORS accepted arbitrary headers | Explicit origins and required headers only; wildcards rejected. Nginx adds security headers and edge rate/body/time limits. |
| PDF parsing and provider reliability limitations | Existing bounded extraction and mocked provider tests preserved; OS parser isolation and live-provider validation remain unverified. |

## Readiness checklist

PASS means the named check passed; it is not a blanket production-security claim.

| Item | Status | Evidence / limitation |
| --- | --- | --- |
| Existing backend behavior | PASS | 157 passed, 1 PostgreSQL-only skip in local suite. |
| PostgreSQL migrations and integration | PASS | 143 selected tests passed, including populated migrations through 0006. |
| Frontend tests | PASS | 33 tests across 7 files passed. |
| TypeScript and production assets | PASS | Vite production build passed. |
| Real HTTP API smoke checks | PASS | Nine checks against real Uvicorn/PostgreSQL in production mode. |
| Anonymous production sensitive-endpoint access denied | PASS | RBAC regression tests plus live HTTP 401 checks. |
| Role restrictions and workspace mismatch denial | PASS | Viewer/operator/reviewer/admin tests and HTTP 403 checks. |
| Existing reviewer/data/run scopes preserved | PASS | Phase 3–6 suites pass alongside new access layer. |
| Credential rotation acceptance check | PASS | Regression rejects a changed credential digest during work. |
| Frontend token memory-only lifecycle | PASS | AccessGate tests cover fail-closed config, sign-in, and token clearing on sign-out. |
| Request IDs and safe logs/errors | PASS | Tests verify request correlation, omission of query/token values, and sanitized exceptions/validation. |
| Readiness rejects stale schema | PASS | Migration mismatch test and HTTP readiness check. |
| Running evaluation persistence and failure recording | PASS | Provider mock observes committed running attempt before failure. |
| Abandoned run/evaluation expiration | PASS | Maintenance regression tests; no automatic resumption claimed. |
| Existing CSV/PDF/JSON limits and citation isolation | PASS | Existing regression suites plus new auth layer pass. |
| Compose YAML syntax and safe configuration assertions | PASS | PyYAML parses services/anchors; no published DB port or fixed password. This is not Compose execution. |
| Docker image build | NOT VERIFIED | Docker executable absent. |
| Docker Compose startup / container health | NOT VERIFIED | Docker executable absent. |
| Nginx configuration/CSP in a running browser/container | NOT VERIFIED | Source reviewed; no Nginx or Docker execution here. |
| TLS/HSTS/public ingress deployment | NOT VERIFIED | No public deployment or certificate configuration performed. |
| Database runtime least privilege | FAIL | Bundled PostgreSQL bootstrap account is also the default application/migration account. Provision separate restricted runtime and migration credentials before public deployment. |
| Durable job resume / hard worker deadlines | FAIL | Stale work is safely failed, not resumed. Cooperative provider I/O can outlive a logical deadline. Pairwise comparisons remain synchronous. |
| Distributed rate limiting | FAIL | Process-local limits plus single-proxy edge limits; multi-replica coordination not implemented. |
| MFA/SSO/automatic user-token expiry | FAIL | Explicitly scoped static high-entropy user tokens; secure rotation required. |
| Backup restore / disaster recovery | NOT VERIFIED | Operational instructions provided, restore drill not executed. |
| Load/soak testing and query-plan benchmarks | NOT VERIFIED | Indexes/timeouts tested functionally only. |
| Dependency vulnerability/container scanning | NOT VERIFIED | `pip check` is compatibility checking, not a vulnerability scan. Base image digests and Python transitive dependencies are not fully pinned. |
| Real LLM/provider quality and production credentials | NOT VERIFIED | All tests use mocked providers; no paid calls made. |
| Independent penetration test | NOT VERIFIED | No external assessment performed. |
| No automatic training or customer mutation | PASS | No training workflow introduced; existing read-only investigation behavior remains. |
| No commit or push | PASS | Changes remain in the local working tree. |

## Exact verification commands and results

Project: `C:\Users\mayank singh\Desktop\neuroops-ai`.

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

**157 passed, 1 skipped, 1 warning in 19.34 seconds.** The skip is a PostgreSQL-only
concurrency check exercised below. The warning is the existing Starlette HTTPX
TestClient deprecation.

```powershell
$env:TEST_POSTGRES_URL='postgresql+psycopg://postgres@127.0.0.1:55439/postgres'
.\.venv\Scripts\python.exe -m pytest tests/test_intelligence.py tests/test_knowledge.py tests/test_agent.py tests/test_evaluation.py tests/test_operations.py -q
```

**143 passed, 1 warning in 76.89 seconds.** Tests created and removed isolated schemas
on the disposable PostgreSQL 16 cluster. They did not migrate the application's real DB.

```powershell
$env:TEST_POSTGRES_URL='postgresql+psycopg://postgres@127.0.0.1:55439/postgres'
.\.venv\Scripts\python.exe scripts/smoke.py
```

**9 real HTTP checks passed**: health 200, readiness 200, anonymous complaints 401,
anonymous evaluation cases 401, authenticated complaint read 200, viewer import 403,
viewer metrics 403, authenticated production docs 404, and session metadata 200.
Every response included a request ID and omitted the test access token. The script
created a unique database, applied migration 0006, started/stopped Uvicorn, and dropped
only that disposable database. No provider calls were made.

From `frontend/`:

```powershell
npm test
npm run build
```

- **33 tests passed across 7 files**, duration **13.19 seconds**.
- **Build passed**, Vite duration **10.25 seconds**. JS **585.14 kB / 168.02 kB gzip**;
  CSS **25.95 kB / 6.73 kB gzip**.
- Existing warnings: Recharts zero-size layout in jsdom; main JS chunk exceeds 500 kB.

From project root:

```powershell
.\backend\.venv\Scripts\python.exe -m compileall -q backend/app
.\backend\.venv\Scripts\python.exe -m pip check
git diff --check
.\backend\.venv\Scripts\python.exe -c "from pathlib import Path; import yaml; d=yaml.safe_load(Path('docker-compose.yml').read_text(encoding='utf-8-sig')); assert set(d['services'])=={'db','migrate','backend','frontend'}; assert d['services']['backend']['environment']['APP_ENV']=='production'; assert 'ports' not in d['services']['db']; print('Compose YAML syntax and safe-default assertions passed (not Docker validation).')"
docker version
```

Compile/import checks passed. No broken Python requirements. No whitespace errors
(Git emitted Windows LF/CRLF notices). YAML assertions passed. `docker version`
**failed** because `docker` is not installed/on PATH; the standard Docker Desktop
executable path was also absent. Build/start checks could not be executed.

Two edit-tool patch attempts were rejected due to duplicate-target and stale-context
validation; the files were reread and the edits applied successfully. These were
editing failures, not application test failures.

The temporary PostgreSQL start initially reported another server might be running,
then completed successfully. Its status/log were inspected before using port 55439.
The temporary cluster was stopped after verification; no application database or
user secret file was overwritten.

## Phase 7 files changed

- Backend: `app/security.py`, `app/operations.py`, `app/job_maintenance.py`,
  `app/main.py`, `app/database.py`, `app/agent_service.py`, `app/evaluation_models.py`,
  `app/evaluation_service.py`, `app/evaluation_routes.py`.
- Migration: `migrations/versions/0006_operations.py`.
- Tests/tooling: `tests/test_operations.py`, `scripts/smoke.py`.
- Frontend: `src/api/access.ts`, existing dashboard/knowledge/agent/evaluation API
  clients, `src/components/AccessGate.tsx`, `AccessGate.test.tsx`,
  `EvaluationWorkspace.tsx`, `src/main.tsx`, `src/styles.css`.
- Deployment/docs: both Dockerfiles and `.dockerignore` files, `frontend/nginx.conf`,
  `docker-compose.yml`, root/backend environment examples, README, this report.

Earlier Phase 4–6 uncommitted files remain present and were preserved. `git status`
therefore lists more files than this Phase 7 change set.

## Recommended deployment order

1. Install Docker on a staging host; configure unique secrets and token hashes using
   the root environment example. Keep the `.env` private and out of Git.
2. Provision separate least-privilege database runtime/migration identities, backups,
   private networking, and TLS ingress. Do not expose local development mode.
3. Run `docker compose config --quiet`, image builds, startup, readiness, authentication,
   and UI smoke tests. Validate Nginx read-only operation and CSP in that environment.
4. Run backup/restore drills, image/dependency scans, and workload/load tests. Pin tested
   dependency/image versions or digests. Add identity/queue/rate-limit infrastructure
   only if deployment requirements need MFA, durable continuation, or multiple replicas.
5. Verify a small approved live-provider dataset with explicit cost/PII controls;
   mocked tests do not establish production model quality.
6. Deploy only after the relevant FAIL/NOT VERIFIED checklist items are resolved and
   rollback/monitoring procedures have been rehearsed. No deployment is claimed here.

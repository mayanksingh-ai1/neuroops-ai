"""Complaint storage, analytics, and operator-triggered intelligence."""

import os
import json
import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .analysis_routes import router as analysis_router
from .knowledge_routes import router as knowledge_router
from .agent_routes import router as agent_router
from .evaluation_routes import router as evaluation_router
from .evaluation_limits import EvaluationBodyLimit
from .knowledge_limits import KnowledgeQuestionLimit
from .security import AccessControl, required, users
from .operations import RequestTelemetry, readiness, metrics
from .job_maintenance import maintenance


@asynccontextmanager
async def lifespan(app):
    stop = threading.Event()
    thread = None
    if required():
        users()  # Fail startup rather than silently permit anonymous production access.
        logging.getLogger('neuroops.requests').setLevel(logging.INFO)
        if not logging.getLogger('neuroops.requests').handlers:
            logging.getLogger('neuroops.requests').addHandler(logging.StreamHandler())
        thread = threading.Thread(target=maintenance, args=(stop,), daemon=True)
        thread.start()
    yield
    stop.set()
    if thread:
        thread.join(timeout=1)


def cors_origins():
    values = json.loads(os.getenv('CORS_ORIGINS_JSON', '["http://localhost:5173","http://127.0.0.1:5173","http://localhost:8080","http://127.0.0.1:8080"]'))
    if not isinstance(values, list) or any(not isinstance(item, str) or item == '*' or not item.startswith(('https://', 'http://')) for item in values):
        raise ValueError('CORS_ORIGINS_JSON must be an explicit JSON array of origins.')
    return values

app = FastAPI(
    title="NeuroOps AI API",
    description="Complaint storage, analytics, and unverified AI suggestions.",
    version="0.7.0",
    lifespan=lifespan,
    docs_url=None if required() else '/docs',
    redoc_url=None if required() else '/redoc',
    openapi_url=None if required() else '/openapi.json',
)

app.add_middleware(KnowledgeQuestionLimit)
app.add_middleware(EvaluationBodyLimit)
app.add_middleware(AccessControl)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-Key", "X-Reviewer-Key", "X-Import-Key"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestTelemetry)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default includes the submitted input, potentially private text/secrets.
    return JSONResponse({'detail': [{'loc': error['loc'], 'msg': error['msg'], 'type': error['type']}
                                    for error in exc.errors()]}, status_code=422)


@app.get('/api/auth/config')
def auth_config():
    return {'required': required()}


@app.get('/api/auth/session')
def auth_session(request: Request):
    identity = request.scope.get('principal')
    return {'principal': {key: identity[key] for key in ('id', 'role', 'workspace')} if identity else None, 'required': required()}


@app.get('/api/ready', tags=['system'])
def ready():
    return readiness()


@app.get('/api/metrics', tags=['system'])
def operational_metrics():
    return metrics()


@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Report that the API process is responding; this does not check dependencies."""
    return {"status": "ok", "service": "neuroops-api"}


app.include_router(router)
app.include_router(analysis_router)
app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(evaluation_router)

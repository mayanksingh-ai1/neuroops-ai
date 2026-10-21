"""Complaint storage, analytics, and operator-triggered intelligence."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .analysis_routes import router as analysis_router

app = FastAPI(
    title="NeuroOps AI API",
    description="Complaint storage, analytics, and unverified AI suggestions.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Report that the API process is responding; this does not check dependencies."""
    return {"status": "ok", "service": "neuroops-api"}


app.include_router(router)
app.include_router(analysis_router)

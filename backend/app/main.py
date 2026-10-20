"""Phase 2 API: complaint import, storage, and dashboard analytics."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(
    title="NeuroOps AI API",
    description="Foundation API for the NeuroOps AI complaint intelligence platform.",
    version="0.1.0",
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

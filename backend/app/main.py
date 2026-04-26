"""
Cyrus — FastAPI Application Entry Point

This is the main file that starts the entire backend API.
FastAPI automatically generates interactive API docs at /docs
"""

from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import create_tables
from app.api import classes, exams, upload, grade, share, export, sync, health, adaptive, answer_keys

log = structlog.get_logger()
settings = get_settings()


# ─────────────────────────────────────────────────────────────────
# Lifespan (startup + shutdown)
# ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code here runs ONCE when the app starts, and once when it stops.
    We use it to:
    - Ensure DB tables exist (development)
    - Pre-warm model cache references
    - Ensure MinIO bucket exists
    """
    log.info("cyrus_starting", environment=settings.environment)

    # In development, auto-create tables (Alembic handles this in production)
    if settings.environment == "development":
        await create_tables()

    # Ensure MinIO bucket exists
    try:
        from app.services.storage import ensure_bucket_exists
        await ensure_bucket_exists()
    except Exception as e:
        log.warning("minio_bucket_init_failed", error=str(e))

    log.info("cyrus_ready", api_docs="http://localhost:8000/docs")

    yield  # ← App runs here

    log.info("cyrus_shutting_down")


# ─────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cyrus",
    description="AI-powered teacher grading & student feedback platform",
    version="0.1.0",
    docs_url="/docs",         # Interactive API explorer
    redoc_url="/redoc",       # Alternative API docs
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─────────────────────────────────────────────────────────────────
# Global Exception Handler
# ─────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Our team has been notified."},
    )


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────
# Each router handles one feature area.
# They are all prefixed with /api/v1/ for versioning.

app.include_router(health.router, tags=["health"])
app.include_router(classes.router,  prefix="/api/v1/classes",  tags=["classes"])
app.include_router(exams.router,    prefix="/api/v1/exams",    tags=["exams"])
app.include_router(upload.router,   prefix="/api/v1/upload",   tags=["upload"])
app.include_router(grade.router,    prefix="/api/v1/grade",    tags=["grading"])
app.include_router(share.router,    prefix="/api/v1/share",    tags=["sharing"])
app.include_router(export.router,   prefix="/api/v1/export",   tags=["export"])
app.include_router(sync.router,     prefix="/api/v1/sync",     tags=["sync"])
app.include_router(adaptive.router, prefix="/api/v1/adaptive", tags=["adaptive"])
app.include_router(answer_keys.router, prefix="/api/v1/answer-keys", tags=["answer-keys"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["feedback"])

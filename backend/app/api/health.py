"""
Cyrus — Health Check Router

Simple endpoints to verify the app is running.
Used by Docker health checks and uptime monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter()


@router.get("/health", summary="Health check")
async def health():
    """Returns OK if the API is running."""
    return {"status": "ok", "service": "cyrus-api"}


@router.get("/health/db", summary="Database health check")
async def health_db(db: AsyncSession = Depends(get_db)):
    """Verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

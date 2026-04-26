"""Cyrus — Sync API (stub — full implementation in Sprint 4)"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/status", summary="Get sync status")
async def sync_status():
    return {"status": "ok", "pending_items": 0}

@router.post("/push", summary="Push offline changes to server")
async def sync_push(body: dict):
    """Receives batched offline changes from the PWA client."""
    return {"status": "not_yet_implemented", "sprint": 4}

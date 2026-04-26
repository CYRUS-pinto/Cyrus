"""Cyrus — Share API (stub — full implementation in Sprint 5)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models.sharing import SharedItem
from app.models.feedback import FeedbackReport
import shortuuid

router = APIRouter()

@router.post("/create", summary="Create a share link for any item")
async def create_share(body: dict, db: AsyncSession = Depends(get_db)):
    token = f"shr_{shortuuid.uuid()}"
    expiry_days = body.get("expiry_days", 7)
    share = SharedItem(
        item_type=body["item_type"],
        item_id=body["item_id"],
        shared_with_email=body.get("email"),
        permission=body.get("permission", "viewer"),
        share_token=token,
        token_expires=datetime.now(timezone.utc) + timedelta(days=expiry_days),
    )
    db.add(share)
    await db.flush()
    return {"token": token, "share_url": f"/share/{token}", "expires_days": expiry_days}

@router.get("/{token}", summary="Resolve a share token")
async def resolve_share(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SharedItem).where(SharedItem.share_token == token, SharedItem.is_active == True))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    if share.token_expires and share.token_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")
    return {"item_type": share.item_type, "item_id": share.item_id, "permission": share.permission}

@router.delete("/{token}", summary="Revoke a share link")
async def revoke_share(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SharedItem).where(SharedItem.share_token == token))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    share.is_active = False
    share.revoked_at = datetime.now(timezone.utc)
    return {"revoked": True}

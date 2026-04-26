"""
Cyrus — OCR Correction + Fine-Tuning API (Sprint 6)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.adaptive import OcrCorrection, FineTuneJob
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/correction", summary="Submit an OCR correction")
async def submit_correction(body: dict, db: AsyncSession = Depends(get_db)):
    """
    Teacher highlights an OCR error and submits the correct text.
    This is the training sample collected for fine-tuning.
    """
    correction = OcrCorrection(
        submission_page_id=body["submission_page_id"],
        wrong_text=body["wrong_text"],
        correct_text=body["correct_text"],
        region_bbox_json=body.get("region_bbox_json"),
        image_crop_url=body.get("image_crop_url"),
        model_source=body.get("model_source"),
    )
    db.add(correction)
    await db.flush()
    return {"id": correction.id, "saved": True}


@router.get("/corrections/stats", summary="Get correction stats and fine-tuning readiness")
async def correction_stats(db: AsyncSession = Depends(get_db)):
    """Shows how many corrections have been collected and whether fine-tuning is available."""
    total_r = await db.execute(select(func.count()).select_from(OcrCorrection))
    total = total_r.scalar() or 0

    unused_r = await db.execute(
        select(func.count()).select_from(OcrCorrection).where(OcrCorrection.used_in_finetune == False)
    )
    unused = unused_r.scalar() or 0

    threshold = settings.ocr_finetune_threshold
    ready = unused >= threshold

    return {
        "total_corrections": total,
        "unused_corrections": unused,
        "threshold": threshold,
        "fine_tuning_available": ready,
        "still_needed": max(0, threshold - unused),
    }


@router.post("/finetune/trigger", summary="Trigger manual LoRA fine-tuning")
async def trigger_finetune(db: AsyncSession = Depends(get_db)):
    """
    Teacher manually triggers fine-tuning when enough corrections are collected.
    Only available when unused_corrections >= threshold.
    """
    # Check readiness
    unused_r = await db.execute(
        select(func.count()).select_from(OcrCorrection).where(OcrCorrection.used_in_finetune == False)
    )
    unused = unused_r.scalar() or 0

    if unused < settings.ocr_finetune_threshold:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough corrections yet. Need {settings.ocr_finetune_threshold}, have {unused}."
        )

    # Create fine-tuning job record
    job = FineTuneJob(
        corrections_used=unused,
        status="pending",
    )
    db.add(job)
    await db.flush()

    # Queue the background fine-tuning task
    try:
        from app.tasks.finetune_tasks import run_lora_finetune
        run_lora_finetune.delay(job.id)
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to queue fine-tuning: {e}")

    return {
        "job_id": job.id,
        "status": "queued",
        "corrections_used": unused,
        "message": f"Fine-tuning queued with {unused} corrections. This will take 1-4 hours.",
    }


@router.get("/finetune/jobs", summary="List all fine-tuning jobs")
async def list_finetune_jobs(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(FineTuneJob).order_by(FineTuneJob.created_at.desc()).limit(20))
    jobs = r.scalars().all()
    return [{
        "id": j.id,
        "status": j.status,
        "corrections_used": j.corrections_used,
        "cer_before": j.cer_before,
        "cer_after": j.cer_after,
        "improvement_percent": j.improvement_percent,
        "created_at": j.created_at,
        "completed_at": j.completed_at,
    } for j in jobs]

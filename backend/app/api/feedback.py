"""
Cyrus — Feedback Report API (Sprint 4)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.feedback import FeedbackReport
import json

router = APIRouter()


@router.get("/{submission_id}", summary="Get feedback report for a submission")
async def get_feedback(submission_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(FeedbackReport).where(FeedbackReport.submission_id == submission_id))
    report = r.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Feedback not yet generated for this submission")
    return {
        "id": report.id,
        "submission_id": submission_id,
        "summary": report.summary_text,
        "study_tips": json.loads(report.study_tips_json) if report.study_tips_json else [],
        "concept_gaps": json.loads(report.concept_gaps_json) if report.concept_gaps_json else [],
        "positive_notes": report.positive_notes,
        "pdf_url": report.pdf_url,
        "share_token": report.share_token,
    }


@router.post("/{submission_id}/generate", summary="Trigger feedback generation")
async def generate_feedback(submission_id: str, db: AsyncSession = Depends(get_db)):
    from app.tasks.grade_tasks import generate_feedback as gen_task
    gen_task.delay(submission_id)
    return {"status": "queued"}

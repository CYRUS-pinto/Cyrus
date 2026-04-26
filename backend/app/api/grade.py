"""Cyrus — Grading API (stub — full implementation in Sprint 3)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.grades import Grade
from app.models.submissions import Submission

router = APIRouter()

@router.get("/submission/{submission_id}", summary="Get all grades for a submission")
async def get_submission_grades(submission_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Grade).where(Grade.submission_id == submission_id))
    grades = result.scalars().all()
    return [{"id": g.id, "question_id": g.question_id, "awarded_marks": g.final_marks,
             "max_marks": g.max_marks, "ai_confidence": g.ai_confidence,
             "flagged": g.flagged_for_review, "teacher_override": g.teacher_override} for g in grades]

@router.post("/submission/{submission_id}/trigger", summary="Trigger AI grading for a submission")
async def trigger_grading(submission_id: str, db: AsyncSession = Depends(get_db)):
    """Queues the AI grading task for this submission."""
    try:
        from app.tasks.grade_tasks import grade_submission
        grade_submission.delay(submission_id)
        return {"status": "queued", "submission_id": submission_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/grade/{grade_id}/override", summary="Teacher overrides an AI grade")
async def override_grade(grade_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone
    result = await db.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    grade.teacher_override = True
    grade.override_marks = body["marks"]
    grade.override_note = body.get("note")
    grade.reviewed_at = datetime.now(timezone.utc)
    return {"id": grade.id, "override_marks": grade.override_marks}

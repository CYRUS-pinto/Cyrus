"""
Cyrus — Answer Key API

Handles upload, OCR, and retrieval of answer keys.
The answer key goes through the same OCR pipeline as student papers,
then is parsed into a structured JSON format per question.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.answer_keys import AnswerKey, AnswerKeyPage
from app.models.exams import Exam, ExamQuestion
import shortuuid
import json

router = APIRouter()


@router.get("/{exam_id}", summary="Get answer key for an exam")
async def get_answer_key(exam_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = r.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="No answer key uploaded for this exam")
    return {
        "id": key.id,
        "exam_id": key.exam_id,
        "ocr_status": key.ocr_status,
        "structured_json": json.loads(key.structured_json) if key.structured_json else None,
        "source_type": key.source_type,
    }


@router.post("/{exam_id}/upload", summary="Upload answer key image/PDF")
async def upload_answer_key_image(
    exam_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload answer key as an image or PDF scan. Queued for OCR processing."""
    from app.services.storage import upload_file

    # Check exam exists
    exam_r = await db.execute(select(Exam).where(Exam.id == exam_id))
    if not exam_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Exam not found")

    file_bytes = await file.read()
    key = f"answer_keys/{exam_id}/page_001{file.filename[file.filename.rfind('.'):]}"
    url = await upload_file(key, file_bytes, file.content_type or "image/jpeg")

    # Create AnswerKey record
    ak = AnswerKey(exam_id=exam_id, source_type="image_upload", ocr_status="pending")
    db.add(ak)
    await db.flush()

    page = AnswerKeyPage(answer_key_id=ak.id, page_number=1, file_url=url, ocr_status="pending")
    db.add(page)
    await db.commit()

    # Queue OCR
    try:
        from app.tasks.ocr_tasks import process_page
        process_page.delay(page.id, is_cover_page=False)
    except Exception:
        pass

    return {"answer_key_id": ak.id, "page_id": page.id, "url": url, "status": "queued_for_ocr"}


@router.post("/{exam_id}/text", summary="Upload answer key as structured text")
async def upload_answer_key_text(exam_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """
    Upload answer key as JSON structure.
    Format: {"questions": [{"num": "1", "answer_text": "...", "marks": 2}]}
    """
    # Delete existing key
    existing_r = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    existing = existing_r.scalar_one_or_none()
    if existing:
        await db.delete(existing)

    ak = AnswerKey(
        exam_id=exam_id,
        source_type="text_input",
        ocr_status="done",
        structured_json=json.dumps(body),
    )
    db.add(ak)
    await db.flush()
    await db.commit()
    return {"answer_key_id": ak.id, "questions": len(body.get("questions", []))}

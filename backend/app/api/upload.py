"""
Cyrus — Upload API Router

Handles QR session creation, student grouping, file uploads.
This is the core of Sprint 1 — fully scaffolded here with real
storage logic started.
"""

import uuid
import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import get_db
from app.models.sessions import UploadSession
from app.models.submissions import Submission, SubmissionPage
from app.models.exams import Exam
from app.config import get_settings
import shortuuid

router = APIRouter()
settings = get_settings()


@router.post("/session", summary="Create a new upload session (generates QR code)")
async def create_session(body: dict, db: AsyncSession = Depends(get_db)):
    """
    Teacher creates a session before photographing papers.
    Returns a QR token that encodes the phone's upload URL.
    """
    exam_id = body.get("exam_id")
    if not exam_id:
        raise HTTPException(status_code=400, detail="exam_id is required")

    # Verify exam exists
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Generate unique QR token
    token = f"sess_{shortuuid.uuid()}"

    session = UploadSession(
        exam_id=exam_id,
        qr_token=token,
        status="open",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db.add(session)
    await db.flush()

    return {
        "session_id": session.id,
        "qr_token": token,
        # The phone opens this URL after scanning the QR code
        "mobile_url": f"{settings.next_public_api_url}/session/{token}",
        "expires_at": session.expires_at,
    }


@router.get("/session/{token}", summary="Get session info (called by phone after QR scan)")
async def get_session(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UploadSession).where(UploadSession.qr_token == token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "closed":
        raise HTTPException(status_code=410, detail="Session is closed")

    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "student_count": session.student_count,
    }


@router.post("/session/{token}/new-student", summary="Start a new student group (+ button)")
async def new_student_group(
    token: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Teacher presses [+ New Student] on their phone.
    Creates a new Submission record.
    Teacher can optionally type the student's name here;
    if blank, it defaults to auto-detection from the first page OCR.
    """
    result = await db.execute(select(UploadSession).where(UploadSession.qr_token == token))
    session = result.scalar_one_or_none()
    if not session or session.status != "open":
        raise HTTPException(status_code=404, detail="Session not found or closed")

    # If teacher typed a name, use it; otherwise we fall back to OCR or Student_001 style
    typed_name = body.get("student_name", "").strip()
    if typed_name:
        name_source = "manual"
        student_name = typed_name
    else:
        # Increment fallback counter for this session
        await db.execute(
            update(UploadSession)
            .where(UploadSession.id == session.id)
            .values(fallback_counter=UploadSession.fallback_counter + 1, student_count=UploadSession.student_count + 1)
        )
        await db.refresh(session)
        name_source = "fallback"
        student_name = f"Student_{session.fallback_counter:03d}"

    # Create the submission record (student_id will be filled after OCR name detection)
    submission = Submission(
        exam_id=session.exam_id,
        session_id=session.id,
        student_id=None,   # filled in after cover page OCR
        status="uploading",
    )
    db.add(submission)
    await db.flush()

    return {
        "submission_id": submission.id,
        "initial_name": student_name,
        "name_source": name_source,
    }


@router.post("/session/{token}/upload-page", summary="Upload one photo page")
async def upload_page(
    token: str,
    submission_id: str = Form(...),
    page_number: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Phone uploads one photo. Stored in MinIO immediately.
    A background OCR task is queued after upload.
    """
    # Validate session
    result = await db.execute(select(UploadSession).where(UploadSession.qr_token == token))
    session = result.scalar_one_or_none()
    if not session or session.status != "open":
        raise HTTPException(status_code=404, detail="Session not found or closed")

    # Validate submission belongs to this session
    sub_result = await db.execute(
        select(Submission).where(Submission.id == submission_id, Submission.session_id == session.id)
    )
    submission = sub_result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found in this session")

    # Read file contents
    contents = await file.read()
    file_size = len(contents)
    extension = file.filename.split(".")[-1].lower() if file.filename else "jpg"

    # Build storage path: submissions/{exam_id}/{submission_id}/page_{N}.{ext}
    storage_key = f"submissions/{session.exam_id}/{submission_id}/page_{page_number:03d}.{extension}"

    # Store in MinIO
    try:
        from app.services.storage import upload_file
        file_url = await upload_file(key=storage_key, data=contents, content_type=file.content_type or "image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    # Create page record
    is_cover = (page_number == 1)
    page = SubmissionPage(
        submission_id=submission_id,
        page_number=page_number,
        file_url=file_url,
        file_size_bytes=file_size,
        original_filename=file.filename,
        is_cover_page=is_cover,
        ocr_status="pending",
    )
    db.add(page)

    # Update submission page count
    await db.execute(
        update(Submission)
        .where(Submission.id == submission_id)
        .values(page_count=Submission.page_count + 1)
    )

    await db.flush()

    # Queue OCR task (runs in background via Celery)
    try:
        from app.tasks.ocr_tasks import process_page
        process_page.delay(page.id, is_cover_page=is_cover, submission_id=submission_id)
    except Exception:
        pass  # Don't fail the upload if queue is unavailable — re-process later

    return {
        "page_id": page.id,
        "page_number": page_number,
        "file_url": file_url,
        "ocr_status": "pending",
        "is_cover_page": is_cover,
    }


@router.post("/session/{token}/close", summary="Close an upload session")
async def close_session(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UploadSession).where(UploadSession.qr_token == token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    return {"status": "closed", "student_count": session.student_count}

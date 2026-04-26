"""
Cyrus — OCR Background Tasks (Celery)

These tasks run in the background after a page is uploaded.
They implement the 3-strike self-correction loop:
  - Run OCR
  - If confidence < threshold, retry with different settings (up to 3 times)
  - On 4th failure, mark page as flagged for teacher review
"""

import structlog
from celery import Task
from celery_worker import celery_app
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


class OcrTask(Task):
    """
    Base class for OCR tasks.
    Loads models once and keeps them in memory across tasks (not reloaded per task).
    """
    _pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            # Import lazily — only when the first OCR task runs
            # This avoids loading 3+ GB of models at worker startup
            from ocr.pipeline import OcrPipeline
            self._pipeline = OcrPipeline()
        return self._pipeline


@celery_app.task(
    bind=True,
    base=OcrTask,
    queue="ocr",
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.ocr_tasks.process_page",
)
def process_page(self, page_id: str, is_cover_page: bool = False, submission_id: str = None):
    """
    Process one uploaded page through the full OCR pipeline.

    Stages:
    1. Download raw image from storage
    2. Pre-process (deskew, denoise, binarize)
    3. Red ink separation (remove teacher annotations)
    4. Layout detection (Surya — identify text/math/diagram regions)
    5. Cover page extraction (if is_cover_page=True)
    6. OCR ensemble (TrOCR + OlmOCR + PaddleOCR voting)
    7. Math OCR (GOT-OCR 2.0 for math regions)
    8. Crossed-out text removal
    9. Post-processing (LanguageTool + Mistral recovery)
    10. Store results back in DB

    3-strike rule: if confidence < threshold, retry up to 3 times
    with enhanced pre-processing before flagging for teacher review.
    """
    attempt = self.request.retries + 1
    log.info("ocr_task_started", page_id=page_id, attempt=attempt)

    try:
        import asyncio
        asyncio.run(_process_page_async(page_id, is_cover_page, submission_id, attempt))
        log.info("ocr_task_complete", page_id=page_id)

    except Exception as exc:
        log.error("ocr_task_failed", page_id=page_id, attempt=attempt, error=str(exc))
        if attempt <= 3:
            # 3-strike rule: retry automatically
            log.info("ocr_task_retrying", page_id=page_id, next_attempt=attempt + 1)
            raise self.retry(exc=exc, countdown=15 * attempt)
        else:
            # 4th failure — flag for teacher review
            log.error("ocr_task_flagged", page_id=page_id, reason="exceeded_max_retries")
            asyncio.run(_flag_page_for_review(page_id, str(exc)))


async def _process_page_async(page_id: str, is_cover_page: bool, submission_id: str, attempt: int):
    """
    Async implementation of page processing.
    Runs inside an event loop created by asyncio.run().
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.database import AsyncSessionLocal
    from app.models.submissions import SubmissionPage, Submission
    from sqlalchemy import select, update
    import json

    async with AsyncSessionLocal() as db:
        # Load the page record
        result = await db.execute(select(SubmissionPage).where(SubmissionPage.id == page_id))
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError(f"SubmissionPage {page_id} not found")

        # Mark as running
        page.ocr_status = "running"
        await db.commit()

        # Download image from storage
        from app.services.storage import download_file, upload_file, key_from_url
        raw_bytes = await download_file(key_from_url(page.file_url))

        # -- STAGE 1: Pre-process --
        from ocr.preprocessor import preprocess_image
        clean_image = preprocess_image(raw_bytes, enhanced=(attempt > 1))

        # Store pre-processed version
        clean_key = page.file_url.replace(".", "_clean.")
        clean_url = await upload_file(clean_key, clean_image, "image/jpeg")

        # -- STAGE 2: Red ink separation --
        from ocr.color_separator import separate_red_ink
        student_image, teacher_marks_image = separate_red_ink(clean_image)

        # -- STAGE 3: Cover page extraction --
        cover_data = {}
        if is_cover_page:
            from ocr.cover_extractor import extract_cover_fields
            cover_data = extract_cover_fields(student_image)

        # -- STAGE 4: Layout detection --
        from ocr.layout_detector import detect_layout
        regions = detect_layout(student_image)

        # -- STAGE 5: OCR ensemble + crossed-out removal --
        from ocr.pipeline import OcrPipeline
        pipeline = OcrPipeline()
        ocr_result = pipeline.run(student_image, regions)

        # -- STAGE 6: Save results --
        page.preprocessed_url = clean_url
        page.ocr_text = ocr_result.full_text
        page.ocr_text_student_only = ocr_result.student_text_only
        page.ocr_confidence = ocr_result.confidence
        page.ocr_winning_model = ocr_result.winning_model
        page.layout_json = json.dumps([r.to_dict() for r in regions])
        page.ocr_status = "flagged" if ocr_result.confidence < settings.ocr_confidence_threshold else "done"

        await db.commit()

        # -- STAGE 7: Update submission status --
        if submission_id:
            sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
            sub = sub_result.scalar_one_or_none()
            if sub and sub.status == "uploading":
                sub.status = "ocr_pending"

        # -- STAGE 8: Auto-set student name from cover --
        if is_cover_page and cover_data.get("name"):
            await _update_student_name(db, submission_id, cover_data)

        await db.commit()


async def _flag_page_for_review(page_id: str, error: str):
    """Mark a page as failed and needing teacher review."""
    from app.database import AsyncSessionLocal
    from app.models.submissions import SubmissionPage
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SubmissionPage).where(SubmissionPage.id == page_id))
        page = result.scalar_one_or_none()
        if page:
            page.ocr_status = "failed"
        await db.commit()


async def _update_student_name(db, submission_id: str, cover_data: dict):
    """
    After cover page OCR, update the student's name in the DB
    if auto-detection found a name.
    """
    import re
    from app.models.submissions import Submission
    from app.models.classes import Student
    from sqlalchemy import select

    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub or not sub.student_id:
        return

    name = cover_data.get("name", "").strip()
    if name:
        stu_result = await db.execute(select(Student).where(Student.id == sub.student_id))
        student = stu_result.scalar_one_or_none()
        if student and student.name_source == "fallback":
            student.name = name
            student.name_slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            student.name_source = "ocr"
            if cover_data.get("registration_number"):
                student.registration_number = cover_data["registration_number"]


@celery_app.task(queue="ocr", name="app.tasks.ocr_tasks.process_submission")
def process_submission(submission_id: str):
    """
    Trigger OCR for all pages of a submission (used for batch reprocessing).
    """
    import asyncio
    asyncio.run(_queue_all_pages(submission_id))


async def _queue_all_pages(submission_id: str):
    from app.database import AsyncSessionLocal
    from app.models.submissions import Submission, SubmissionPage
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        pages_result = await db.execute(
            select(SubmissionPage).where(SubmissionPage.submission_id == submission_id).order_by(SubmissionPage.page_number)
        )
        pages = pages_result.scalars().all()
        for page in pages:
            process_page.delay(page.id, is_cover_page=page.is_cover_page, submission_id=submission_id)

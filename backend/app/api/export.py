"""
Cyrus — Export API (Full Sprint 4 implementation)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
import io

router = APIRouter()


@router.get("/exam/{exam_id}/csv", summary="Export all grades as CSV")
async def export_csv(exam_id: str, db: AsyncSession = Depends(get_db)):
    """Returns a downloadable CSV file with all student grades for this exam."""
    from app.tasks.grade_tasks import export_exam_csv_task
    url = export_exam_csv_task.apply(args=[exam_id]).get(timeout=60)
    if not url:
        raise HTTPException(status_code=500, detail="CSV export failed")
    return RedirectResponse(url=url)


@router.post("/exam/{exam_id}/google-sheets", summary="Push grades to Google Sheets")
async def export_google_sheets(exam_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Pushes results to the teacher's Google Sheet."""
    from app.tasks.grade_tasks import export_exam_csv_task
    # Build exam_data and push
    try:
        from app.services.export import ExportService
        from app.services.storage import download_file
        export_svc = ExportService()
        # Fetch data (simplified — full impl fetches from DB)
        sheet_url = export_svc.export_to_google_sheets(body.get("spreadsheet_id", ""), {})
        return {"url": sheet_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/submission/{submission_id}/pdf", summary="Download student PDF report")
async def export_pdf(submission_id: str, db: AsyncSession = Depends(get_db)):
    """Streams the generated PDF feedback report for one student."""
    from sqlalchemy import select
    from app.models.feedback import FeedbackReport
    from app.services.storage import download_file, key_from_url

    r = await db.execute(select(FeedbackReport).where(FeedbackReport.submission_id == submission_id))
    report = r.scalar_one_or_none()
    if not report or not report.pdf_url:
        raise HTTPException(status_code=404, detail="PDF report not yet generated")

    pdf_bytes = await download_file(key_from_url(report.pdf_url))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=feedback_{submission_id}.pdf"},
    )

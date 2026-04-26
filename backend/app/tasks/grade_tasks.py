"""
Cyrus — Full Grading + Feedback + Export Celery Tasks (Sprint 3/4)
"""

import json
import asyncio
import structlog
from datetime import datetime, timezone
from celery_worker import celery_app
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


@celery_app.task(bind=True, queue="grading", max_retries=3, name="app.tasks.grade_tasks.grade_submission")
def grade_submission(self, submission_id: str):
    """
    Grade all questions for one student submission.
    Runs after all pages have been OCR'd.
    """
    try:
        asyncio.run(_grade_async(submission_id))
    except Exception as exc:
        log.error("grade_submission_failed", submission_id=submission_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


async def _grade_async(submission_id: str):
    from app.database import AsyncSessionLocal
    from app.models.submissions import Submission, SubmissionPage
    from app.models.exams import Exam, ExamQuestion
    from app.models.answer_keys import AnswerKey
    from app.models.grades import Grade
    from app.services.grading import GradingService
    from sqlalchemy import select
    import re

    grader = GradingService()

    async with AsyncSessionLocal() as db:
        # Load submission
        sub_r = await db.execute(select(Submission).where(Submission.id == submission_id))
        sub = sub_r.scalar_one_or_none()
        if not sub:
            raise ValueError(f"Submission {submission_id} not found")

        sub.status = "grading"
        await db.commit()

        # Load all OCR'd pages for this submission
        pages_r = await db.execute(
            select(SubmissionPage).where(SubmissionPage.submission_id == submission_id,
                                         SubmissionPage.ocr_status == "done")
            .order_by(SubmissionPage.page_number)
        )
        pages = pages_r.scalars().all()
        full_student_text = "\n".join(p.ocr_text_student_only or p.ocr_text or "" for p in pages)

        # Load exam questions
        exam_r = await db.execute(select(Exam).where(Exam.id == sub.exam_id))
        exam = exam_r.scalar_one_or_none()

        questions_r = await db.execute(
            select(ExamQuestion).where(ExamQuestion.exam_id == sub.exam_id)
            .order_by(ExamQuestion.order_index)
        )
        questions = questions_r.scalars().all()

        # Load answer key
        ak_r = await db.execute(
            select(AnswerKey).where(AnswerKey.exam_id == sub.exam_id, AnswerKey.ocr_status == "done")
        )
        answer_key = ak_r.scalar_one_or_none()
        if not answer_key or not answer_key.structured_json:
            log.warning("no_answer_key", exam_id=sub.exam_id)
            sub.status = "needs_review"
            await db.commit()
            return

        key_data = json.loads(answer_key.structured_json)
        key_by_question = {q["num"]: q for q in key_data.get("questions", [])}

        total_awarded = 0.0

        for question in questions:
            key_entry = key_by_question.get(question.question_num, {})
            answer_key_text = key_entry.get("answer_text", "")

            # Extract student text for this question using regex
            student_answer = _extract_question_text(full_student_text, question.question_num)

            # Grade it
            result = grader.grade_question(
                student_text=student_answer,
                answer_key_text=answer_key_text,
                max_marks=float(question.max_marks),
                content_type=question.content_type,
                rubric=json.loads(question.rubric_json) if question.rubric_json else None,
            )

            # Save grade record
            grade = Grade(
                submission_id=submission_id,
                question_id=question.id,
                max_marks=result.max_marks,
                awarded_marks=result.awarded_marks,
                ai_confidence=result.ai_confidence,
                ai_feedback=result.ai_feedback,
                ai_reasoning=result.ai_reasoning,
                grading_method=result.grading_method,
                flagged_for_review=result.flagged_for_review,
                flag_reason=result.flag_reason,
            )
            db.add(grade)
            total_awarded += result.awarded_marks

        # Update submission total
        sub.total_marks = total_awarded
        sub.status = "completed"
        await db.commit()

        log.info("grading_complete", submission_id=submission_id, total=total_awarded)

        # Queue feedback generation
        generate_feedback.delay(submission_id)


def _extract_question_text(full_text: str, question_num: str) -> str:
    """
    Extract the student's answer for a specific question number from full OCR text.
    Uses regex to find "Q8", "8.", "8)" etc. and extract to next question.
    """
    import re
    pattern = rf"(?:Q|Question\s*)?{re.escape(question_num)}[\.)\s]+"
    matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
    if not matches:
        return ""
    start = matches[0].end()
    # Find the next question marker
    next_match = re.search(r"\n\s*(?:Q|Question\s*)?\d+[\.)\s]+", full_text[start:])
    end = start + next_match.start() if next_match else len(full_text)
    return full_text[start:end].strip()


@celery_app.task(bind=True, queue="feedback", max_retries=2, name="app.tasks.grade_tasks.generate_feedback")
def generate_feedback(self, submission_id: str):
    """Generate AI feedback report after grading is complete."""
    try:
        asyncio.run(_feedback_async(submission_id))
    except Exception as exc:
        log.error("feedback_failed", submission_id=submission_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _feedback_async(submission_id: str):
    from app.database import AsyncSessionLocal
    from app.models.submissions import Submission
    from app.models.grades import Grade
    from app.models.exams import Exam, ExamQuestion
    from app.models.classes import Student
    from app.models.feedback import FeedbackReport
    from app.services.feedback import FeedbackService
    from app.services.export import ExportService
    from app.services.storage import upload_file
    from sqlalchemy import select
    import shortuuid

    fb_service = FeedbackService()
    export_service = ExportService()

    async with AsyncSessionLocal() as db:
        sub_r = await db.execute(select(Submission).where(Submission.id == submission_id))
        sub = sub_r.scalar_one_or_none()
        if not sub:
            return

        # Load grades
        grades_r = await db.execute(
            select(Grade, ExamQuestion)
            .join(ExamQuestion, Grade.question_id == ExamQuestion.id)
            .where(Grade.submission_id == submission_id)
        )
        grade_rows = grades_r.all()

        # Load student name
        student_name = "Student"
        if sub.student_id:
            st_r = await db.execute(select(Student).where(Student.id == sub.student_id))
            st = st_r.scalar_one_or_none()
            if st:
                student_name = st.name

        # Load exam
        exam_r = await db.execute(select(Exam).where(Exam.id == sub.exam_id))
        exam = exam_r.scalar_one_or_none()

        grade_breakdown = [
            {
                "question": f"{q.part}-Q{q.question_num}" if q.part else f"Q{q.question_num}",
                "awarded": float(g.final_marks or 0),
                "max": float(g.max_marks),
                "feedback": g.ai_feedback or "",
            }
            for g, q in grade_rows
        ]

        # Generate feedback text
        result = fb_service.generate(
            student_name=student_name,
            exam_name=exam.name if exam else "Exam",
            total_marks=float(sub.total_marks or 0),
            max_marks=float(exam.total_marks) if exam else 0,
            grade_breakdown=grade_breakdown,
        )

        # Generate PDF
        report_data = {
            "student_name": student_name,
            "exam_name": exam.name if exam else "Exam",
            "total_marks": float(sub.total_marks or 0),
            "max_marks": float(exam.total_marks) if exam else 0,
            "summary": result.summary,
            "positive_notes": result.positive_notes,
            "study_tips": result.study_tips,
            "concept_gaps": result.concept_gaps,
            "grades": grade_breakdown,
        }
        pdf_bytes = export_service.generate_student_pdf(report_data)
        pdf_key = f"reports/{sub.exam_id}/{submission_id}/report.pdf"
        pdf_url = await upload_file(pdf_key, pdf_bytes, "application/pdf")

        # Create FeedbackReport record
        share_token = f"rep_{shortuuid.uuid()}"
        fr = FeedbackReport(
            submission_id=submission_id,
            summary_text=result.summary,
            study_tips_json=json.dumps(result.study_tips),
            concept_gaps_json=json.dumps(result.concept_gaps),
            positive_notes=result.positive_notes,
            pdf_url=pdf_url,
            share_token=share_token,
        )
        db.add(fr)
        await db.commit()

        log.info("feedback_complete", submission_id=submission_id, token=share_token)


@celery_app.task(bind=True, queue="export", name="app.tasks.grade_tasks.export_exam_csv")
def export_exam_csv_task(self, exam_id: str) -> str:
    """Export full exam results as CSV and return the download URL."""
    return asyncio.run(_export_csv_async(exam_id))


async def _export_csv_async(exam_id: str) -> str:
    from app.database import AsyncSessionLocal
    from app.models.exams import Exam, ExamQuestion
    from app.models.submissions import Submission
    from app.models.grades import Grade
    from app.models.classes import Student
    from app.services.export import ExportService
    from app.services.storage import upload_file
    from sqlalchemy import select

    export_service = ExportService()

    async with AsyncSessionLocal() as db:
        exam_r = await db.execute(select(Exam).where(Exam.id == exam_id))
        exam = exam_r.scalar_one_or_none()

        subs_r = await db.execute(select(Submission).where(Submission.exam_id == exam_id))
        subs = subs_r.scalars().all()

        students_data = []
        for sub in subs:
            name = "Unknown"
            reg_no = ""
            if sub.student_id:
                st_r = await db.execute(select(Student).where(Student.id == sub.student_id))
                st = st_r.scalar_one_or_none()
                if st:
                    name = st.name
                    reg_no = st.registration_number or ""

            grades_r = await db.execute(
                select(Grade, ExamQuestion)
                .join(ExamQuestion, Grade.question_id == ExamQuestion.id)
                .where(Grade.submission_id == sub.id)
                .order_by(ExamQuestion.order_index)
            )
            grade_rows = grades_r.all()

            students_data.append({
                "name": name,
                "reg_no": reg_no,
                "total_marks": float(sub.total_marks or 0),
                "grades": [{"question": f"Q{q.question_num}", "marks": float(g.final_marks or 0)} for g, q in grade_rows],
            })

        exam_data = {
            "exam_name": exam.name if exam else "Exam",
            "max_marks": float(exam.total_marks) if exam else 0,
            "students": students_data,
        }

        csv_bytes = export_service.export_exam_csv(exam_data)
        key = f"exports/{exam_id}/grades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        url = await upload_file(key, csv_bytes, "text/csv")
        return url

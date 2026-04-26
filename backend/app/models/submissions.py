"""
Cyrus — Submissions & Submission Pages Models

A Submission is one student's answer booklet for one exam.
It groups all their pages (1–16 photos) together.

SubmissionPage is one individual photo — one physical page.
All OCR results, pre-processed images, and confidence scores live here.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"))
    student_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_sessions.id", ondelete="CASCADE"))

    # Total pages uploaded for this student
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    # Processing lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="uploading",
        doc="uploading | ocr_pending | ocr_running | grading | completed | needs_review | failed"
    )

    # Final grade (sum of all question marks)
    total_marks: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Whether teacher has reviewed and approved this submission's grades
    teacher_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="submissions")  # type: ignore[name-defined]
    session: Mapped["UploadSession"] = relationship("UploadSession", back_populates="submissions")  # type: ignore[name-defined]
    pages: Mapped[list["SubmissionPage"]] = relationship(
        "SubmissionPage", back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionPage.page_number"
    )
    grades: Mapped[list] = relationship("Grade", back_populates="submission", cascade="all, delete-orphan")
    feedback_report: Mapped["FeedbackReport | None"] = relationship("FeedbackReport", back_populates="submission", uselist=False)  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Submission student={self.student_id!r} status={self.status!r}>"


class SubmissionPage(Base):
    """
    One photo = one page.
    This is where all the OCR pipeline results are stored.
    The storage path follows: submissions/{exam_id}/{student_slug}/page_{N}.jpg
    """
    __tablename__ = "submission_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submissions.id", ondelete="CASCADE"))
    page_number: Mapped[int] = mapped_column(Integer, default=1)

    # Original uploaded file (as stored in MinIO/Supabase)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pre-processed version (after OpenCV deskew, denoise, binarize)
    preprocessed_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OCR output — combined across all models
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text_student_only: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ^ student-only = after red ink (teacher marks) have been removed

    # OCR confidence (0.0 → 1.0). Below threshold → flagged for teacher review.
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Which OCR model "won" the ensemble vote for this page
    ocr_winning_model: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Detailed layout as JSON: list of detected regions with bounding boxes and type
    # e.g. [{"type": "text", "bbox": [x,y,w,h], "ocr_text": "...", "confidence": 0.89}, ...]
    layout_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing status
    ocr_status: Mapped[str] = mapped_column(
        String(20), default="pending",
        doc="pending | running | done | failed | flagged"
    )

    # Is this the cover page? (for name/reg extraction)
    is_cover_page: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="pages")
    ocr_corrections: Mapped[list] = relationship("OcrCorrection", back_populates="submission_page")

    def __repr__(self) -> str:
        return f"<SubmissionPage #{self.page_number} status={self.ocr_status!r}>"

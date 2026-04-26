"""
Cyrus — Answer Keys Models

The AnswerKey is the teacher's model answer.
It can be uploaded as images, typed as text, or provided as PDF.
Each page of the answer key is stored separately (same pattern as student submissions).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"))

    # How the answer key was provided
    input_type: Mapped[str] = mapped_column(
        String(20), default="image",
        doc="image | text | pdf | mixed"
    )

    # After OCR, the structured extraction is stored as JSON
    # Format: {"questions": [{"num": "1", "part": "A", "answer_text": "...", "diagram_url": null}]}
    structured_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Can this answer key be shared as a template?
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    template_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OCR processing status
    ocr_status: Mapped[str] = mapped_column(
        String(20), default="pending",
        doc="pending | processing | done | failed"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="answer_keys")  # type: ignore[name-defined]
    pages: Mapped[list["AnswerKeyPage"]] = relationship(
        "AnswerKeyPage", back_populates="answer_key",
        cascade="all, delete-orphan",
        order_by="AnswerKeyPage.page_number"
    )

    def __repr__(self) -> str:
        return f"<AnswerKey exam={self.exam_id!r} type={self.input_type!r}>"


class AnswerKeyPage(Base):
    """
    One page of the answer key.
    Mirrors the structure of SubmissionPage for consistent pipeline handling.
    """
    __tablename__ = "answer_key_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_key_id: Mapped[str] = mapped_column(String(36), ForeignKey("answer_keys.id", ondelete="CASCADE"))
    page_number: Mapped[int] = mapped_column(default=1)

    # Storage URL (MinIO or Supabase)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)

    # After pre-processing (OpenCV cleaned version)
    preprocessed_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OCR output
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    ocr_status: Mapped[str] = mapped_column(String(20), default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    answer_key: Mapped["AnswerKey"] = relationship("AnswerKey", back_populates="pages")

    def __repr__(self) -> str:
        return f"<AnswerKeyPage #{self.page_number} key={self.answer_key_id!r}>"

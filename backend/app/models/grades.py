"""
Cyrus — Grades Model

One Grade record = one student's answer to one question.
Stores both the AI grading result and any teacher override.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submissions.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("exam_questions.id", ondelete="CASCADE"))

    # ── AI grading result ──────────────────────────────────────
    max_marks: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    awarded_marks: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Confidence score from the AI (0.0 → 1.0)
    # Below settings.OCR_CONFIDENCE_THRESHOLD → flagged for mandatory teacher review
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Short feedback summary (what was right/wrong)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Longer reasoning (for teacher's reference — not shown to student)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which grading method was used
    grading_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="semantic | llm | sympy | llava | manual"
    )

    # ── Teacher override ───────────────────────────────────────
    teacher_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_marks: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Flag for review ────────────────────────────────────────
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="grades")  # type: ignore[name-defined]
    question: Mapped["ExamQuestion"] = relationship("ExamQuestion", back_populates="grades")  # type: ignore[name-defined]

    @property
    def final_marks(self) -> float | None:
        """Returns teacher override if set, otherwise AI-awarded marks."""
        if self.teacher_override and self.override_marks is not None:
            return float(self.override_marks)
        return float(self.awarded_marks) if self.awarded_marks is not None else None

    def __repr__(self) -> str:
        return f"<Grade Q={self.question_id!r} marks={self.final_marks}/{self.max_marks}>"

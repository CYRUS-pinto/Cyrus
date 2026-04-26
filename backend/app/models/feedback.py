"""
Cyrus — Feedback Reports Model

After grading is complete, a second AI pass generates a complete
personalized feedback report for each student. This is separate from
the Grade records — grading assigns marks, feedback teaches.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # One feedback report per submission (unique constraint enforced by the relationship)
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submissions.id", ondelete="CASCADE"), unique=True)

    # Overall summary (1–2 sentences, shown at top of student report)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON array of study tips
    # Format: [{"topic": "Cellular Respiration", "tip": "Review Chapter 4.3", "chapter_ref": "4.3"}]
    study_tips_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON array of identified concept gaps
    # Format: [{"concept": "Electron Transport Chain", "severity": "major"}]
    concept_gaps_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Positive encouragement note (what the student did well overall)
    positive_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generated PDF stored in object storage
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Student access (no-login link) ─────────────────────────
    # A unique token for the student to access their report
    # URL: /results/{share_token}
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    share_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    share_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Teacher has approved this report to be shared
    released_to_student: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="feedback_report")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<FeedbackReport submission={self.submission_id!r} released={self.released_to_student}>"

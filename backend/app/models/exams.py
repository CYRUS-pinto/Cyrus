"""
Cyrus — Exams & Exam Questions Models

An Exam belongs to a Subject.
Each Exam has Questions with mark allocations (the rubric).
Parts A/B/C from the Indian university format map to content_type.
"""

import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Text, Numeric, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(255), nullable=False)   # "Mid-Term May 2026 — IA 1"
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_marks: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    # Status lifecycle: draft → active → grading → completed
    status: Mapped[str] = mapped_column(
        String(20), default="draft",
        doc="draft | active | grading | completed"
    )

    # Instructions shown to teacher during review
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    subject: Mapped["Subject"] = relationship("Subject", back_populates="exams")  # type: ignore[name-defined]
    questions: Mapped[list["ExamQuestion"]] = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.order_index")
    answer_keys: Mapped[list] = relationship("AnswerKey", back_populates="exam", cascade="all, delete-orphan")
    upload_sessions: Mapped[list] = relationship("UploadSession", back_populates="exam")

    def __repr__(self) -> str:
        return f"<Exam {self.name!r} status={self.status!r}>"


class ExamQuestion(Base):
    """
    Represents one question (or sub-question) in an exam.

    Indian university answer booklet example:
    - Part A, Q1, Q2 ... Q7 (MCQ, 2 marks each)
    - Part B, Q8, Q9 (short answer, 6 marks each)
    - Part C, Q10 (long answer, 10 marks)

    We store these as:
    question_num = "1b", "2b", "8", "10"
    part = "A", "B", "C"
    content_type = "mcq", "text", "text", "text"
    """
    __tablename__ = "exam_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"))

    question_num: Mapped[str] = mapped_column(String(20), nullable=False)  # "1", "2a", "Q10"
    part: Mapped[str | None] = mapped_column(String(5), nullable=True)     # "A", "B", "C"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)   # question text if known

    max_marks: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    order_index: Mapped[int] = mapped_column(default=0)  # for display ordering

    # What kind of answer is expected?
    content_type: Mapped[str] = mapped_column(
        String(20), default="text",
        doc="text | diagram | math | mcq | derivation | mixed"
    )

    # Rubric — optional structured marking criteria
    # e.g. {"criteria": [{"description": "identifies ATP", "marks": 3}, ...]}
    rubric_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # stored as JSON string

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="questions")
    grades: Mapped[list] = relationship("Grade", back_populates="question")

    def __repr__(self) -> str:
        return f"<ExamQuestion Q{self.question_num} {self.max_marks}marks>"

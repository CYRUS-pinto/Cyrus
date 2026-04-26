"""
Cyrus — Classes, Students, Subjects Models

These three tables are the organizational backbone:
- Class (e.g., "Grade 10 - Section A - 2026")
  - contains → Subjects (e.g., "Biology", "Mathematics")
    - contains → Exams (defined in exams.py)
  - contains → Students (e.g., "Ahmed Hassan")
    - has → Submissions (one per exam, in submissions.py)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # e.g. "Grade 10 - Section A - 2026"
    year: Mapped[str | None] = mapped_column(String(10), nullable=True)
    section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    students: Mapped[list["Student"]] = relationship("Student", back_populates="class_", cascade="all, delete-orphan")
    subjects: Mapped[list["Subject"]] = relationship("Subject", back_populates="class_", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Class {self.name!r}>"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id", ondelete="CASCADE"))

    # Name — auto-detected from OCR of cover page, or typed by teacher
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Normalized slug for storage paths (e.g., "ahmed_hassan")
    name_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    # Registration number extracted from the answer booklet cover
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Program / semester from cover page
    program: Mapped[str | None] = mapped_column(String(100), nullable=True)
    semester: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Fallback tracking: was this name auto-detected (OCR) or manually typed?
    name_source: Mapped[str] = mapped_column(String(20), default="manual")
    # "ocr" | "manual" | "fallback" (Student_001 style)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    class_: Mapped["Class"] = relationship("Class", back_populates="students")
    submissions: Mapped[list] = relationship("Submission", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Student {self.name!r} reg={self.registration_number!r}>"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # "Biology", "Mathematics"
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "25ENUMH1GH"
    faculty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    class_: Mapped["Class"] = relationship("Class", back_populates="subjects")
    exams: Mapped[list] = relationship("Exam", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Subject {self.name!r}>"

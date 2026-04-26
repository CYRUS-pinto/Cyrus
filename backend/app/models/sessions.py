"""
Cyrus — Upload Sessions Model

An UploadSession is created when a teacher starts photographing student papers.
It has a unique QR token that the teacher scans on their phone to connect.
All submissions uploaded during a session are linked to this record.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"))

    # The unique token embedded in the QR code
    # Format: "sess_<shortuuid>" — unique, URL-safe
    qr_token: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Session status lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="open",
        doc="open | processing | closed"
    )

    # How many student groups have been created in this session
    student_count: Mapped[int] = mapped_column(default=0)

    # Fallback name counter (Student_001, Student_002, etc.)
    fallback_counter: Mapped[int] = mapped_column(default=0)

    # Session automatically closes after this time
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="upload_sessions")  # type: ignore[name-defined]
    submissions: Mapped[list] = relationship("Submission", back_populates="session")

    def __repr__(self) -> str:
        return f"<UploadSession token={self.qr_token!r} status={self.status!r}>"

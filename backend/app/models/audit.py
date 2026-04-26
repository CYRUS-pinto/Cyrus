"""
Cyrus — Audit Log Model

Every significant action is logged here with a timestamp.
This is used for debugging, accountability, and the admin view.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # What happened
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "share_template", "grade_override", "session_created", "finetune_triggered"

    # What type of item was affected
    item_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. "submission", "exam", "grade", "shared_item"

    # The ID of the affected item
    item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Extra context as JSON — varies by action type
    # e.g. {"old_marks": 6, "new_marks": 8, "question": "Q3"}
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # IP address if available (for detecting unusual access patterns)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action!r} item={self.item_type!r}:{self.item_id!r}>"

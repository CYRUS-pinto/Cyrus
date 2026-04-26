"""
Cyrus — Sharing System Model

Modelled after Google Docs sharing.
Any item (template, result, class, feedback) can be shared
with a specific email or via a token-based link.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SharedItem(Base):
    __tablename__ = "shared_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # What type of item is being shared?
    item_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        doc="template | result | class | feedback_report"
    )

    # The ID of the item being shared (references a record in another table)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # ── Email-based sharing ────────────────────────────────────
    # NULL if link-based sharing
    shared_with_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Permission level (Google Docs model) ──────────────────
    permission: Mapped[str] = mapped_column(
        String(20), default="viewer",
        doc="owner | editor | commenter | viewer"
    )

    # ── Link-based sharing ─────────────────────────────────────
    # Unique opaque token — embedded in the share URL
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Is this share link currently active?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SharedItem type={self.item_type!r} permission={self.permission!r}>"

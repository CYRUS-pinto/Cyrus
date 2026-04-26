"""
Cyrus — Adaptive Learning Models

OcrCorrection: When a teacher corrects an OCR error, that correction
is stored here. After 200+ corrections, the fine-tuning pipeline
can use them to make the model more accurate for this school's handwriting.

FineTuneJob: Tracks when a fine-tuning run was started, how long it took,
and whether accuracy improved.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OcrCorrection(Base):
    """
    One teacher correction = one training sample.
    Stored as: the image crop (what OCR saw) + wrong text + correct text.
    """
    __tablename__ = "ocr_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_page_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission_pages.id", ondelete="CASCADE"))

    # Bounding box of the region on the page that was corrected
    # Stored as JSON: {"x": 100, "y": 200, "w": 300, "h": 50}
    region_bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The cropped image of the region stored in object storage (for fine-tuning dataset)
    image_crop_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # What the OCR model incorrectly produced
    wrong_text: Mapped[str] = mapped_column(Text, nullable=False)

    # What the teacher corrected it to (ground truth)
    correct_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Which OCR model produced the wrong output
    model_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # "trocr" | "olmocr" | "paddleocr" | "got_ocr"

    # Has this correction been used in a fine-tuning run yet?
    used_in_finetune: Mapped[bool] = mapped_column(Boolean, default=False)
    finetune_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    submission_page: Mapped["SubmissionPage"] = relationship("SubmissionPage", back_populates="ocr_corrections")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<OcrCorrection wrong={self.wrong_text[:20]!r} → correct={self.correct_text[:20]!r}>"


class FineTuneJob(Base):
    """
    Tracks a LoRA fine-tuning run on the OCR model.
    Triggered manually by the teacher dashboard when enough corrections exist.
    """
    __tablename__ = "finetune_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Which base model was fine-tuned
    base_model: Mapped[str] = mapped_column(String(100), default="microsoft/trocr-large-handwritten")

    # How many correction samples were used
    corrections_used: Mapped[int] = mapped_column(Integer, default=0)

    # Job status
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        doc="pending | running | completed | failed"
    )

    # Where the fine-tuned model weights are saved
    output_model_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Accuracy metrics (Character Error Rate — lower is better)
    cer_before: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    cer_after: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def improvement_percent(self) -> float | None:
        """
        How much did fine-tuning improve accuracy?
        Negative = improvement (CER is an error rate — lower = better)
        """
        if self.cer_before and self.cer_after and self.cer_before > 0:
            return ((self.cer_before - self.cer_after) / self.cer_before) * 100
        return None

    def __repr__(self) -> str:
        return f"<FineTuneJob status={self.status!r} samples={self.corrections_used}>"

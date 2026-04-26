"""
Cyrus — Initial Database Migration (Alembic)

Run with: alembic upgrade head
           from inside backend/ directory
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all 14 Cyrus tables."""

    op.create_table("classes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("year", sa.String(20), nullable=True),
        sa.Column("section", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("subjects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("faculty_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_slug", sa.String(200), nullable=True),
        sa.Column("name_source", sa.String(20), nullable=True, server_default="fallback"),
        sa.Column("registration_number", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("exams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("exam_date", sa.Date, nullable=True),
        sa.Column("total_marks", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("exam_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_num", sa.String(10), nullable=False),
        sa.Column("part", sa.String(10), nullable=True),
        sa.Column("max_marks", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("rubric_json", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table("answer_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="image_upload"),
        sa.Column("ocr_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("structured_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("answer_key_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("answer_key_id", sa.String(36), sa.ForeignKey("answer_keys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("ocr_status", sa.String(20), nullable=True, server_default="pending"),
        sa.Column("ocr_text", sa.Text, nullable=True),
    )

    op.create_table("upload_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qr_token", sa.String(64), nullable=False, unique=True),
        sa.Column("mobile_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table("submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("upload_sessions.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploading"),
        sa.Column("total_marks", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table("submission_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.String(36), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("is_cover_page", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("preprocessed_url", sa.Text, nullable=True),
        sa.Column("ocr_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("ocr_text_student_only", sa.Text, nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("ocr_winning_model", sa.String(30), nullable=True),
        sa.Column("layout_json", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("grades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.String(36), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("exam_questions.id"), nullable=False),
        sa.Column("max_marks", sa.Numeric(5, 2), nullable=False),
        sa.Column("awarded_marks", sa.Numeric(5, 2), nullable=True),
        sa.Column("override_marks", sa.Numeric(5, 2), nullable=True),
        sa.Column("teacher_override", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("override_note", sa.Text, nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("ai_feedback", sa.Text, nullable=True),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("grading_method", sa.String(30), nullable=True),
        sa.Column("flagged_for_review", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("flag_reason", sa.Text, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("feedback_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.String(36), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary_text", sa.Text, nullable=True),
        sa.Column("study_tips_json", sa.Text, nullable=True),
        sa.Column("concept_gaps_json", sa.Text, nullable=True),
        sa.Column("positive_notes", sa.Text, nullable=True),
        sa.Column("pdf_url", sa.Text, nullable=True),
        sa.Column("share_token", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("shared_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("shared_with_email", sa.String(200), nullable=True),
        sa.Column("permission", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("share_token", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("ocr_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_page_id", sa.String(36), sa.ForeignKey("submission_pages.id"), nullable=True),
        sa.Column("wrong_text", sa.Text, nullable=False),
        sa.Column("correct_text", sa.Text, nullable=False),
        sa.Column("region_bbox_json", sa.Text, nullable=True),
        sa.Column("image_crop_url", sa.Text, nullable=True),
        sa.Column("model_source", sa.String(30), nullable=True),
        sa.Column("used_in_finetune", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("finetune_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("finetune_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("corrections_used", sa.Integer, nullable=True),
        sa.Column("cer_before", sa.Float, nullable=True),
        sa.Column("cer_after", sa.Float, nullable=True),
        sa.Column("output_model_path", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table("audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Indexes for common queries
    op.create_index("ix_submissions_exam_id", "submissions", ["exam_id"])
    op.create_index("ix_grades_submission_id", "grades", ["submission_id"])
    op.create_index("ix_submission_pages_submission_id", "submission_pages", ["submission_id"])
    op.create_index("ix_upload_sessions_qr_token", "upload_sessions", ["qr_token"])
    op.create_index("ix_shared_items_share_token", "shared_items", ["share_token"])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    for table in [
        "audit_log", "finetune_jobs", "ocr_corrections", "shared_items",
        "feedback_reports", "grades", "submission_pages", "submissions",
        "upload_sessions", "answer_key_pages", "answer_keys",
        "exam_questions", "exams", "students", "subjects", "classes",
    ]:
        op.drop_table(table)

"""
Cyrus — Celery Worker Entry Point

This is the file Celery uses to start background workers.
Run with: celery -A celery_worker worker --loglevel=info

Background workers handle all heavy processing:
- OCR pipeline (reading handwriting from photos)
- AI grading (comparing answers)
- Feedback generation (writing student tips)
- PDF export (generating report cards)
"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

# Create the Celery app
# The broker is Redis — it holds the task queue
# The backend is also Redis — it stores task results
celery_app = Celery(
    "cyrus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.ocr_tasks",
        "app.tasks.grade_tasks",
        "app.tasks.feedback_tasks",
        "app.tasks.export_tasks",
    ]
)

# ─────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialize tasks as JSON (readable, debuggable)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task routing — different queues for different priorities
    task_routes={
        "app.tasks.ocr_tasks.*": {"queue": "ocr"},
        "app.tasks.grade_tasks.*": {"queue": "grading"},
        "app.tasks.feedback_tasks.*": {"queue": "feedback"},
        "app.tasks.export_tasks.*": {"queue": "export"},
    },

    # Retry failed tasks up to 3 times (the 3-strike rule)
    task_max_retries=3,
    task_default_retry_delay=30,   # wait 30s before retrying

    # Results expire after 24 hours (saves Redis memory)
    result_expires=86400,

    # Prefetch — workers take 1 task at a time (better for long OCR jobs)
    worker_prefetch_multiplier=1,
    task_acks_late=True,           # task acknowledged only after completion
)

# Make celery_app importable as `celery`
celery = celery_app

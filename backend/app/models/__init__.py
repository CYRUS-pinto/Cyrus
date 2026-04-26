"""
Cyrus Models — Central Import

Import all models here so Alembic can discover them all
for migration generation. If a model isn't imported here,
Alembic won't know it exists.
"""

from app.models.classes import Class, Student, Subject
from app.models.exams import Exam, ExamQuestion
from app.models.answer_keys import AnswerKey, AnswerKeyPage
from app.models.sessions import UploadSession
from app.models.submissions import Submission, SubmissionPage
from app.models.grades import Grade
from app.models.feedback import FeedbackReport
from app.models.sharing import SharedItem
from app.models.adaptive import OcrCorrection, FineTuneJob
from app.models.audit import AuditLog

__all__ = [
    "Class", "Student", "Subject",
    "Exam", "ExamQuestion",
    "AnswerKey", "AnswerKeyPage",
    "UploadSession",
    "Submission", "SubmissionPage",
    "Grade",
    "FeedbackReport",
    "SharedItem",
    "OcrCorrection", "FineTuneJob",
    "AuditLog",
]

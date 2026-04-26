"""Cyrus — Settings page share API update (mounts feedback router)"""
from fastapi import APIRouter

# Re-export all api modules so main.py can import cleanly
from . import health, classes, exams, upload, grade, share, export, sync, adaptive, answer_keys, feedback

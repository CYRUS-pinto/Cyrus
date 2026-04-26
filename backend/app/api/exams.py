"""Cyrus — Exams API (stub — full implementation in Sprint 3)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.exams import Exam, ExamQuestion
from app.models.classes import Subject

router = APIRouter()

@router.get("/", summary="List all exams")
async def list_exams(subject_id: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Exam)
    if subject_id:
        q = q.where(Exam.subject_id == subject_id)
    result = await db.execute(q.order_by(Exam.created_at.desc()))
    exams = result.scalars().all()
    return [{"id": e.id, "name": e.name, "status": e.status, "total_marks": e.total_marks, "exam_date": e.exam_date} for e in exams]

@router.post("/", summary="Create a new exam")
async def create_exam(body: dict, db: AsyncSession = Depends(get_db)):
    exam = Exam(
        subject_id=body["subject_id"],
        name=body["name"],
        exam_date=body.get("exam_date"),
        total_marks=body.get("total_marks", 0),
        status="draft",
    )
    db.add(exam)
    await db.flush()
    return {"id": exam.id, "name": exam.name, "status": exam.status}

@router.get("/{exam_id}", summary="Get exam with questions")
async def get_exam(exam_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    qs = await db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.order_index))
    return {
        "id": exam.id, "name": exam.name, "status": exam.status,
        "total_marks": exam.total_marks, "exam_date": exam.exam_date,
        "questions": [{"id": q.id, "num": q.question_num, "part": q.part, "max_marks": q.max_marks, "content_type": q.content_type} for q in qs.scalars().all()]
    }

@router.post("/{exam_id}/questions", summary="Add a question to an exam")
async def add_question(exam_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    q = ExamQuestion(
        exam_id=exam_id,
        question_num=body["question_num"],
        part=body.get("part"),
        max_marks=body.get("max_marks", 0),
        content_type=body.get("content_type", "text"),
        description=body.get("description"),
        order_index=body.get("order_index", 0),
    )
    db.add(q)
    await db.flush()
    return {"id": q.id, "question_num": q.question_num}

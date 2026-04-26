"""
Cyrus — Classes API Router

Handles all CRUD operations for classes, students, and subjects.
Sprint 0: Route signatures defined, implementation in Sprint 1.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.classes import Class, Student, Subject

router = APIRouter()

# ─────────────────────────────────────────────────────────────────
# CLASSES
# ─────────────────────────────────────────────────────────────────

@router.get("/", summary="List all classes")
async def list_classes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Class).order_by(Class.created_at.desc()))
    classes = result.scalars().all()
    return [{"id": c.id, "name": c.name, "year": c.year, "section": c.section, "created_at": c.created_at} for c in classes]


@router.post("/", summary="Create a new class", status_code=status.HTTP_201_CREATED)
async def create_class(body: dict, db: AsyncSession = Depends(get_db)):
    new_class = Class(
        name=body.get("name", ""),
        year=body.get("year"),
        section=body.get("section"),
        description=body.get("description"),
    )
    db.add(new_class)
    await db.flush()
    return {"id": new_class.id, "name": new_class.name}


@router.get("/{class_id}", summary="Get a class with its students and subjects")
async def get_class(class_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    students_result = await db.execute(select(Student).where(Student.class_id == class_id).order_by(Student.name))
    subjects_result = await db.execute(select(Subject).where(Subject.class_id == class_id))

    return {
        "id": cls.id,
        "name": cls.name,
        "year": cls.year,
        "section": cls.section,
        "description": cls.description,
        "students": [{"id": s.id, "name": s.name, "registration_number": s.registration_number} for s in students_result.scalars().all()],
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in subjects_result.scalars().all()],
    }


@router.put("/{class_id}", summary="Update a class")
async def update_class(class_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    if "name" in body: cls.name = body["name"]
    if "year" in body: cls.year = body["year"]
    if "section" in body: cls.section = body["section"]
    return {"id": cls.id, "name": cls.name}


@router.delete("/{class_id}", summary="Delete a class")
async def delete_class(class_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    await db.delete(cls)
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────
# STUDENTS
# ─────────────────────────────────────────────────────────────────

@router.post("/{class_id}/students", summary="Add a student to a class")
async def add_student(class_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    import re
    name = body.get("name", "Student")
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    student = Student(
        class_id=class_id,
        name=name,
        name_slug=slug,
        registration_number=body.get("registration_number"),
        program=body.get("program"),
        semester=body.get("semester"),
        name_source=body.get("name_source", "manual"),
    )
    db.add(student)
    await db.flush()
    return {"id": student.id, "name": student.name, "name_slug": student.name_slug}


@router.put("/{class_id}/students/{student_id}", summary="Update a student's name")
async def update_student(class_id: str, student_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    import re
    result = await db.execute(select(Student).where(Student.id == student_id, Student.class_id == class_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if "name" in body:
        student.name = body["name"]
        student.name_slug = re.sub(r"[^a-z0-9]+", "_", body["name"].lower()).strip("_")
    if "registration_number" in body:
        student.registration_number = body["registration_number"]
    return {"id": student.id, "name": student.name}


# ─────────────────────────────────────────────────────────────────
# SUBJECTS
# ─────────────────────────────────────────────────────────────────

@router.post("/{class_id}/subjects", summary="Add a subject to a class")
async def add_subject(class_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    subject = Subject(
        class_id=class_id,
        name=body.get("name", ""),
        code=body.get("code"),
        faculty_name=body.get("faculty_name"),
    )
    db.add(subject)
    await db.flush()
    return {"id": subject.id, "name": subject.name}

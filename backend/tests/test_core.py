"""
Cyrus — Pytest Configuration + Backend smoke tests
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─── Health check ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── Classes CRUD ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_and_list_class(client):
    r = await client.post("/api/v1/classes/", json={"name": "Test Class", "year": "2025", "section": "A"})
    assert r.status_code == 200
    class_id = r.json()["id"]
    assert class_id

    r2 = await client.get("/api/v1/classes/")
    assert r2.status_code == 200
    ids = [c["id"] for c in r2.json()]
    assert class_id in ids


# ─── Exam CRUD ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_exam(client):
    # Create subject first
    r = await client.post("/api/v1/classes/", json={"name": "Sprint Test Class"})
    class_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/classes/{class_id}/subjects",
                            json={"name": "Innovation", "code": "IDT101"})
    subject_id = r2.json()["id"]

    r3 = await client.post("/api/v1/exams/",
                            json={"name": "IA 1", "subject_id": subject_id, "total_marks": 30})
    assert r3.status_code == 200
    assert r3.json()["name"] == "IA 1"


# ─── Share token ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_and_resolve_share(client):
    r = await client.post("/api/v1/share/create", json={"item_type": "submission", "item_id": "test-123", "expiry_days": 1})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token.startswith("shr_")

    r2 = await client.get(f"/api/v1/share/{token}")
    assert r2.status_code == 200
    assert r2.json()["item_id"] == "test-123"


# ─── Grading service unit test ──────────────────────────────
def test_semantic_grading_same_text():
    from app.services.grading import GradingService
    svc = GradingService()
    result = svc.grade_question("The mitochondria is the powerhouse of the cell",
                                 "The mitochondria is the powerhouse of the cell", 5.0)
    assert result.awarded_marks == 5.0
    assert result.ai_confidence > 0.85


def test_semantic_grading_empty():
    from app.services.grading import GradingService
    svc = GradingService()
    result = svc.grade_question("", "Some answer", 5.0)
    assert result.awarded_marks == 0


def test_mcq_grading():
    from app.services.grading import GradingService
    svc = GradingService()
    result = svc.grade_question("b)", "b) Photosynthesis", 1.0, content_type="mcq")
    assert result.awarded_marks == 1.0
    result2 = svc.grade_question("a)", "b)", 1.0, content_type="mcq")
    assert result2.awarded_marks == 0


def test_voting_engine_consensus():
    from ocr.ensemble.voting import vote, levenshtein_distance
    assert levenshtein_distance("hello", "hello") == 0
    assert levenshtein_distance("hello", "helo") == 1

    text, conf, model = vote([
        {"model": "trocr", "text": "The quick brown fox", "confidence": 0.85},
        {"model": "olmocr", "text": "The quick brown fox", "confidence": 0.82},
        {"model": "paddleocr", "text": "The quick brown foxe", "confidence": 0.78},
    ])
    assert "quick" in text
    assert conf > 0.85   # consensus → high confidence

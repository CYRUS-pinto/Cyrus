# ───────────────────────────────────────────────────────────────
# Cyrus — Developer Makefile
# Usage: make <target>
# ───────────────────────────────────────────────────────────────

.PHONY: help up down logs db-migrate db-reset frontend backend worker test clean

help:
	@echo ""
	@echo "  Cyrus — Available commands"
	@echo ""
	@echo "  make up         → Start all services (docker compose)"
	@echo "  make down       → Stop all services"
	@echo "  make logs       → Tail all container logs"
	@echo "  make db-migrate → Run Alembic migrations"
	@echo "  make db-reset   → Drop + recreate database (WARNING: wipes data)"
	@echo "  make frontend   → Start Next.js dev server (port 3000)"
	@echo "  make backend    → Start FastAPI dev server (port 8000)"
	@echo "  make worker     → Start Celery OCR worker"
	@echo "  make test       → Run all backend tests"
	@echo "  make clean      → Remove __pycache__ and .next"
	@echo ""

# ── Docker ───────────────────────────────────────────────────
up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d
	@echo ""
	@echo "  ✅ Cyrus is running!"
	@echo "  Dashboard:  http://localhost"
	@echo "  API Docs:   http://localhost:8000/docs"
	@echo "  MinIO:      http://localhost:9001  (minioadmin / minioadmin123)"
	@echo "  Flower:     http://localhost:5555"
	@echo ""

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

# ── Database ─────────────────────────────────────────────────
db-migrate:
	cd backend && alembic upgrade head

db-reset:
	@echo "⚠️  This will delete all data. Press Ctrl+C to cancel, Enter to continue."
	@read _
	cd backend && alembic downgrade base && alembic upgrade head

# ── Local Dev (without Docker) ───────────────────────────────
frontend:
	cd frontend && npm install && npm run dev

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && celery -A celery_worker worker --loglevel=info -Q ocr,grading,feedback,export -c 2

flower:
	cd backend && celery -A celery_worker flower --port=5555

# ── Tests ────────────────────────────────────────────────────
test:
	cd backend && pytest tests/ -v

test-watch:
	cd backend && pytest tests/ -v --watch

# ── Clean ────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

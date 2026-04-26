# Cyrus

> **Open-source AI-powered teacher grading platform.**
> Grade 80 handwritten exam papers in minutes, not hours.

[![License: MIT](https://img.shields.io/badge/License-MIT-violet.svg)](https://opensource.org/licenses/MIT)

---

## What It Does

1. Teacher generates a QR code on their laptop
2. Scans it with their phone → opens camera upload interface
3. Photographs each student's answer booklet (1-click per page)
4. Cyrus reads the handwriting (3-model OCR ensemble), grades against the answer key (Mistral 7B + SymPy), and generates per-student PDF feedback reports

**No login required. Runs offline. Gets smarter from teacher corrections.**

---

## Quick Start (One Command)

```bash
# 1. Clone
git clone https://github.com/your-username/cyrus
cd cyrus

# 2. Copy environment config
cp .env.example .env

# 3. Start everything
docker compose up --build

# 4. Open the app
#    Teacher dashboard: http://localhost:80
#    API docs:          http://localhost:8000/docs
#    MinIO console:     http://localhost:9001  (minioadmin / minioadmin123)
#    Celery monitor:    http://localhost:5555
```

### Requirements
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- [Ollama](https://ollama.com/) running with `mistral:7b-instruct-q4_K_M` and `llava:7b-q4_K_M` pulled
- 16 GB RAM recommended (8 GB minimum)
- GTX 1650+ or any CUDA GPU for AI grading acceleration (CPU fallback available)

### Pull AI models (one-time setup)
```bash
ollama pull mistral:7b-instruct-q4_K_M
ollama pull llava:7b-q4_K_M
ollama pull nomic-embed-text
```

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Next.js 14 Frontend                                 │
│  Teacher dashboard · Mobile upload · Student results │
└────────────────────────┬─────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼─────────────────────────────┐
│  FastAPI Backend                                      │
│  REST API · Business logic · Session management       │
└──────┬──────────────────────────────┬────────────────┘
       │ Celery tasks (Redis)          │ SQLAlchemy
┌──────▼──────────┐          ┌────────▼────────────────┐
│  OCR Workers    │          │  PostgreSQL / SQLite     │
│  TrOCR + OlmOCR │          │  14 tables               │
│  + PaddleOCR    │          └─────────────────────────┘
│  ensemble vote  │
│  + Surya layout │          ┌─────────────────────────┐
│  + GOT-OCR math │          │  MinIO Object Storage   │
└─────────────────┘          │  All photos + PDFs      │
                             └─────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Ollama (local AI server)                            │
│  Mistral 7B · LLaVA 7B · Embedding model            │
└──────────────────────────────────────────────────────┘
```

See [`CYRUS_ARCHITECTURE.md`](./CYRUS_ARCHITECTURE.md) for the complete technical guide.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Celery, Redis |
| Database | PostgreSQL + Alembic migrations |
| Storage | MinIO (self-hosted S3) |
| OCR | TrOCR-Large + OlmOCR-2-7B + PaddleOCR-VL ensemble |
| AI Grading | Mistral 7B (Ollama) + sentence-transformers + SymPy |
| Diagrams | LLaVA 7B (Ollama) |
| Fine-tuning | Unsloth + LoRA (manual trigger) |

---

## Project Status

| Sprint | Status |
|--------|--------|
| 0 — Foundation | ✅ Done |
| 1 — Upload Pipeline | 🔜 Next |
| 2 — OCR Pipeline | 🔜 |
| 3 — AI Grading | 🔜 |
| 4 — Feedback + Export | 🔜 |

---

## License

MIT — free to use, modify, and deploy.

---

*Built with love by Cyrus.*

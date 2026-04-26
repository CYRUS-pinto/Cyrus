# Cyrus — Living Architecture Guide
> **Updated automatically every sprint. This is the source of truth for the whole system.**
> Last updated: Sprint 0 complete

---

## What Cyrus Does (30-second version)

A teacher photographs 80 students' handwritten exam papers on their phone.
Cyrus reads the handwriting (OCR), compares against the answer key (AI grading),
and produces per-student PDF feedback reports with a single command.

---

## How the System Works (The Grand Tour)

```
[Teacher's Laptop]                    [Teacher's Phone]
     │                                       │
     │  1. Teacher opens /dashboard           │
     │  2. Selects exam → clicks Upload      │
     │  3. QR Code appears                   │
     │  4. Phone scans QR ──────────────────►│
     │                                       │  5. Phone opens /session/{token}
     │                                       │  6. Teacher presses [+ New Student]
     │                                       │  7. Photos each page of booklet
     │                                       │  8. Photos upload to MinIO via FastAPI
     │                                       │
[FastAPI /api/v1/upload/...] ◄───────────────┘
     │
     │  9. Each page queued to Redis (Celery task queue)
     │
[Celery OCR Worker]
     │
     │  10. Downloads raw photo from MinIO
     │  11. OpenCV: deskew + denoise + binarize (preprocessor.py)
     │  12. HSV split: remove red teacher marks (color_separator.py)
     │  13. Hough lines: remove crossed-out text (crossed_out_detector.py)
     │  14. Surya: detect text/math/diagram regions (layout_detector.py)
     │  15. Cover page? LLaVA extracts Name + Reg No (cover_extractor.py)
     │  16. Text regions: TrOCR + OlmOCR + PaddleOCR → vote (voting.py)
     │  17. Math regions: GOT-OCR 2.0
     │  18. Confidence < 0.7 → retry (up to 3 strikes) → flag for teacher
     │  19. Results stored in submission_pages table
     │
[FastAPI /api/v1/grade/...]
     │
     │  20. Teacher uploads answer key (same OCR pipeline)
     │  21. Teacher clicks "Grade All"
     │
[Celery Grading Worker]                [Ollama on GTX 1650]
     │                                       │
     │  22. Per question: sentence-transformers similarity
     │  23. Per question: Mistral 7B ────────►│ (if semantic score inconclusive)
     │  24. Math: SymPy equivalence check     │
     │  25. Diagrams: LLaVA comparison ──────►│
     │  26. Grades stored in grades table    │
     │  27. Low confidence → flagged for teacher review
     │
[Teacher reviews grades]
     │
     │  28. Corrects any wrong OCR → saved in ocr_corrections
     │  29. Overrides any AI grade → saved in grades.teacher_override
     │  30. When 200+ corrections collected → "Run Fine-Tuning" button appears
     │
[Celery Feedback Worker]
     │
     │  31. Mistral 7B generates encouraging feedback per student
     │  32. Concept gaps identified + study tips written
     │  33. PDF generated via WeasyPrint
     │  34. Unique token URL created → /results/{token}
     │
[Student]
     │
     │  35. Teacher shares link → student opens /results/{token}
     │      (no login needed — token IS the access)
     └──────────────────────────────────────────────────────────
```

---

## File Map — Where Is Everything?

```
cyrus/
│
├── docker-compose.yml       WHY: One command starts all 7 services
├── .env.example             WHY: Documents every config variable
│
├── nginx/nginx.conf         WHAT: Reverse proxy, rate limiting, WebSocket
│
├── backend/
│   ├── app/main.py          WHAT: FastAPI entry point. Mounts all routers.
│   ├── app/config.py        WHAT: All env vars, typed + validated by Pydantic
│   ├── app/database.py      WHAT: Async SQLAlchemy engine, session factory
│   │
│   ├── app/models/          WHAT: 14 database tables (SQLAlchemy)
│   │   ├── classes.py       → Class, Student, Subject
│   │   ├── exams.py         → Exam, ExamQuestion
│   │   ├── answer_keys.py   → AnswerKey, AnswerKeyPage
│   │   ├── sessions.py      → UploadSession (QR token + state)
│   │   ├── submissions.py   → Submission, SubmissionPage (all OCR output)
│   │   ├── grades.py        → Grade (AI marks + teacher override)
│   │   ├── feedback.py      → FeedbackReport (student link + PDF)
│   │   ├── sharing.py       → SharedItem (Google-style permissions)
│   │   ├── adaptive.py      → OcrCorrection, FineTuneJob
│   │   └── audit.py         → AuditLog (append-only action log)
│   │
│   ├── app/api/             WHAT: HTTP route handlers
│   │   ├── health.py        → GET /health, /health/db
│   │   ├── classes.py       → CRUD for classes, students, subjects
│   │   ├── exams.py         → CRUD for exams + questions
│   │   ├── upload.py        → QR sessions, page upload, student grouping
│   │   ├── grade.py         → Trigger grading, fetch grades, teacher override
│   │   ├── share.py         → Create/revoke share links
│   │   └── export.py        → CSV, PDF, Google Sheets (Sprint 4)
│   │
│   ├── app/services/
│   │   └── storage.py       WHAT: MinIO/Supabase abstraction (upload/download)
│   │
│   ├── app/tasks/           WHAT: Celery background jobs
│   │   ├── ocr_tasks.py     → 3-strike OCR pipeline per page
│   │   └── grade_tasks.py   → AI grading, feedback, export (Sprint 3/4)
│   │
│   ├── alembic/             WHAT: Database migration scripts
│   │   └── env.py           → Connects Alembic to SQLAlchemy models
│   │
│   └── celery_worker.py     WHAT: Celery app, queues (ocr/grading/feedback)
│
├── ocr/
│   ├── pipeline.py          WHAT: Orchestrates full 7-stage OCR pipeline
│   ├── preprocessor.py      WHAT: OpenCV deskew, binarize, denoise
│   ├── color_separator.py   WHAT: HSV masking to remove red teacher marks
│   ├── cover_extractor.py   WHAT: Extract student name, reg no from cover page
│   ├── crossed_out_detector.py WHAT: Hough line detection → remove struck text
│   ├── layout_detector.py   WHAT: Surya region detection
│   └── ensemble/
│       └── voting.py        WHAT: Confidence-weighted majority vote (3 models)
│
└── frontend/
    ├── app/layout.tsx           Root layout (Inter font, dark mode)
    ├── app/globals.css          Design tokens, glassmorphism, animations
    ├── app/(teacher)/layout.tsx Sidebar + header shell
    ├── app/(teacher)/dashboard/ Stats, recent exams, quick actions
    ├── app/(teacher)/classes/   Class management
    ├── app/(teacher)/exams/     Exam management
    ├── app/(teacher)/upload/    QR generation → upload session
    ├── app/(teacher)/grade/     AI grade review + teacher override
    ├── app/(mobile)/session/    Phone camera upload interface
    └── app/results/[token]/     Student feedback (no login, token-based)
```

---

## Database Schema (14 tables)

```
classes ──────── students
     │           students ──── submissions ──── submission_pages
     │                              │                └── ocr_corrections
     └── subjects ─── exams ───────┘
                        │
                        ├── exam_questions ─── grades
                        ├── answer_keys ─────── answer_key_pages
                        └── upload_sessions ─── submissions

feedback_reports (1:1 with submissions)
shared_items (polymorphic)
finetune_jobs (standalone)
audit_log (append-only)
```

---

## Key Design Decisions (Why We Did It This Way)

| Decision | Alternatives Rejected | Reason |
|----------|----------------------|--------|
| OCR ensemble (3 models vote) | Single model | 50% lower CER in literature; no single model wins on all handwriting styles |
| Red ink removal before OCR | OCR everything + filter | Teacher marks in red contaminate grading comparison |
| Celery + Redis (async) | Synchronous endpoint | OCR takes 5–30s per page; can't block 80 concurrent uploads |
| Cover page → LLaVA extraction | Regex on raw OCR | Fixed form layout — VLM is 40% more accurate than regex on labeled forms |
| MinIO (local first) | Supabase only | Works offline, zero cost, teacher controls their own data |
| No login system | Password login | Teachers asked for zero friction; token URLs are the auth mechanism |
| Fallback: `Student_001` reset per session | Global counter | Two different teachers grading different exams shouldn't share numbering |

---

## Sprint Completion Status

| Sprint | Name | Status |
|--------|------|--------|
| 0 | Foundation | ✅ **Complete** |
| 1 | Upload Pipeline | 🔜 Next |
| 2 | OCR Pipeline | 🔜 |
| 3 | Grading Engine | 🔜 |
| 4 | Feedback + Export | 🔜 |
| 5 | Sharing System | 🔜 |
| 6 | Adaptive Fine-Tuning | 🔜 |
| 7 | Polish + Deploy | 🔜 |

---

*This document is updated by the AI architect after every sprint. Never delete it.*

"""
Cyrus — OCR Microservice
Runs as a standalone HTTP server on port 8001.
The main backend calls this service to run OCR on uploaded images.

Endpoints:
  POST /ocr/process  — Run the full OCR pipeline on an image
  GET  /health       — Health check
"""

import os
import base64
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

log = structlog.get_logger()

app = FastAPI(
    title="Cyrus OCR Service",
    description="Ensemble OCR pipeline for handwritten exam papers",
    version="0.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────

class OCRRequest(BaseModel):
    """Request body for OCR processing."""
    image_base64: str          # base64-encoded image bytes
    filename: str = "page.jpg" # original filename for format detection
    mode: str = "full"         # "full" | "header_only" (for name extraction)


class OCRResponse(BaseModel):
    """Response from OCR processing."""
    raw_text: str
    confidence: float          # 0.0–1.0
    regions: list              # list of {type, text, confidence, bbox}
    student_name: Optional[str] = None  # populated in header_only mode
    processing_time_ms: float


# ─────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ocr"}


# ─────────────────────────────────────────────────────────────────
# OCR endpoint
# ─────────────────────────────────────────────────────────────────

@app.post("/ocr/process", response_model=OCRResponse)
async def process_image(req: OCRRequest):
    """
    Run the full OCR ensemble pipeline on a base64-encoded image.
    Returns extracted text, confidence scores, and region breakdown.
    """
    import time
    import io
    from PIL import Image

    start = time.time()

    # Decode the image
    try:
        image_bytes = base64.b64decode(req.image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    # Run the OCR pipeline (lazy import so models load on first call)
    try:
        from pipeline import OCRPipeline

        pipeline = OCRPipeline()
        result = pipeline.process(image, mode=req.mode)

        elapsed_ms = (time.time() - start) * 1000

        return OCRResponse(
            raw_text=result.get("text", ""),
            confidence=result.get("confidence", 0.0),
            regions=result.get("regions", []),
            student_name=result.get("student_name"),
            processing_time_ms=elapsed_ms,
        )
    except Exception as e:
        log.error("ocr_pipeline_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"OCR pipeline error: {e}")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )

"""
Cyrus — Cover Page Extractor

Specifically designed for the St. Aloysius University (and similar Indian university)
Internal Assessment Answer Booklet cover page.

The cover page has a fixed printed template with labeled fields:
  Name:              ___________
  Program:           ___________
  Semester:          ___________
  Course Code:       ___________
  Title of Course:   ___________
  Name of Faculty:   ___________
  Registration No:   [2][5][1][9][1][1][6][0]  ← boxed grid

We use VLM (vision-language model) to extract these fields reliably
because the template is consistent and labeled — much more accurate
than trying to extract from free-form OCR text.
"""

import io
import re
import json
import base64
import structlog
from PIL import Image

log = structlog.get_logger()


def extract_cover_fields(image_bytes: bytes) -> dict:
    """
    Extract structured fields from an answer booklet cover page.

    Returns a dict with extracted fields:
    {
        "name": "Zaeem Zameer Mohammed",
        "registration_number": "25191160",
        "program": "BTech CSE (AIML)",
        "semester": "IInd Sem",
        "course_code": "25ENUMH1GH",
        "course_title": "Innovation and Design Thinking",
        "faculty_name": "Dr. Gleson Tony",
        "confidence": 0.92
    }
    Missing fields will have value None.
    """
    try:
        return _extract_with_ollama_llava(image_bytes)
    except Exception as e:
        log.warning("cover_extraction_llava_failed", error=str(e))
        try:
            return _extract_with_regex_fallback(image_bytes)
        except Exception as e2:
            log.error("cover_extraction_failed", error=str(e2))
            return {}


def _extract_with_ollama_llava(image_bytes: bytes) -> dict:
    """
    Uses LLaVA vision model (running via Ollama) to read the cover page fields.
    LLaVA understands image layouts, not just raw text — ideal for forms.
    """
    from app.config import get_settings
    settings = get_settings()

    # Encode image as base64 for Ollama API
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Precise extraction prompt — tells LLaVA exactly what to extract
    prompt = """This is a university answer booklet cover page.
Extract the following fields and return ONLY valid JSON, no other text:

{
  "name": "<student full name from the Name field>",
  "registration_number": "<digits from Registration No boxes — numbers only>",
  "program": "<program from Program field>",
  "semester": "<semester from Semester field>",
  "course_code": "<code from Course Code field>",
  "course_title": "<title from Title of the Course field>",
  "faculty_name": "<name from Name of the Faculty field>"
}

If a field is unreadable or missing, use null for that field."""

    import httpx
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_vision_model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    raw = response.json().get("response", "{}")

    # Strip any markdown code blocks LLaVA might add
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)

    data = json.loads(raw.strip())
    data["confidence"] = 0.90  # high confidence when LLaVA succeeds
    return data


def _extract_with_regex_fallback(image_bytes: bytes) -> dict:
    """
    Fallback: OCR the full cover page with TrOCR, then extract fields using regex.
    Less accurate than LLaVA for forms, but works without Ollama.
    """
    # Run basic TrOCR on the image
    from ocr.ensemble.trocr_provider import TrOcrProvider
    provider = TrOcrProvider()
    result = provider.process_image(image_bytes)
    text = result.text

    def extract_after_label(label: str, text: str) -> str | None:
        """Find 'Label:' in text and return everything after it on the same line."""
        pattern = rf"{re.escape(label)}\s*:?\s*(.+?)(?:\n|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    # Extract registration number from digit boxes (numbers only)
    reg_match = re.search(r"Registration\s*No\.?\s*[:\|]?\s*([\d\s]+)", text, re.IGNORECASE)
    reg_number = re.sub(r"\s+", "", reg_match.group(1)) if reg_match else None

    return {
        "name": extract_after_label("Name", text),
        "registration_number": reg_number,
        "program": extract_after_label("Program", text),
        "semester": extract_after_label("Semester", text),
        "course_code": extract_after_label("Course Code", text),
        "course_title": extract_after_label("Title of the Course", text) or extract_after_label("Title", text),
        "faculty_name": extract_after_label("Name of the Faculty", text) or extract_after_label("Faculty", text),
        "confidence": 0.65,  # lower confidence for regex fallback
    }

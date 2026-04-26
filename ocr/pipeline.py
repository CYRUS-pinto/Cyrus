"""
Cyrus — OCR Pipeline Orchestrator

This is the central coordinator for reading handwriting from a page.
It runs the full ensemble pipeline and produces a single confident output.

Pipeline order per page:
1.  Pre-process      (preprocessor.py)
2.  Red ink removal  (color_separator.py)
3.  Crossed-out text (crossed_out_detector.py)
4.  Layout detection (layout_detector.py)
5.  Per-region OCR:
    - Text regions  → TrOCR + OlmOCR + PaddleOCR ensemble (voting.py)
    - Math regions  → GOT-OCR 2.0
    - Diagram areas → cropped and stored separately for LLaVA grading
6.  Post-processing:
    - LanguageTool spelling correction
    - Mistral 7B recovery for low-confidence regions
7.  Assemble full page text
"""

import io
import struct
import structlog
from dataclasses import dataclass, field
from PIL import Image

log = structlog.get_logger()


@dataclass
class OcrResult:
    """Output of the OCR pipeline for one page."""
    full_text: str               # Complete OCR text (student + corrected)
    student_text_only: str       # After red ink removal
    confidence: float            # Overall page confidence (0.0-1.0)
    winning_model: str           # Model that "won" majority vote
    regions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class OcrPipeline:
    """
    Main OCR orchestrator. Loaded once per Celery worker and reused across tasks.
    Model loading is lazy (on first call) to avoid slow startup.
    """

    def __init__(self):
        self._trocr = None
        self._olmocr = None
        self._paddleocr = None
        self._got_ocr = None
        self._surya = None

    @property
    def trocr(self):
        if self._trocr is None:
            log.info("loading_trocr")
            from ocr.ensemble.trocr_provider import TrOcrProvider
            self._trocr = TrOcrProvider()
        return self._trocr

    @property
    def olmocr(self):
        if self._olmocr is None:
            log.info("loading_olmocr")
            from ocr.ensemble.olmocr_provider import OlmOcrProvider
            self._olmocr = OlmOcrProvider()
        return self._olmocr

    @property
    def paddleocr(self):
        if self._paddleocr is None:
            log.info("loading_paddleocr")
            from ocr.ensemble.paddleocr_provider import PaddleOcrProvider
            self._paddleocr = PaddleOcrProvider()
        return self._paddleocr

    def run(self, image_bytes: bytes, regions: list) -> OcrResult:
        """
        Run the full OCR pipeline on a pre-processed, colour-separated image.

        Args:
            image_bytes: Student-only image (black writing, red removed)
            regions: List of layout regions from layout_detector.py

        Returns:
            OcrResult with full text, confidence, and winning model
        """
        from ocr.crossed_out_detector import remove_crossed_out_text
        from ocr.ensemble.voting import vote

        # Step 1: Remove crossed-out text
        clean_bytes, removed = remove_crossed_out_text(image_bytes)
        log.debug("crossed_out_removed", count=len(removed))

        # Step 2: Process each region
        text_parts = []
        region_confidences = []
        models_used = []

        for region in regions:
            if region.type == "diagram":
                # Diagrams are stored separately for LLaVA grading — not OCR'd into text
                text_parts.append(f"\n[DIAGRAM: Q{region.question_ref}]\n")
                continue

            # Crop the region from the image
            region_bytes = _crop_region(clean_bytes, region.bbox)

            if region.type == "math":
                # Math regions → GOT-OCR 2.0
                text, conf = self._run_math_ocr(region_bytes)
                model = "got_ocr"
            else:
                # Text regions → Ensemble vote
                results = self._run_ensemble(region_bytes)
                text, conf, model = vote(results)

            text_parts.append(text)
            region_confidences.append(conf)
            models_used.append(model)

        # Step 3: Assemble page text
        full_text = "\n".join(t for t in text_parts if t.strip())

        # Overall confidence = average of all regions
        avg_confidence = sum(region_confidences) / len(region_confidences) if region_confidences else 0.5

        # Winning model = most frequently selected in ensemble votes
        winning = max(set(models_used), key=models_used.count) if models_used else "unknown"

        # Step 4: Post-processing (optional — only if confidence is low)
        if avg_confidence < 0.75:
            full_text = self._languagetool_fix(full_text)

        return OcrResult(
            full_text=full_text,
            student_text_only=full_text,  # already red-ink separated before this step
            confidence=round(avg_confidence, 3),
            winning_model=winning,
            regions=regions,
        )

    def _run_ensemble(self, region_bytes: bytes) -> list[dict]:
        """Run all three OCR models on a text region and return their outputs."""
        results = []
        for name, model in [("trocr", self.trocr), ("olmocr", self.olmocr), ("paddleocr", self.paddleocr)]:
            try:
                result = model.process_image(region_bytes)
                results.append({"model": name, "text": result.text, "confidence": result.confidence})
            except Exception as e:
                log.warning("ensemble_model_failed", model=name, error=str(e))
        return results

    def _run_math_ocr(self, region_bytes: bytes) -> tuple[str, float]:
        """GOT-OCR 2.0 for math/mixed content regions."""
        try:
            if self._got_ocr is None:
                from ocr.math_ocr import GotOcrProvider
                self._got_ocr = GotOcrProvider()
            result = self._got_ocr.process_image(region_bytes)
            return result.text, result.confidence
        except Exception as e:
            log.warning("got_ocr_failed", error=str(e))
            # Fallback to TrOCR
            result = self.trocr.process_image(region_bytes)
            return result.text, result.confidence * 0.8  # reduce confidence for fallback

    def _languagetool_fix(self, text: str) -> str:
        """Run LanguageTool to fix common OCR spelling errors."""
        try:
            import language_tool_python
            tool = language_tool_python.LanguageTool("en-US")
            matches = tool.check(text)
            # Only apply corrections with high confidence
            safe_matches = [m for m in matches if m.ruleId in ("MORFOLOGIK_RULE_EN_GB", "SPELL")]
            return language_tool_python.utils.correct(text, safe_matches)
        except Exception:
            return text  # return original if LanguageTool fails


def _crop_region(image_bytes: bytes, bbox: dict) -> bytes:
    """Crop a region from the image using bounding box coordinates."""
    img = Image.open(io.BytesIO(image_bytes))
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    cropped = img.crop((x, y, x + w, y + h))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=95)
    return buf.getvalue()

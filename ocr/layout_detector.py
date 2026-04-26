"""
Cyrus — Layout Detector (Surya)

Surya is a state-of-the-art document layout detection model.
It identifies regions on a page and classifies each as:
- text (regular paragraph/line text → goes to OCR ensemble)
- math (equations/formulae → goes to GOT-OCR 2.0)
- diagram/figure (drawings → goes to LLaVA for comparison)
- table (structured data → special handling)
- header/title

WHY LAYOUT FIRST:
Without layout detection, we'd OCR the entire page as one blob.
This causes math symbols to get garbled by text OCR, and diagrams
to produce nonsense strings. By splitting first, each region goes
to the right specialist model.

WHAT WE FOUND IN THE SAMPLE PAPERS:
- St. Aloysius booklets have: PART-A/B/C headings (layout markers),
  question numbers (Q1, Q2...), text paragraphs, occasional underlines,
  red margin lines. No complex tables in the student answers.
- The printed form header (cover page) is handled separately by cover_extractor.py
"""

import io
from dataclasses import dataclass, field
import structlog

log = structlog.get_logger()


@dataclass
class LayoutRegion:
    """One detected region on a page."""
    region_id: str
    type: str       # "text" | "math" | "diagram" | "table" | "header" | "question_label"
    bbox: dict      # {"x": 0, "y": 0, "w": 100, "h": 50}
    confidence: float
    question_ref: str | None = None   # e.g. "Q8" — populated by question label detection
    text: str = ""  # filled in by OCR later

    def to_dict(self) -> dict:
        return {
            "region_id": self.region_id,
            "type": self.type,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "question_ref": self.question_ref,
        }


class LayoutDetector:
    """
    Surya layout detector wrapper.
    Loaded once per worker, reused across pages.
    """
    def __init__(self):
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        log.info("surya_loading")
        try:
            from surya.model.layout.encoderdecoder import SuryaLayoutModel
            from surya.model.layout.processor import LayoutImageProcessor
            self._model = SuryaLayoutModel.from_pretrained("surf-ai/surya-layout")
            self._processor = LayoutImageProcessor.from_pretrained("surf-ai/surya-layout")
            log.info("surya_ready")
        except ImportError:
            log.warning("surya_not_installed", fallback="rule_based")
        except Exception as e:
            log.error("surya_load_failed", error=str(e))

    def detect(self, image_bytes: bytes) -> list[LayoutRegion]:
        """
        Detect layout regions in a page image.

        Returns:
            List of LayoutRegion objects ordered top-to-bottom then left-to-right
        """
        self._load()

        if self._model is None:
            # Surya not installed — use simple rule-based split
            return self._fallback_detect(image_bytes)

        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Run Surya
        try:
            preds = self._run_surya(img)
            regions = []
            for i, pred in enumerate(preds):
                region = LayoutRegion(
                    region_id=f"r{i:03d}",
                    type=self._map_label(pred.get("label", "text")),
                    bbox={"x": int(pred["bbox"][0]), "y": int(pred["bbox"][1]),
                          "w": int(pred["bbox"][2] - pred["bbox"][0]),
                          "h": int(pred["bbox"][3] - pred["bbox"][1])},
                    confidence=float(pred.get("confidence", 0.85)),
                )
                regions.append(region)

            # Sort top-to-bottom
            regions.sort(key=lambda r: r.bbox["y"])

            # Assign question references based on position
            regions = self._assign_question_refs(regions)
            return regions

        except Exception as e:
            log.warning("surya_inference_failed", error=str(e))
            return self._fallback_detect(image_bytes)

    def _run_surya(self, img) -> list[dict]:
        """Run Surya model inference."""
        inputs = self._processor(img, return_tensors="pt")
        import torch
        device = next(self._model.parameters()).device if hasattr(self._model, 'parameters') else "cpu"
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self._model(**inputs)
        return outputs if isinstance(outputs, list) else []

    def _map_label(self, label: str) -> str:
        """Map Surya label names to Cyrus region types."""
        mapping = {
            "Text": "text",
            "Figure": "diagram",
            "Table": "table",
            "Formula": "math",
            "Title": "header",
            "Caption": "text",
            "Section-header": "header",
            "List-item": "text",
            "Footnote": "text",
        }
        return mapping.get(label, "text")

    def _assign_question_refs(self, regions: list[LayoutRegion]) -> list[LayoutRegion]:
        """
        Use heuristics to label which question number each region belongs to.
        Looks for region labels like "Q8", "8.", "Part B" at the start of text.
        """
        import re
        current_q = None
        for region in regions:
            if region.text:
                q_match = re.match(r"^(?:Q|Question\s*)?(\d+[a-z]?)\b", region.text.strip(), re.IGNORECASE)
                if q_match:
                    current_q = q_match.group(1)
            if current_q:
                region.question_ref = current_q
        return regions

    def _fallback_detect(self, image_bytes: bytes) -> list[LayoutRegion]:
        """
        Simple fallback when Surya is not installed.
        Treats the entire image as one text region.
        Fine for Sprint 0/1, replaced by Surya in Sprint 2.
        """
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        return [LayoutRegion(
            region_id="r000",
            type="text",
            bbox={"x": 0, "y": 0, "w": w, "h": h},
            confidence=0.7,
        )]


# Module-level singleton for import convenience
_detector = None
def detect_layout(image_bytes: bytes) -> list[LayoutRegion]:
    global _detector
    if _detector is None:
        _detector = LayoutDetector()
    return _detector.detect(image_bytes)

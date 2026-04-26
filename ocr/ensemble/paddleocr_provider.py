"""
Cyrus — PaddleOCR-VL Provider

PaddleOCR is Baidu's open-source OCR toolkit, specifically proven on handwritten text.
The VL (Vision-Language) variant adds contextual understanding.

Why PaddleOCR: Fastest of the three models, excellent on Asian scripts and
handwriting with tight character spacing. Good complement to TrOCR.

Loading: PaddleOCR uses its own initialization — not HuggingFace format.
"""

import io
import structlog
from ocr.ensemble.trocr_provider import OcrModelResult

log = structlog.get_logger()


class PaddleOcrProvider:
    """
    PaddleOCR-VL wrapper.
    Uses PaddleOCR's handwriting recognition pipeline.
    """

    def __init__(self):
        self._ocr = None

    def _load(self):
        if self._ocr is not None:
            return
        log.info("paddleocr_loading")
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,     # handles rotated text lines
                lang="en",
                use_gpu=True,           # falls back to CPU if no GPU
                show_log=False,
                enable_mkldnn=True,     # CPU optimization
                rec_model_dir=None,     # auto-download
                det_model_dir=None,
            )
            log.info("paddleocr_ready")
        except Exception as e:
            log.error("paddleocr_load_failed", error=str(e))
            raise

    def process_image(self, image_bytes: bytes) -> OcrModelResult:
        """Run PaddleOCR on one image region."""
        import numpy as np
        from PIL import Image

        self._load()

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img)

        # Run OCR — returns list of [bounding_box, (text, confidence)]
        results = self._ocr.ocr(img_np, cls=True)

        if not results or not results[0]:
            return OcrModelResult(text="", confidence=0.3, model="paddleocr")

        # Flatten all detected text blocks into a single string
        # Order by vertical position (top-to-bottom reading)
        lines = []
        confidences = []

        for line in results[0]:
            if line is None:
                continue
            bbox, (text, conf) = line
            # Get y-coordinate of the top of the bounding box for sorting
            y_top = min(p[1] for p in bbox)
            lines.append((y_top, text, conf))
            confidences.append(conf)

        # Sort by top position (reading order)
        lines.sort(key=lambda x: x[0])
        full_text = "\n".join(t for _, t, _ in lines)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        return OcrModelResult(
            text=full_text.strip(),
            confidence=round(float(avg_conf), 3),
            model="paddleocr",
        )

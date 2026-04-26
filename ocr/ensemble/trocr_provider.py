"""
Cyrus — TrOCR Handwriting OCR Provider

Microsoft TrOCR-Large-Handwritten is the primary OCR model for student text.
It is a transformer encoder-decoder trained specifically on handwritten text.

Why TrOCR: Best single-model performance on IAM/CVL handwriting benchmarks.
Limitation: Struggles with very messy or unusual handwriting → why we use ensemble.

Loading: Model is loaded ONCE per worker (lazy) and cached as instance variable.
Subsequent calls use the cached model — no repeated 3GB disk reads.
"""

import io
from dataclasses import dataclass
import structlog

log = structlog.get_logger()


@dataclass
class OcrModelResult:
    text: str
    confidence: float
    model: str


class TrOcrProvider:
    """
    TrOCR-Large-Handwritten wrapper.
    Model: microsoft/trocr-large-handwritten
    Architecture: ViT (vision encoder) + RoBERTa (text decoder)
    """
    MODEL_ID = "microsoft/trocr-large-handwritten"

    def __init__(self):
        self._processor = None
        self._model = None

    def _load(self):
        """Lazy load — only runs on the first call, never again."""
        if self._model is not None:
            return
        log.info("trocr_loading", model=self.MODEL_ID)
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        self._processor = TrOCRProcessor.from_pretrained(self.MODEL_ID)
        self._model = VisionEncoderDecoderModel.from_pretrained(self.MODEL_ID)

        # Move to GPU if available
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._model.to(device)
        self._model.eval()
        log.info("trocr_ready", device=device)

    def process_image(self, image_bytes: bytes) -> OcrModelResult:
        """
        Run TrOCR on one image region.

        Args:
            image_bytes: Cleaned, pre-processed image bytes

        Returns:
            OcrModelResult with text and confidence
        """
        import torch
        from PIL import Image

        self._load()

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Resize if too tall (TrOCR works best on single-line crops)
        w, h = img.size
        if h > 128:
            scale = 128 / h
            img = img.resize((int(w * scale), 128))

        # Prepare inputs
        pixel_values = self._processor(img, return_tensors="pt").pixel_values
        device = next(self._model.parameters()).device
        pixel_values = pixel_values.to(device)

        # Generate text
        with torch.no_grad():
            outputs = self._model.generate(
                pixel_values,
                max_new_tokens=256,
                output_scores=True,
                return_dict_in_generate=True,
            )

        # Decode text
        text = self._processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0]

        # Estimate confidence from token scores
        confidence = self._estimate_confidence(outputs.scores)

        return OcrModelResult(text=text.strip(), confidence=confidence, model="trocr")

    def _estimate_confidence(self, scores) -> float:
        """
        Convert per-token log probabilities to an overall confidence score.
        Higher = model was more certain about its output.
        """
        import torch
        import math

        if not scores:
            return 0.5

        try:
            # Average probability across all generated tokens
            probs = [torch.softmax(s, dim=-1).max().item() for s in scores]
            avg_prob = sum(probs) / len(probs)
            # Scale to [0.3, 0.97] — TrOCR rarely hits extremes
            return round(max(0.3, min(0.97, avg_prob)), 3)
        except Exception:
            return 0.6

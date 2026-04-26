"""
Cyrus — OlmOCR-2-7B Provider

OlmOCR is a vision-language model from the Allen Institute for AI.
It can read complex document layouts including mixed text+math on the same line.

Why OlmOCR: Specifically designed for document OCR, handles printed+handwritten mix.
Size: ~7B parameters — requires at least 8GB VRAM or runs on CPU (slower).

Loading: Same lazy-load pattern as TrOCR — loaded once per worker.
"""

import io
import structlog
from ocr.ensemble.trocr_provider import OcrModelResult

log = structlog.get_logger()


class OlmOcrProvider:
    """
    OlmOCR-2-7B wrapper.
    Model: allenai/olmOCR-7B-0225-preview
    Architecture: Vision-Language Model (Qwen2-VL backbone)
    """
    MODEL_ID = "allenai/olmOCR-7B-0225-preview"

    def __init__(self):
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        log.info("olmocr_loading", model=self.MODEL_ID)
        try:
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            self._processor = AutoProcessor.from_pretrained(self.MODEL_ID, trust_remote_code=True)
            self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.MODEL_ID,
                torch_dtype=dtype,
                device_map=device,
                trust_remote_code=True,
            )
            self._model.eval()
            log.info("olmocr_ready", device=device)
        except Exception as e:
            log.error("olmocr_load_failed", error=str(e))
            raise

    def process_image(self, image_bytes: bytes) -> OcrModelResult:
        """Run OlmOCR on one image region."""
        import torch
        from PIL import Image

        self._load()

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # OlmOCR uses a chat-style prompt with the image
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": "Read all text in this image exactly as written. Output only the text, nothing else."},
                ],
            }
        ]

        text_prompt = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self._processor(
            text=[text_prompt],
            images=[img],
            return_tensors="pt",
        )

        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = self._model.generate(**inputs, max_new_tokens=512)

        input_len = inputs["input_ids"].shape[1]
        output_ids = output_ids[:, input_len:]
        text = self._processor.batch_decode(output_ids, skip_special_tokens=True)[0]

        return OcrModelResult(
            text=text.strip(),
            confidence=0.78,  # OlmOCR doesn't expose token probabilities easily
            model="olmocr",
        )

"""
Cyrus — GOT-OCR 2.0 Math OCR Provider

GOT-OCR 2.0 (General OCR Theory) is designed for mixed-content pages
with both text and mathematical notation. It outputs LaTeX for math.

Why GOT for math: Standard OCR models output "x2" for x² and "integral" for ∫.
GOT outputs "$x^{2}$" and "$\\int$" — actual LaTeX that SymPy can parse.

This is critical for the math verification step in grading:
If a student writes "x² + 2x = 0" and the answer key has x²+2x=0,
SymPy can verify they are equivalent ONLY if OCR outputs valid LaTeX.
"""

import io
import structlog
from ocr.ensemble.trocr_provider import OcrModelResult

log = structlog.get_logger()


class GotOcrProvider:
    """
    GOT-OCR 2.0 wrapper.
    Model: stepfun-ai/GOT-OCR2_0
    Outputs: Plain text, LaTeX, or markdown based on content type
    """
    MODEL_ID = "stepfun-ai/GOT-OCR2_0"

    def __init__(self):
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return
        log.info("got_ocr_loading", model=self.MODEL_ID)
        try:
            from transformers import AutoModel, AutoTokenizer
            import torch

            self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID, trust_remote_code=True)
            self._model = AutoModel.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                device_map="auto",
                use_safetensors=True,
                pad_token_id=self._tokenizer.eos_token_id,
            )
            self._model.eval()
            log.info("got_ocr_ready")
        except Exception as e:
            log.error("got_ocr_load_failed", error=str(e))
            raise

    def process_image(self, image_bytes: bytes) -> OcrModelResult:
        """
        Run GOT-OCR on an image region. Returns LaTeX for math content.

        The model automatically detects if content is:
        - Plain text → returns text
        - Math formula → returns LaTeX wrapped in $...$
        - Mixed → returns a mix
        """
        import tempfile
        import os

        self._load()

        # GOT-OCR requires a file path (saves to temp file)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_bytes)
            tmp_path = f.name

        try:
            # type: "ocr" for plain text, "format" for structured (LaTeX + markdown)
            result = self._model.chat(
                self._tokenizer,
                tmp_path,
                ocr_type="format",   # outputs LaTeX for math
                render=False,
            )
            return OcrModelResult(
                text=result.strip(),
                confidence=0.85,  # GOT-OCR is generally high confidence
                model="got_ocr",
            )
        except Exception as e:
            log.warning("got_ocr_inference_failed", error=str(e))
            return OcrModelResult(text="", confidence=0.2, model="got_ocr")
        finally:
            os.unlink(tmp_path)

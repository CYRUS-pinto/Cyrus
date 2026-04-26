"""
Cyrus — AI Grading Service

The heart of the system. Takes student OCR text and answer key text,
runs them through 4 grading strategies, and returns a final mark + explanation.

Grading Strategy (in order):
1. SEMANTIC SIMILARITY — sentence-transformers MiniLM (fast, CPU)
   "Invention; Innovation" ≈ "Invention and Innovation" → accept
   
2. LLM GRADING — Mistral 7B via Ollama (slower, GPU, for nuanced text)
   Long paragraph answers where semantic alone isn't enough.
   Falls back to Groq cloud if Ollama unavailable.
   
3. MATH VERIFICATION — SymPy (deterministic, always correct for math)
   "x² + 2x = 0" sympy-equivalent to "x(x+2) = 0" → full marks
   
4. DIAGRAM COMPARISON — LLaVA 7B via Ollama (vision model)
   Compares student-drawn diagram to answer key diagram.
   Checks: key components present, correct relationships, labels.
"""

import json
import re
import structlog
from dataclasses import dataclass
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


@dataclass
class GradingResult:
    awarded_marks: float
    max_marks: float
    ai_confidence: float
    ai_feedback: str
    ai_reasoning: str
    grading_method: str        # "semantic" | "llm" | "sympy" | "llava" | "hybrid"
    flagged_for_review: bool = False
    flag_reason: str | None = None


class GradingService:
    """
    Orchestrates all grading strategies.
    Loaded once per Celery worker.
    """

    def __init__(self):
        self._embedder = None   # sentence-transformers
        self._similarity_threshold = 0.75  # above this = semantically similar

    @property
    def embedder(self):
        if self._embedder is None:
            log.info("loading_sentence_transformers")
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._embedder

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC: Grade one question
    # ─────────────────────────────────────────────────────────────────
    def grade_question(
        self,
        student_text: str,
        answer_key_text: str,
        max_marks: float,
        content_type: str = "text",
        rubric: dict | None = None,
        student_diagram_url: str | None = None,
        answer_key_diagram_url: str | None = None,
    ) -> GradingResult:
        """
        Grade one student answer against the answer key.
        
        Strategy selection:
        - Empty answer → 0 marks
        - content_type == "math" → SymPy first, then LLM fallback
        - content_type == "diagram" → LLaVA
        - content_type == "mcq" → exact match
        - Otherwise → semantic, then LLM if low confidence
        """
        # Empty answer
        if not student_text or not student_text.strip():
            return GradingResult(0, max_marks, 0.95, "No answer provided.", "", "semantic")

        # MCQ — exact or close match
        if content_type == "mcq":
            return self._grade_mcq(student_text, answer_key_text, max_marks)

        # Math — SymPy first
        if content_type == "math":
            result = self._grade_math(student_text, answer_key_text, max_marks)
            if result.ai_confidence >= 0.85:
                return result
            # Fall through to LLM for low-confidence math

        # Diagram — LLaVA
        if content_type == "diagram" and student_diagram_url and answer_key_diagram_url:
            return self._grade_diagram(student_diagram_url, answer_key_diagram_url, max_marks)

        # Text/mixed — semantic first, LLM if needed
        semantic_result = self._grade_semantic(student_text, answer_key_text, max_marks)

        # If semantic is confident enough, return it
        if semantic_result.ai_confidence >= 0.80:
            return semantic_result

        # Low semantic confidence → escalate to LLM
        log.info("escalating_to_llm", semantic_conf=semantic_result.ai_confidence)
        try:
            return self._grade_llm(student_text, answer_key_text, max_marks, rubric)
        except Exception as e:
            log.warning("llm_grading_failed", error=str(e))
            # Fall back to semantic result but flag for review
            semantic_result.flagged_for_review = True
            semantic_result.flag_reason = f"LLM unavailable, semantic confidence {semantic_result.ai_confidence:.0%}"
            return semantic_result

    # ─────────────────────────────────────────────────────────────────
    # STRATEGY 1: Semantic Similarity
    # ─────────────────────────────────────────────────────────────────
    def _grade_semantic(self, student_text: str, answer_key_text: str, max_marks: float) -> GradingResult:
        """
        Uses sentence-transformers to compute cosine similarity.
        Fast (runs on CPU in ~100ms) but doesn't understand partial credit nuance.
        """
        from sentence_transformers import util
        import torch

        student_emb = self.embedder.encode(student_text, convert_to_tensor=True)
        key_emb = self.embedder.encode(answer_key_text, convert_to_tensor=True)

        similarity = float(util.cos_sim(student_emb, key_emb)[0][0])

        # Map similarity to marks (non-linear — small differences matter at the top end)
        if similarity >= 0.90:
            ratio = 1.0
        elif similarity >= 0.75:
            ratio = 0.7 + (similarity - 0.75) / 0.15 * 0.3
        elif similarity >= 0.55:
            ratio = 0.4 + (similarity - 0.55) / 0.20 * 0.3
        elif similarity >= 0.35:
            ratio = 0.1 + (similarity - 0.35) / 0.20 * 0.3
        else:
            ratio = 0.0

        awarded = round(ratio * max_marks, 1)
        confidence = round(min(0.90, 0.5 + abs(similarity - 0.5)), 3)

        feedback = (
            "Answer matches key concepts well." if ratio >= 0.7
            else "Answer partially covers the topic."
            if ratio >= 0.3 else "Answer does not address the question."
        )

        return GradingResult(
            awarded_marks=awarded,
            max_marks=max_marks,
            ai_confidence=confidence,
            ai_feedback=feedback,
            ai_reasoning=f"Semantic similarity: {similarity:.2f} → ratio: {ratio:.2f}",
            grading_method="semantic",
        )

    # ─────────────────────────────────────────────────────────────────
    # STRATEGY 2: LLM Grading (Mistral 7B / Groq fallback)
    # ─────────────────────────────────────────────────────────────────
    def _grade_llm(self, student_text: str, answer_key_text: str, max_marks: float, rubric: dict | None) -> GradingResult:
        """
        Uses Mistral 7B (via Ollama) to perform nuanced grading.
        Returns structured JSON with marks and feedback.
        """
        rubric_str = json.dumps(rubric, indent=2) if rubric else "No rubric provided — use your judgment."

        prompt = f"""You are a university professor grading an exam answer.

ANSWER KEY (model answer):
{answer_key_text}

STUDENT ANSWER:
{student_text}

RUBRIC:
{rubric_str}

MAXIMUM MARKS: {max_marks}

Grade the student answer. Return ONLY valid JSON, no other text:
{{
  "awarded_marks": <number between 0 and {max_marks}>,
  "confidence": <0.0 to 1.0 — how confident you are in this grade>,
  "feedback": "<1-2 sentence feedback for the student, encouraging tone>",
  "reasoning": "<brief internal reasoning for the marks>"
}}

Rules:
- awarded_marks must be a multiple of 0.5
- Be fair but precise — partial credit is allowed
- If the answer shows correct understanding but wrong phrasing, award most marks"""

        # Try Ollama first
        try:
            result_json = self._call_ollama(prompt)
            return self._parse_llm_response(result_json, max_marks, "llm")
        except Exception as e:
            log.warning("ollama_failed", error=str(e))

        # Groq cloud fallback
        if settings.groq_api_key:
            try:
                result_json = self._call_groq(prompt)
                return self._parse_llm_response(result_json, max_marks, "llm")
            except Exception as e:
                log.error("groq_failed", error=str(e))

        raise RuntimeError("All LLM backends failed")

    def _call_ollama(self, prompt: str) -> str:
        import httpx
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": settings.ollama_grading_model, "prompt": prompt, "stream": False},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["response"]

    def _call_groq(self, prompt: str) -> str:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content

    def _parse_llm_response(self, raw: str, max_marks: float, method: str) -> GradingResult:
        raw = re.sub(r"```json\s*", "", raw).replace("```", "").strip()
        data = json.loads(raw)
        awarded = min(float(data.get("awarded_marks", 0)), max_marks)
        # Round to nearest 0.5
        awarded = round(awarded * 2) / 2
        return GradingResult(
            awarded_marks=awarded,
            max_marks=max_marks,
            ai_confidence=float(data.get("confidence", 0.75)),
            ai_feedback=data.get("feedback", ""),
            ai_reasoning=data.get("reasoning", ""),
            grading_method=method,
        )

    # ─────────────────────────────────────────────────────────────────
    # STRATEGY 3: Math Verification (SymPy)
    # ─────────────────────────────────────────────────────────────────
    def _grade_math(self, student_text: str, answer_key_text: str, max_marks: float) -> GradingResult:
        """
        Deterministic math verification using SymPy.
        If student's expression is symbolically equivalent to the answer key → full marks.
        """
        try:
            import sympy
            from sympy.parsing.latex import parse_latex
            from sympy import simplify, sympify

            # Try to parse as LaTeX first (GOT-OCR outputs LaTeX)
            def parse_expr(text: str):
                text = text.strip().strip("$")
                try:
                    return parse_latex(text)
                except Exception:
                    return sympify(text)

            student_expr = parse_expr(student_text)
            key_expr = parse_expr(answer_key_text)

            # Check symbolic equivalence
            difference = simplify(student_expr - key_expr)
            equivalent = difference == 0

            if equivalent:
                return GradingResult(
                    awarded_marks=max_marks,
                    max_marks=max_marks,
                    ai_confidence=0.98,
                    ai_feedback="Correct! Your answer is mathematically equivalent to the model solution.",
                    ai_reasoning=f"SymPy: {student_expr} == {key_expr} → True",
                    grading_method="sympy",
                )
            else:
                return GradingResult(
                    awarded_marks=0,
                    max_marks=max_marks,
                    ai_confidence=0.90,
                    ai_feedback="The mathematical expression doesn't match the expected answer.",
                    ai_reasoning=f"SymPy: {student_expr} ≠ {key_expr}, diff={difference}",
                    grading_method="sympy",
                )
        except Exception as e:
            log.debug("sympy_parse_failed", error=str(e))
            # Fall through to LLM
            return GradingResult(0, max_marks, 0.3, "", f"SymPy parse failed: {e}", "sympy",
                                 flagged_for_review=True, flag_reason="Could not parse math expression")

    # ─────────────────────────────────────────────────────────────────
    # STRATEGY 4: MCQ Exact Match
    # ─────────────────────────────────────────────────────────────────
    def _grade_mcq(self, student_text: str, answer_key_text: str, max_marks: float) -> GradingResult:
        """
        MCQ: extract the selected option and compare.
        Handles formats: "b)", "(b)", "B", "b. Social; Agricultural"
        """
        import re
        def extract_option(text: str) -> str:
            match = re.match(r"[(\[]?\s*([a-dA-D])\s*[)\]]?", text.strip())
            return match.group(1).lower() if match else text.strip().lower()[:3]

        student_opt = extract_option(student_text)
        key_opt = extract_option(answer_key_text)
        correct = student_opt == key_opt

        return GradingResult(
            awarded_marks=max_marks if correct else 0,
            max_marks=max_marks,
            ai_confidence=0.97,
            ai_feedback="Correct!" if correct else f"Incorrect. The right answer was ({key_opt}).",
            ai_reasoning=f"MCQ: student='{student_opt}' key='{key_opt}' match={correct}",
            grading_method="semantic",
        )

    # ─────────────────────────────────────────────────────────────────
    # STRATEGY 5: Diagram Comparison (LLaVA)
    # ─────────────────────────────────────────────────────────────────
    def _grade_diagram(self, student_diagram_url: str, answer_key_diagram_url: str, max_marks: float) -> GradingResult:
        """
        Compares student-drawn diagram to answer key diagram using LLaVA.
        Checks: key components present, correct relationships, labels.
        """
        try:
            import httpx
            import base64
            from app.services.storage import download_file, key_from_url

            student_bytes = download_file(key_from_url(student_diagram_url))  # type: ignore
            key_bytes = download_file(key_from_url(answer_key_diagram_url))  # type: ignore

            student_b64 = base64.b64encode(student_bytes).decode()
            key_b64 = base64.b64encode(key_bytes).decode()

            prompt = f"""Compare these two diagrams. The first is a student's answer, the second is the model answer.
Score the student diagram out of {max_marks} marks based on:
- Key components present (50% of marks)
- Correct relationships/connections between components (30% of marks)  
- Accurate labels (20% of marks)

Return ONLY JSON:
{{"awarded_marks": <number>, "confidence": <0.0-1.0>, "feedback": "<1-2 sentences>", "reasoning": "<what was correct/missing>"}}"""

            response = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_vision_model,
                    "prompt": prompt,
                    "images": [student_b64, key_b64],
                    "stream": False,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            raw = response.json()["response"]
            return self._parse_llm_response(raw, max_marks, "llava")

        except Exception as e:
            log.warning("diagram_grading_failed", error=str(e))
            return GradingResult(
                max_marks / 2, max_marks, 0.3,
                "Diagram grading requires manual review.",
                str(e), "llava",
                flagged_for_review=True, flag_reason="LLaVA unavailable for diagram comparison"
            )

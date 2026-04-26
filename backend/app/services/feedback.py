"""
Cyrus — Feedback Generation Service (Sprint 4)

After all questions are graded, a second AI pass generates a complete
personalized feedback report for the student.

Uses Mistral 7B via Ollama. Falls back to Groq.

The feedback is:
- Encouraging (never demoralizing)  
- Specific (identifies exact concept gaps)
- Actionable (provides study tips with chapter references)
- Concise (3-4 bullet points, not an essay)
"""

import json
import re
import structlog
from dataclasses import dataclass
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


@dataclass
class FeedbackResult:
    summary: str
    study_tips: list[dict]    # [{"topic": "ATP", "tip": "Review Chapter 4.3"}]
    concept_gaps: list[dict]  # [{"concept": "ATP synthesis", "severity": "major"}]
    positive_notes: str


class FeedbackService:

    def generate(
        self,
        student_name: str,
        exam_name: str,
        total_marks: float,
        max_marks: float,
        grade_breakdown: list[dict],  # [{"question": "Q8", "awarded": 4, "max": 6, "feedback": "..."}]
    ) -> FeedbackResult:
        """
        Generate a comprehensive feedback report for one student.

        Args:
            student_name: Student's name (for personalization)
            exam_name: Name of the exam
            total_marks: Total marks awarded
            max_marks: Maximum possible marks
            grade_breakdown: Per-question grading results
        """
        percentage = (total_marks / max_marks * 100) if max_marks > 0 else 0

        # Build context for the LLM
        grade_summary = "\n".join([
            f"- {g['question']}: {g['awarded']}/{g['max']} marks. {g.get('feedback', '')}"
            for g in grade_breakdown
        ])

        prompt = f"""You are a supportive university professor writing a personalized feedback report for a student.

Student: {student_name}
Exam: {exam_name}
Score: {total_marks}/{max_marks} ({percentage:.0f}%)

Grade breakdown by question:
{grade_summary}

Write a feedback report. Return ONLY valid JSON:
{{
  "summary": "<1-2 encouraging sentences about overall performance>",
  "positive_notes": "<1 sentence about what they did well>",
  "concept_gaps": [
    {{"concept": "<topic they struggled with>", "severity": "major|minor"}}
  ],
  "study_tips": [
    {{"topic": "<topic>", "tip": "<specific actionable advice>", "chapter_ref": "<optional chapter reference>"}}
  ]
}}

Rules:
- Maximum 3 concept_gaps
- Maximum 4 study_tips
- Always start with encouragement, even for low scores
- Be specific about WHAT to study, not just "study more"
- Use student's name in the summary"""

        raw = self._call_llm(prompt)
        return self._parse_feedback(raw)

    def _call_llm(self, prompt: str) -> str:
        import httpx

        try:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_grading_model, "prompt": prompt, "stream": False},
                timeout=90.0,
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            log.warning("feedback_ollama_failed", error=str(e))

        if settings.groq_api_key:
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            resp = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return resp.choices[0].message.content

        raise RuntimeError("All LLM backends unavailable for feedback generation")

    def _parse_feedback(self, raw: str) -> FeedbackResult:
        raw = re.sub(r"```json\s*", "", raw).replace("```", "").strip()
        data = json.loads(raw)
        return FeedbackResult(
            summary=data.get("summary", ""),
            study_tips=data.get("study_tips", []),
            concept_gaps=data.get("concept_gaps", []),
            positive_notes=data.get("positive_notes", ""),
        )

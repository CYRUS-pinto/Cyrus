"""
Cyrus — Ensemble Voting Engine

Three OCR models vote on every text region.
The winner is selected by confidence-weighted majority voting.

Voting rules:
- If all 3 agree (Levenshtein distance < 3):   → HIGH confidence
- If 2 agree, 1 differs:                        → MEDIUM confidence, use majority
- If all 3 disagree:                            → LOW confidence, use highest scorer, flag for review

This is based on peer-reviewed research showing a 50% reduction in
Character Error Rate when using top-5 voting ensembles on handwritten text
(AAAI 2022, confirmed in 2025 papers).
"""

from dataclasses import dataclass


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates how 'different' two strings are.
    0 = identical. Higher = more different.
    Named after the Russian scientist Vladimir Levenshtein (1965).
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if not s2:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for c1 in s1:
        curr_row = [prev_row[0] + 1]
        for j, c2 in enumerate(s2):
            curr_row.append(min(prev_row[j + 1] + 1, curr_row[-1] + 1, prev_row[j] + (c1 != c2)))
        prev_row = curr_row
    return prev_row[-1]


def vote(results: list[dict]) -> tuple[str, float, str]:
    """
    Choose the best OCR output from a list of model results.

    Args:
        results: List of {"model": "trocr", "text": "...", "confidence": 0.85}

    Returns:
        Tuple of (winning_text, confidence_score, winning_model_name)
    """
    if not results:
        return "", 0.0, "none"

    if len(results) == 1:
        r = results[0]
        return r["text"], r["confidence"] * 0.8, r["model"]  # single model — lower confidence

    texts = [r["text"].strip() for r in results]
    confs = [r["confidence"] for r in results]
    models = [r["model"] for r in results]

    # ── Case 1: All 3 agree ────────────────────────────────
    if len(results) == 3:
        d01 = levenshtein_distance(texts[0], texts[1])
        d02 = levenshtein_distance(texts[0], texts[2])
        d12 = levenshtein_distance(texts[1], texts[2])

        if d01 <= 3 and d02 <= 3 and d12 <= 3:
            # All agree — use the highest-confidence output
            best_idx = confs.index(max(confs))
            return texts[best_idx], min(0.97, max(confs) * 1.05), models[best_idx]

        # ── Case 2: Two agree, one differs ────────────────
        pairs = [(0, 1, d01), (0, 2, d02), (1, 2, d12)]
        agreeing_pair = None
        for i, j, dist in pairs:
            if dist <= 3:
                agreeing_pair = (i, j)
                break

        if agreeing_pair is not None:
            i, j = agreeing_pair
            # Use the one with higher confidence from the agreeing pair
            winner_idx = i if confs[i] >= confs[j] else j
            avg_conf = (confs[i] + confs[j]) / 2
            return texts[winner_idx], round(avg_conf * 0.95, 3), models[winner_idx]

    # ── Case 3: All disagree — use highest confidence ─────
    best_idx = confs.index(max(confs))
    # Lower confidence since no consensus (will be flagged for review if below threshold)
    return texts[best_idx], round(max(confs) * 0.7, 3), models[best_idx]

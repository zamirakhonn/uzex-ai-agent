from __future__ import annotations

from rapidfuzz import fuzz

from .glossary import GLOSSARY
from .textnorm import normalize


def glossary_search(question: str, threshold: float = 40) -> dict | None:
    q = normalize(question)
    best = None
    best_score = 0.0
    for item in GLOSSARY:
        score = float(fuzz.token_set_ratio(q, normalize(item["keys"] + " " + item["uz"] + " " + item["ru"])))
        if score > best_score:
            best_score = score
            best = item
    if best and best_score >= threshold:
        return {**best, "score": best_score}
    return None

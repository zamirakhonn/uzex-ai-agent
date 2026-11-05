from __future__ import annotations

import re
import unicodedata

_QUOTES = str.maketrans({'"': " ", "'": " ", "«": " ", "»": " ", "“": " ", "”": " "})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = text.replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("`", "'")
    text = text.translate(_QUOTES)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def compact_legal(text: str) -> str:
    t = normalize(text)
    t = re.sub(r"\b(mchj|мчж|ooo|ооо|aj|ао|qmj|қмж)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

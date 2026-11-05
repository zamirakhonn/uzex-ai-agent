from __future__ import annotations

import re

from .schemas import Language

_UZ_CYR = re.compile(r"[ўқғҳЎҚҒҲ]")
_CYR = re.compile(r"[А-Яа-яЁё]")
_UZ_LATIN = re.compile(
    r"\b(yilda|nechta|qancha|qaysi|bitim|shartnoma|kompaniya|sotuvchi|xaridor|"
    r"eng\s+ko'?p|ma.?lumot|tushuntir|qilgan|bo'?lgan|necha|qayerda|"
    r"o'?zbek|so'?m|dollari|broker|ishtirokchi)\b",
    re.I,
)
_RU = re.compile(
    r"\b(сколько|сделк|контракт|компани|продав|покупател|самая|самый|какой|"
    r"какая|данные|информация|год[ауе]?|январ|феврал|сумм|брокер|участник)\b",
    re.I,
)


def detect_language(text: str) -> Language:
    if _UZ_CYR.search(text):
        return "uz"
    if _UZ_LATIN.search(text) and not _RU.search(text):
        return "uz"
    if _RU.search(text) or (_CYR.search(text) and not _UZ_CYR.search(text)):
        return "ru"
    if _UZ_LATIN.search(text):
        return "uz"
    return "uz"

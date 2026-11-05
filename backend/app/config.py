from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data")).expanduser().resolve()
DB_DIR = Path(os.getenv("DB_DIR", ROOT / "db")).expanduser().resolve()
DB_PATH = DB_DIR / "uzex.duckdb"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
ENABLE_LLM_SQL = os.getenv("ENABLE_LLM_SQL", "false").lower() in {"1", "true", "yes"}
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

FUZZY_COMPANY_THRESHOLD = 82.0
VECTOR_SCORE_THRESHOLD = 0.28
CACHE_SIZE = 256

NOT_FOUND = {
    "uz": "Ushbu ma'lumot datasetda mavjud emas.",
    "ru": "Этой информации нет в предоставленных данных.",
}

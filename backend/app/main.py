from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .catalog import catalog
from .config import DB_PATH, ENABLE_LLM_SQL, OPENAI_API_KEY
from .db import fetchall, fetchone, get_con
from .ingest import build_database
from .pipeline import answer
from .schemas import AskRequest, AskResponse, HealthResponse, StatsResponse
from .telegram import close_telegram, initialize_telegram, router as telegram_router

SUGGESTED = {
    "uz": [
        "2025 yilda nechta bitim tuzilgan?",
        "2024 yil yanvarida nechta bitim bo'lgan?",
        "Eng katta bitim qaysi?",
        "Eng ko'p bitim qilgan kompaniya qaysi?",
        "Eksport bitimlari nechta?",
        "USD kursi 03.01.2022 qancha?",
        "Bitim holatlari bo'yicha statistika",
        "2024 va 2025 yillarni solishtiring",
    ],
    "ru": [
        "Сколько сделок было в 2025 году?",
        "Сколько сделок было в январе 2024 года?",
        "Какая самая крупная сделка?",
        "Какая компания заключила больше всего сделок?",
        "Сколько экспортных сделок?",
        "Какой курс доллара на 03.01.2022?",
        "Статистика по состояниям сделок",
        "Сравните 2024 и 2025 годы",
    ],
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    force = not Path(DB_PATH).exists()
    build_database(force=force)
    get_con()
    catalog.load()
    await initialize_telegram()
    try:
        yield
    finally:
        await close_telegram()


app = FastAPI(title="UZEX Insight", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(telegram_router)


@app.get("/")
def root():
    return {"status": "UZEX AI Agent running"}


@app.get("/health", response_model=HealthResponse)
def health():
    try:
        row = fetchone("SELECT COUNT(*) AS n FROM deals_enriched")
        ready = True
        stats = {"deals": int(row["n"]) if row else 0}
    except Exception:
        ready = False
        stats = {}
    return HealthResponse(
        status="ok" if ready else "starting",
        database_ready=ready,
        llm_sql_enabled=ENABLE_LLM_SQL and bool(OPENAI_API_KEY),
        stats=stats,
    )


@app.get("/stats", response_model=StatsResponse)
def stats():
    row = fetchone(
        """
        SELECT COUNT(*) AS deals,
               MIN(deal_date) AS min_date,
               MAX(deal_date) AS max_date,
               ROUND(SUM(amount_uzs), 2) AS amount_uzs
        FROM deals_enriched
        """
    )
    years = fetchall(
        "SELECT year, COUNT(*) AS deals, ROUND(SUM(amount_uzs),2) AS amount_uzs FROM deals_enriched GROUP BY year ORDER BY year"
    )
    extra = fetchone(
        """
        SELECT
          (SELECT COUNT(*) FROM contracts) AS contracts,
          (SELECT COUNT(*) FROM participants) AS participants,
          (SELECT COUNT(*) FROM brokers) AS brokers
        """
    )
    return StatsResponse(
        stats={**(row or {}), **(extra or {}), "by_year": years},
        suggested_questions=SUGGESTED,
    )


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(400, "Empty question")
    return answer(req.question, req.language)


@app.get("/suggest")
def suggest():
    return SUGGESTED

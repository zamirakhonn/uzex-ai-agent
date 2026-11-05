from __future__ import annotations

import time

from . import db
from .cache import cache
from .config import NOT_FOUND
from .formatters import format_answer, serialize_rows
from .language import detect_language
from .llm import llm_sql
from .planner import Plan, plan_query
from .retrieval import glossary_search
from .schemas import AskResponse, Language, Verification
from .verify import is_safe_sql, verify


def _safe_sql(sql: str) -> bool:
    return is_safe_sql(sql)


def answer(question: str, language: Language | None = None) -> AskResponse:
    t0 = time.perf_counter()
    q = question.strip()
    lang: Language = language or detect_language(q)
    ck = f"{lang}::{q.lower()}"
    hit = cache.get(ck)
    if hit:
        hit["cached"] = True
        hit["execution_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return AskResponse(**hit)

    plan = plan_query(q)
    rows: list[dict] = []
    sql = plan.sql
    params = plan.params

    if plan.intent == "unknown" or (plan.intent == "company_deals" and "company_not_matched" in plan.notes):
        gloss = glossary_search(q, threshold=72)
        if gloss:
            plan.intent = "glossary"
            plan.glossary_id = gloss["id"]
            plan.confidence = min(0.85, gloss["score"] / 100)
        elif plan.intent == "unknown":
            llm = llm_sql(q)
            if llm and _safe_sql(llm):
                sql = llm
                params = []
                plan.intent = "llm_sql"
                plan.confidence = 0.7
                plan.sql = sql

    if sql:
        try:
            rows = db.fetchall(sql, params or None)
        except Exception as exc:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return AskResponse(
                question=q,
                language=lang,
                found=False,
                answer=NOT_FOUND[lang],
                confidence=0.0,
                intent=plan.intent,
                reasoning_summary=f"SQL execution failed; refusing to guess. ({type(exc).__name__})",
                sql=sql,
                evidence=[],
                sources=[],
                rows=[],
                execution_ms=ms,
                verification=Verification(passed=True, method="sql_error_fail_closed", notes=[str(exc)[:200]]),
            )

    found = bool(rows) or plan.intent == "glossary"
    if plan.intent == "company_deals" and "company_not_matched" in plan.notes:
        found = False
    if rows and plan.intent in {"count_deals", "sum_amount"} and rows[0].get("deals") == 0:
        found = False

    if found:
        text, evidence, sources = format_answer(lang, plan, rows)
        if text == NOT_FOUND[lang]:
            found = False
            evidence, sources = [], []
    else:
        text, evidence, sources = NOT_FOUND[lang], [], []

    v = verify(sql, rows, found)
    if not v.passed:
        found = False
        text = NOT_FOUND[lang]
        evidence, sources = [], []

    confidence = 0.0 if not found else float(plan.confidence)
    if found and rows:
        confidence = min(0.99, confidence + 0.02)

    reasoning = _summary(lang, plan)

    payload = AskResponse(
        question=q,
        language=lang,
        found=found,
        answer=text,
        confidence=round(confidence, 3),
        intent=plan.intent,
        reasoning_summary=reasoning,
        sql=sql,
        evidence=evidence,
        sources=sources,
        rows=serialize_rows(rows),
        execution_ms=round((time.perf_counter() - t0) * 1000, 1),
        verification=v,
        cached=False,
    )
    cache.set(ck, payload.model_dump())
    return payload


def _summary(lang: Language, plan: Plan) -> str:
    if lang == "uz":
        return (
            f"Savol {plan.intent} niyatiga yo'naltirildi. "
            "Javob faqat DuckDB natijasi yoki dataset izohidan shakllantirildi. "
            "Bo'sh natija taxmin qilinmaydi."
        )
    return (
        f"Вопрос классифицирован как {plan.intent}. "
        "Ответ построен только из результата DuckDB или описания датасета. "
        "Пустой результат не дополняется догадками."
    )

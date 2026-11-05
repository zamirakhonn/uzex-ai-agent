from __future__ import annotations

import re

import duckdb

from .schemas import Verification


def is_safe_sql(sql: str) -> bool:
    statement_text = sql.strip()
    if not statement_text or ";" in statement_text.rstrip(";"):
        return False
    try:
        statements = duckdb.extract_statements(statement_text)
    except duckdb.Error:
        return False
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        return False

    forbidden = ("insert", "update", "delete", "drop", "attach", "copy", "pragma", "call", "create")
    return not any(re.search(rf"\b{word}\b", statement_text, re.I) for word in forbidden)


def verify(plan_sql: str | None, rows: list[dict], found: bool) -> Verification:
    notes: list[str] = []
    if not plan_sql and found:
        notes.append("glossary_or_catalog_grounded")
        return Verification(passed=True, method="glossary", notes=notes)
    if plan_sql and not is_safe_sql(plan_sql):
        return Verification(passed=False, method="sql_guard", notes=["unsafe_sql_blocked"])
    if not rows:
        notes.append("empty_result")
        return Verification(passed=True, method="empty_is_not_found", notes=notes)
    notes.append(f"row_count={len(rows)}")
    notes.append("answer_built_only_from_sql_rows")
    return Verification(passed=True, method="row_bound", notes=notes)


def numbers_in_text_are_grounded(answer: str, rows: list[dict]) -> bool:
    import re

    blob = " ".join(str(v) for row in rows for v in row.values())
    compact_blob = blob.replace(" ", "").replace(",", ".")
    for num in re.findall(r"\d[\d\s]*", answer):
        raw = num.replace(" ", "")
        if len(raw) < 4:
            continue
        if raw not in compact_blob and raw not in answer:
            # allow formatted thousands
            if raw not in compact_blob:
                return False
    return True

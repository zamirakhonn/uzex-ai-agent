from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .catalog import EntityHit, catalog

MONTHS = {
    "январ": 1, "yanvar": 1, "january": 1,
    "феврал": 2, "fevral": 2, "february": 2,
    "март": 3, "mart": 3, "march": 3,
    "апрел": 4, "aprel": 4, "april": 4,
    "май": 5, "мая": 5, "may": 5,
    "июн": 6, "iyun": 6, "june": 6,
    "июл": 7, "iyul": 7, "july": 7,
    "август": 8, "avgust": 8, "august": 8,
    "сентябр": 9, "sentyabr": 9, "september": 9,
    "октябр": 10, "oktabr": 10, "october": 10,
    "ноябр": 11, "noyabr": 11, "november": 11,
    "декабр": 12, "dekabr": 12, "december": 12,
}

STATUS_MAP = [
    (r"аннулир|bekor|cancel", "Аннулирован(Не оплачен)"),
    (r"частичн|qisman|partial", "Исполнен(Частично)"),
    (r"исполнен|ijro etilgan|bajarilgan", "Исполнен"),
    (r"не подписан|imzolanmagan", "Не подписан"),
    (r"заключен", "Заключен"),
    (r"ждёт оплату|to'?lov kutil", "Ждёт оплату"),
    (r"оплачен|to'?langan", "Оплачен"),
    (r"\bновый\b|\byangi\b", "Новый"),
]


@dataclass
class Extracted:
    years: list[int] = field(default_factory=list)
    month: int | None = None
    day: int | None = None
    exact_date: date | None = None
    inns: list[str] = field(default_factory=list)
    deal_ids: list[int] = field(default_factory=list)
    contract_ids: list[int] = field(default_factory=list)
    broker_codes: list[str] = field(default_factory=list)
    companies: list[EntityHit] = field(default_factory=list)
    products: list[EntityHit] = field(default_factory=list)
    brokers: list[EntityHit] = field(default_factory=list)
    region: str | None = None
    status: str | None = None
    contract_kind: str | None = None
    contract_form: str | None = None
    limit: int = 5
    company_query: str | None = None


def extract(question: str) -> Extracted:
    q = question.strip()
    low = q.lower()
    out = Extracted()

    out.years = [int(y) for y in re.findall(r"\b(202[2-6])\b", q)]
    for name, num in MONTHS.items():
        if name in low:
            out.month = num
            break

    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](202[2-6])\b", q)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out.exact_date = date(y, mo, d)
            out.years = [y]
            out.month = mo
            out.day = d
        except ValueError:
            pass

    out.inns = re.findall(r"\b(\d{9})\b", q)
    out.broker_codes = [c.upper() for c in re.findall(r"\b(BK\d{3})\b", q, re.I)]
    out.deal_ids = [int(x) for x in re.findall(r"\b(1\d{5}|[2-6]\d{5})\b", q) if len(x) == 6 and not x.startswith("20")]
    # contract ids also 6 digits starting 10xxxx
    out.contract_ids = [int(x) for x in re.findall(r"\b(10\d{4})\b", q)]

    m = re.search(r"\b(top|eng\s+ko'?p|самы[ех]|первых?)\s+(\d{1,2})\b", low)
    if m:
        out.limit = max(1, min(int(m.group(2)), 20))
    m = re.search(r"\b(\d{1,2})\s*(ta|шт|компаний|kompaniya)", low)
    if m and int(m.group(1)) <= 20:
        out.limit = int(m.group(1))

    for pat, status in STATUS_MAP:
        if re.search(pat, low, re.I):
            out.status = status
            break
    if out.status is None and re.search(
        r"(?:holat|status).{0,24}\btuzilgan\b|\btuzilgan\b.{0,24}(?:holat|status)",
        low,
        re.I,
    ):
        out.status = "Заключен"

    if re.search(r"eksport|экспорт", low):
        out.contract_kind = "Экспортный"
    elif re.search(r"ichki|внутренн", low):
        out.contract_kind = "Внутренний"
    if re.search(r"\bspot\b|спот", low):
        out.contract_form = "Спот"
    elif re.search(r"forvard|форвард", low):
        out.contract_form = "Форвард"
    elif re.search(r"fyucher|фьючерс", low):
        out.contract_form = "Фьючерс"

    quoted = re.findall(r"[\"«](.+?)[\"»]", q)
    company_bits = quoted[:]
    m = re.search(
        r"(kompaniya|компания|tashkilot|организация|sotuvchi|продавец|xaridor|покупатель)\s+(.+)$",
        q,
        re.I,
    )
    if m:
        company_bits.append(m.group(2))
    m = re.search(r"^(.+?)\s+(kompaniyasi|компании|ning bitim)", q, re.I)
    if m:
        company_bits.append(m.group(1))

    seen_inn = set(out.inns)
    for bit in company_bits:
        hits = catalog.find_company(bit)
        for h in hits:
            if h.key not in seen_inn:
                out.companies.append(h)
                seen_inn.add(h.key)
        if hits:
            out.company_query = bit
        elif bit and not hits:
            out.company_query = bit

    # If the question looks like a named entity search without quotes
    if not out.companies and not out.inns:
        # avoid matching generic words
        generic = re.search(
            r"\b(bitim|сделк|nechta|сколько|eng |сам|qancha|сумм|year|yil|год)\b",
            low,
        )
        leftover = re.sub(
            r"\b(202[2-6]|yilda|году|январ\w*|yanvar|fevral|март\w*|nechta|сколько|сделок|bitim\w*|qilgan|kompaniya\w*|компани\w*)\b",
            " ",
            q,
            flags=re.I,
        )
        leftover = re.sub(r"\s+", " ", leftover).strip()
        if leftover and len(leftover) >= 5 and not generic:
            hits = catalog.find_company(leftover)
            if hits:
                out.companies.extend(hits)
                out.company_query = leftover

    if out.inns:
        # resolve names later via SQL
        pass

    for code in out.broker_codes:
        hits = catalog.find_broker(code)
        out.brokers.extend(hits)
    if re.search(r"broker|брокер", low) and not out.brokers:
        # try remaining quoted
        for bit in quoted:
            out.brokers.extend(catalog.find_broker(bit))

    # products: explicit commodity words
    if re.search(r"tovar|товар|product|mahsulot|бензин|хлоп|карбамид|медь|полиэтилен|цемент", low):
        prod_q = q
        hits = catalog.find_product(prod_q)
        out.products = hits[:3]

    out.region = catalog.find_region(q)
    return out

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .entities import Extracted, extract
from .glossary import GLOSSARY
from .textnorm import normalize

INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("deal_lookup", [r"номер сделки", r"bitim raqami", r"сделка №", r"deal id", r"bitim №"]),
    ("contract_lookup", [r"контракт №", r"номер контракта", r"shartnoma raqami", r"contract"]),
    ("fx_rate", [r"курс", r"kurs", r"dollar kursi", r"usd"]),
    ("glossary", [r"что значит", r"nima demak", r"nima ma.?nosi", r"статус", r"holat nima", r"как считать", r"qanday hisob"]),
    ("dataset_stats", [r"nechta ishtirokchi", r"сколько участник", r"nechta broker", r"сколько брокер", r"nechta shartnoma", r"сколько контракт", r"dataset", r"статистика", r"umumiy"]),
    ("max_deal", [r"eng katta", r"самая крупн", r"максимальн", r"highest", r"eng yuqori summa", r"самая большая сумма"]),
    ("min_deal", [r"eng kichik", r"минимальн", r"самая маленьк"]),
    ("top_company", [r"eng ko\s*p bitim", r"больше всего сделок", r"top kompaniya", r"лидер", r"eng faol"]),
    ("top_product", [r"eng ko'?p sotil", r"популярн.*товар", r"top tovar", r"qaysi mahsulot"]),
    ("top_region", [r"qaysi viloyat", r"какой регион", r"eng ko'?p.*region", r"по регионам"]),
    ("top_broker", [r"eng ko'?p.*broker", r"какой брокер", r"faol broker"]),
    ("company_deals", [r"kompaniya", r"компани", r"инн", r"stir", r"sotuvchi", r"продавец", r"xaridor", r"покупател"]),
    ("count_deals", [r"nechta bitim", r"сколько сделок", r"soni", r"количество сделок", r"necha bitim"]),
    ("sum_amount", [r"umumiy summa", r"общая сумма", r"jami summa", r"оборот", r"hajmi so.?m", r"сумма сделок"]),
    ("status_breakdown", [r"holatlar", r"по статусам", r"statuslar", r"состояния"]),
    ("compare_years", [r"solishtir", r"сравни", r"versus", r"farqi", r"vs"]),
    ("product_stats", [r"бензин", r"хлоп", r"карбамид", r"масл", r"цемент", r"полиэтилен"]),
]


@dataclass
class Plan:
    intent: str
    sql: str | None
    params: list = field(default_factory=list)
    confidence: float = 0.5
    filters: dict = field(default_factory=dict)
    entities: Extracted | None = None
    glossary_id: str | None = None
    notes: list[str] = field(default_factory=list)


def _where(ent: Extracted, extra: list[str] | None = None) -> tuple[str, list]:
    clauses = extra[:] if extra else []
    params: list = []
    if ent.exact_date:
        clauses.append("deal_date = ?")
        params.append(ent.exact_date)
    else:
        if len(ent.years) == 1:
            clauses.append("year = ?")
            params.append(ent.years[0])
        elif len(ent.years) >= 2:
            clauses.append("year IN (?, ?)")
            params.extend(ent.years[:2])
        if ent.month:
            clauses.append("month = ?")
            params.append(ent.month)
        if ent.day:
            clauses.append("day = ?")
            params.append(ent.day)
    if ent.status:
        clauses.append("status = ?")
        params.append(ent.status)
    if ent.region:
        clauses.append("region = ?")
        params.append(ent.region)
    if ent.contract_kind:
        clauses.append("contract_kind = ?")
        params.append(ent.contract_kind)
    if ent.contract_form:
        clauses.append("contract_form = ?")
        params.append(ent.contract_form)
    inns = list(ent.inns)
    inns += [c.key for c in ent.companies]
    if inns:
        placeholders = ", ".join(["?"] * len(inns))
        clauses.append(f"(seller_inn IN ({placeholders}) OR buyer_inn IN ({placeholders}))")
        params.extend(inns)
        params.extend(inns)
    if ent.broker_codes:
        placeholders = ", ".join(["?"] * len(ent.broker_codes))
        clauses.append(f"(seller_broker IN ({placeholders}) OR buyer_broker IN ({placeholders}))")
        params.extend(ent.broker_codes * 2)
    if ent.products:
        like = f"%{ent.products[0].name.split()[0]}%"
        clauses.append("product_name ILIKE ?")
        params.append(like)
    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def detect_intent(question: str, ent: Extracted) -> str:
    q = normalize(question)
    if ent.deal_ids and re.search(r"сделк|bitim|номер", q):
        return "deal_lookup"
    if ent.contract_ids and re.search(r"контракт|shartnoma", q):
        return "contract_lookup"
    if len(ent.years) >= 2 and re.search(r"solishtir|сравн|farq", q):
        return "compare_years"
    for intent, pats in INTENT_PATTERNS:
        for p in pats:
            if re.search(p, q, re.I):
                return intent
    if ent.inns or ent.companies or ent.company_query:
        return "company_deals"
    if ent.deal_ids:
        return "deal_lookup"
    if ent.contract_ids:
        return "contract_lookup"
    if ent.exact_date and re.search(r"курс|kurs|dollar", q):
        return "fx_rate"
    if ent.years or ent.month:
        return "count_deals"
    return "unknown"


def plan_query(question: str) -> Plan:
    ent = extract(question)
    intent = detect_intent(question, ent)
    plan = Plan(intent=intent, sql=None, entities=ent, filters={})

    if intent == "glossary":
        plan.confidence = 0.9
        plan.glossary_id = _best_glossary(question)
        return plan

    if intent == "dataset_stats":
        plan.sql = """
            SELECT
              (SELECT COUNT(*) FROM deals_enriched) AS deals,
              (SELECT COUNT(*) FROM contracts) AS contracts,
              (SELECT COUNT(*) FROM participants) AS participants,
              (SELECT COUNT(*) FROM brokers) AS brokers,
              (SELECT MIN(deal_date) FROM deals_enriched) AS min_date,
              (SELECT MAX(deal_date) FROM deals_enriched) AS max_date
        """
        plan.confidence = 0.99
        return plan

    if intent == "fx_rate":
        if ent.exact_date:
            plan.sql = "SELECT rate_date, rate FROM usd_rates WHERE rate_date = ?"
            plan.params = [ent.exact_date]
        elif ent.years:
            plan.sql = """
                SELECT EXTRACT(YEAR FROM rate_date)::INTEGER AS year, ROUND(AVG(rate), 2) AS avg_rate,
                       MIN(rate) AS min_rate, MAX(rate) AS max_rate
                FROM usd_rates WHERE year(rate_date) = ?
                GROUP BY 1
            """
            plan.params = [ent.years[0]]
        else:
            plan.sql = """
                SELECT MIN(rate_date) AS min_date, MAX(rate_date) AS max_date,
                       ROUND(AVG(rate), 2) AS avg_rate, MIN(rate) AS min_rate, MAX(rate) AS max_rate
                FROM usd_rates
            """
        plan.confidence = 0.97
        return plan

    if intent == "deal_lookup":
        ids = ent.deal_ids or []
        if not ids:
            plan.intent = "unknown"
            plan.confidence = 0.2
            return plan
        placeholders = ", ".join(["?"] * len(ids))
        plan.sql = f"""
            SELECT deal_id, deal_date, deal_time, product_name, amount, amount_uzs, currency,
                   quantity, lot, unit, status, contract_id, contract_kind, contract_form,
                   seller_inn, seller_name, buyer_inn, buyer_name,
                   seller_broker, seller_broker_name, buyer_broker, buyer_broker_name,
                   region, source_file, auction_type
            FROM deals_enriched
            WHERE deal_id IN ({placeholders})
        """
        plan.params = ids
        plan.confidence = 0.99
        return plan

    if intent == "contract_lookup":
        ids = ent.contract_ids or []
        if not ids:
            plan.intent = "unknown"
            return plan
        placeholders = ", ".join(["?"] * len(ids))
        plan.sql = f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM deals_enriched d WHERE d.contract_id = c.contract_id) AS deals_count,
                   (SELECT ROUND(SUM(amount_uzs),2) FROM deals_enriched d WHERE d.contract_id = c.contract_id) AS deals_amount_uzs
            FROM contracts c
            WHERE contract_id IN ({placeholders})
        """
        plan.params = ids
        plan.confidence = 0.98
        return plan

    if intent == "max_deal":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT deal_id, deal_date, product_name, amount, amount_uzs, currency, quantity, unit,
                   seller_name, seller_inn, buyer_name, buyer_inn, contract_id, status, region, source_file
            FROM deals_enriched
            {where}
            ORDER BY amount_uzs DESC NULLS LAST
            LIMIT 1
        """
        plan.params = params
        plan.confidence = 0.96
        return plan

    if intent == "min_deal":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT deal_id, deal_date, product_name, amount, amount_uzs, currency, quantity, unit,
                   seller_name, seller_inn, buyer_name, buyer_inn, contract_id, status, region, source_file
            FROM deals_enriched
            {where}
            ORDER BY amount_uzs ASC NULLS LAST
            LIMIT 1
        """
        plan.params = params
        plan.confidence = 0.95
        return plan

    if intent == "top_company":
        where, params = _where(ent)
        limit = ent.limit or 5
        plan.sql = f"""
            WITH parties AS (
              SELECT seller_inn AS inn, seller_name AS name, 'seller' AS role, amount_uzs
              FROM deals_enriched {where}
              UNION ALL
              SELECT buyer_inn, buyer_name, 'buyer', amount_uzs
              FROM deals_enriched {where}
            )
            SELECT inn, name, COUNT(*) AS deals, ROUND(SUM(amount_uzs), 2) AS amount_uzs
            FROM parties
            WHERE inn IS NOT NULL
            GROUP BY 1, 2
            ORDER BY deals DESC, amount_uzs DESC
            LIMIT {int(limit)}
        """
        plan.params = params + params
        plan.confidence = 0.94
        return plan

    if intent == "top_product":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT COALESCE(contract_product, product_name) AS product, COUNT(*) AS deals,
                   ROUND(SUM(amount_uzs), 2) AS amount_uzs
            FROM deals_enriched
            {where}
            GROUP BY 1
            ORDER BY deals DESC
            LIMIT 10
        """
        plan.params = params
        plan.confidence = 0.92
        return plan

    if intent == "top_region":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT region, COUNT(*) AS deals, ROUND(SUM(amount_uzs), 2) AS amount_uzs
            FROM deals_enriched
            {where}
            GROUP BY 1
            ORDER BY deals DESC
            LIMIT 14
        """
        plan.params = params
        plan.confidence = 0.93
        return plan

    if intent == "top_broker":
        where, params = _where(ent)
        plan.sql = f"""
            WITH b AS (
              SELECT seller_broker AS code, seller_broker_name AS name FROM deals_enriched {where}
              UNION ALL
              SELECT buyer_broker, buyer_broker_name FROM deals_enriched {where}
            )
            SELECT code, name, COUNT(*) AS deals
            FROM b
            WHERE code IS NOT NULL
            GROUP BY 1, 2
            ORDER BY deals DESC
            LIMIT 10
        """
        plan.params = params + params
        plan.confidence = 0.92
        return plan

    if intent == "company_deals":
        inns = ent.inns + [c.key for c in ent.companies]
        if not inns:
            plan.confidence = 0.15
            plan.notes.append("company_not_matched")
            return plan
        placeholders = ", ".join(["?"] * len(inns))
        date_where, date_params = _where(
            Extracted(
                years=ent.years,
                month=ent.month,
                exact_date=ent.exact_date,
                status=ent.status,
                contract_kind=ent.contract_kind,
                contract_form=ent.contract_form,
            )
        )
        extra = date_where.replace(" WHERE ", " AND ") if date_where else ""
        plan.sql = f"""
            SELECT
              p.inn, p.name, p.role,
              COUNT(*) FILTER (WHERE d.seller_inn = p.inn) AS as_seller,
              COUNT(*) FILTER (WHERE d.buyer_inn = p.inn) AS as_buyer,
              COUNT(*) AS deals,
              ROUND(SUM(d.amount_uzs), 2) AS amount_uzs
            FROM deals_enriched d
            JOIN participants p ON p.inn IN ({placeholders})
            WHERE (d.seller_inn = p.inn OR d.buyer_inn = p.inn) {extra}
            GROUP BY 1, 2, 3
        """
        plan.params = inns + date_params
        plan.confidence = 0.97 if ent.inns or (ent.companies and ent.companies[0].score >= 90) else 0.88
        return plan

    if intent == "sum_amount":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT COUNT(*) AS deals,
                   ROUND(SUM(amount_uzs), 2) AS amount_uzs,
                   ROUND(SUM(CASE WHEN currency = 'Доллар США' THEN amount ELSE 0 END), 2) AS amount_usd,
                   COUNT(*) FILTER (WHERE status = 'Аннулирован(Не оплачен)') AS cancelled,
                   MIN(deal_date) AS min_date,
                   MAX(deal_date) AS max_date
            FROM deals_enriched
            {where}
        """
        plan.params = params
        plan.confidence = 0.96
        return plan

    if intent == "status_breakdown":
        where, params = _where(ent)
        plan.sql = f"""
            SELECT status, COUNT(*) AS deals, ROUND(SUM(amount_uzs), 2) AS amount_uzs
            FROM deals_enriched
            {where}
            GROUP BY 1
            ORDER BY deals DESC
        """
        plan.params = params
        plan.confidence = 0.97
        return plan

    if intent == "compare_years":
        years = ent.years[:2] if len(ent.years) >= 2 else [2024, 2025]
        plan.sql = """
            SELECT year, COUNT(*) AS deals, ROUND(SUM(amount_uzs), 2) AS amount_uzs
            FROM deals_enriched
            WHERE year IN (?, ?)
            GROUP BY year
            ORDER BY year
        """
        plan.params = years
        plan.confidence = 0.95
        return plan

    if intent in {"count_deals", "product_stats"}:
        where, params = _where(ent)
        plan.sql = f"""
            SELECT COUNT(*) AS deals,
                   ROUND(SUM(amount_uzs), 2) AS amount_uzs,
                   COUNT(DISTINCT seller_inn) AS sellers,
                   COUNT(DISTINCT buyer_inn) AS buyers,
                   MIN(deal_date) AS min_date,
                   MAX(deal_date) AS max_date
            FROM deals_enriched
            {where}
        """
        plan.params = params
        plan.confidence = 0.97 if ent.years or ent.month or ent.products else 0.8
        plan.intent = "count_deals"
        return plan

    plan.confidence = 0.2
    return plan


def _best_glossary(question: str) -> str | None:
    q = normalize(question)
    best_id = None
    best = 0
    for item in GLOSSARY:
        score = sum(1 for tok in item["keys"].split() if tok in q)
        if score > best:
            best = score
            best_id = item["id"]
    return best_id

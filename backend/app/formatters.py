from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from .config import NOT_FOUND
from .glossary import GLOSSARY
from .planner import Plan
from .schemas import EvidenceItem, Language


def fmt_num(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(n - round(n)) < 1e-6:
        return f"{int(round(n)):,}".replace(",", " ")
    return f"{n:,.2f}".replace(",", " ")


def _cell(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def serialize_rows(rows: list[dict], limit: int = 25) -> list[dict]:
    out = []
    for row in rows[:limit]:
        out.append({k: _cell(v) for k, v in row.items()})
    return out


def evidence_from_row(row: dict, lang: Language) -> list[EvidenceItem]:
    labels_uz = {
        "deal_id": "Bitim raqami",
        "contract_id": "Shartnoma",
        "deal_date": "Sana",
        "seller_name": "Sotuvchi",
        "seller_inn": "Sotuvchi STIR",
        "buyer_name": "Xaridor",
        "buyer_inn": "Xaridor STIR",
        "amount": "Summa (valyuta)",
        "amount_uzs": "Summa (so'm)",
        "currency": "Valyuta",
        "product_name": "Tovar",
        "status": "Holat",
        "region": "Hudud",
        "source_file": "Fayl",
        "seller_broker": "Sotuvchi broker",
        "name": "Nomi",
        "inn": "STIR",
        "deals": "Bitimlar",
        "rate": "USD kursi",
        "rate_date": "Kurs sanasi",
    }
    labels_ru = {
        "deal_id": "Номер сделки",
        "contract_id": "Контракт",
        "deal_date": "Дата",
        "seller_name": "Продавец",
        "seller_inn": "ИНН продавца",
        "buyer_name": "Покупатель",
        "buyer_inn": "ИНН покупателя",
        "amount": "Сумма (валюта)",
        "amount_uzs": "Сумма (сум)",
        "currency": "Валюта",
        "product_name": "Товар",
        "status": "Статус",
        "region": "Регион",
        "source_file": "Файл",
        "seller_broker": "Брокер продавца",
        "name": "Наименование",
        "inn": "ИНН",
        "deals": "Сделки",
        "rate": "Курс USD",
        "rate_date": "Дата курса",
    }
    labels = labels_uz if lang == "uz" else labels_ru
    items = []
    for key, label in labels.items():
        if key in row and row[key] not in (None, ""):
            items.append(EvidenceItem(label=label, value=str(fmt_num(row[key]) if not isinstance(row[key], str) else row[key])))
    return items


def not_found(lang: Language) -> str:
    return NOT_FOUND[lang]


def format_answer(lang: Language, plan: Plan, rows: list[dict]) -> tuple[str, list[EvidenceItem], list[str]]:
    sources = ["deals_enriched"]
    if plan.intent == "glossary":
        item = next((g for g in GLOSSARY if g["id"] == plan.glossary_id), GLOSSARY[0])
        return item[lang], [EvidenceItem(label="Source", value="data/README.md")], ["data/README.md"]

    if not rows:
        return not_found(lang), [], []

    row = rows[0]
    ev = evidence_from_row(row, lang)

    if plan.intent == "dataset_stats":
        sources = ["deals_*.csv", "contracts.csv", "participants.csv", "brokers.csv"]
        if lang == "uz":
            ans = (
                f"Datasetda {fmt_num(row['deals'])} ta bitim, {fmt_num(row['contracts'])} ta shartnoma, "
                f"{fmt_num(row['participants'])} ta ishtirokchi va {fmt_num(row['brokers'])} ta broker bor. "
                f"Sana oralig'i: {fmt_num(row['min_date'])} — {fmt_num(row['max_date'])}."
            )
        else:
            ans = (
                f"В датасете {fmt_num(row['deals'])} сделок, {fmt_num(row['contracts'])} контрактов, "
                f"{fmt_num(row['participants'])} участников и {fmt_num(row['brokers'])} брокеров. "
                f"Период: {fmt_num(row['min_date'])} — {fmt_num(row['max_date'])}."
            )
        return ans, ev, sources

    if plan.intent == "fx_rate":
        sources = ["usd_rates.csv"]
        if "rate" in row:
            if lang == "uz":
                ans = f"{fmt_num(row.get('rate_date'))} sanasida 1 USD = {fmt_num(row['rate'])} so'm."
            else:
                ans = f"На {fmt_num(row.get('rate_date'))} курс: 1 USD = {fmt_num(row['rate'])} сум."
        else:
            if lang == "uz":
                ans = (
                    f"USD kursi: o'rtacha {fmt_num(row.get('avg_rate'))} so'm, "
                    f"min {fmt_num(row.get('min_rate'))}, max {fmt_num(row.get('max_rate'))}."
                )
            else:
                ans = (
                    f"Курс USD: средний {fmt_num(row.get('avg_rate'))} сум, "
                    f"min {fmt_num(row.get('min_rate'))}, max {fmt_num(row.get('max_rate'))}."
                )
        return ans, ev, sources

    if plan.intent in {"deal_lookup", "max_deal", "min_deal"}:
        sources = [str(row.get("source_file") or "deals_*.csv")]
        kind = "Bitim" if lang == "uz" else "Сделка"
        if lang == "uz":
            ans = (
                f"{kind} #{fmt_num(row.get('deal_id'))}: {row.get('product_name')}. "
                f"Summa {fmt_num(row.get('amount'))} {row.get('currency') or ''} "
                f"({fmt_num(row.get('amount_uzs'))} so'm), sana {fmt_num(row.get('deal_date'))}. "
                f"Sotuvchi: {row.get('seller_name')} (STIR {row.get('seller_inn')}), "
                f"xaridor: {row.get('buyer_name')} (STIR {row.get('buyer_inn')}). "
                f"Holat: {row.get('status')}."
            )
        else:
            ans = (
                f"{kind} №{fmt_num(row.get('deal_id'))}: {row.get('product_name')}. "
                f"Сумма {fmt_num(row.get('amount'))} {row.get('currency') or ''} "
                f"({fmt_num(row.get('amount_uzs'))} сум), дата {fmt_num(row.get('deal_date'))}. "
                f"Продавец: {row.get('seller_name')} (ИНН {row.get('seller_inn')}), "
                f"покупатель: {row.get('buyer_name')} (ИНН {row.get('buyer_inn')}). "
                f"Статус: {row.get('status')}."
            )
        return ans, ev, sources

    if plan.intent == "contract_lookup":
        sources = ["contracts.csv"]
        if lang == "uz":
            ans = (
                f"Shartnoma #{fmt_num(row.get('contract_id'))}: {row.get('product_name')}, "
                f"valyuta {row.get('currency')}, sotuvchi STIR {row.get('seller_inn')}. "
                f"Bitimlar: {fmt_num(row.get('deals_count'))}."
            )
        else:
            ans = (
                f"Контракт №{fmt_num(row.get('contract_id'))}: {row.get('product_name')}, "
                f"валюта {row.get('currency')}, ИНН продавца {row.get('seller_inn')}. "
                f"Сделок: {fmt_num(row.get('deals_count'))}."
            )
        return ans, ev, sources

    if plan.intent == "company_deals":
        sources = ["participants.csv", "deals_*.csv"]
        parts = []
        for r in rows:
            if lang == "uz":
                parts.append(
                    f"{r.get('name')} (STIR {r.get('inn')}): {fmt_num(r.get('deals'))} ta bitim "
                    f"(sotuvchi: {fmt_num(r.get('as_seller'))}, xaridor: {fmt_num(r.get('as_buyer'))}), "
                    f"jami {fmt_num(r.get('amount_uzs'))} so'm."
                )
            else:
                parts.append(
                    f"{r.get('name')} (ИНН {r.get('inn')}): {fmt_num(r.get('deals'))} сделок "
                    f"(продавец: {fmt_num(r.get('as_seller'))}, покупатель: {fmt_num(r.get('as_buyer'))}), "
                    f"итого {fmt_num(r.get('amount_uzs'))} сум."
                )
        ev = evidence_from_row(rows[0], lang)
        return " ".join(parts), ev, sources

    if plan.intent == "top_company":
        sources = ["participants.csv", "deals_*.csv"]
        lines = []
        for i, r in enumerate(rows[:5], 1):
            lines.append(f"{i}. {r.get('name')} — {fmt_num(r.get('deals'))} / {fmt_num(r.get('amount_uzs'))} UZS")
        if lang == "uz":
            ans = "Eng ko'p bitimda qatnashgan kompaniyalar:\n" + "\n".join(lines)
        else:
            ans = "Компании с наибольшим числом сделок:\n" + "\n".join(lines)
        return ans, evidence_from_row(rows[0], lang), sources

    if plan.intent in {"top_product", "top_region", "top_broker", "status_breakdown", "compare_years"}:
        key = {"top_product": "product", "top_region": "region", "top_broker": "name", "status_breakdown": "status", "compare_years": "year"}[plan.intent]
        lines = [f"{r.get(key)} — {fmt_num(r.get('deals'))}" for r in rows[:10]]
        title = {
            "uz": {
                "top_product": "Mahsulotlar bo'yicha bitimlar",
                "top_region": "Hududlar bo'yicha bitimlar",
                "top_broker": "Brokerlar",
                "status_breakdown": "Holatlar",
                "compare_years": "Yillar solishtirmasi",
            },
            "ru": {
                "top_product": "Сделки по товарам",
                "top_region": "Сделки по регионам",
                "top_broker": "Брокеры",
                "status_breakdown": "Статусы",
                "compare_years": "Сравнение лет",
            },
        }[lang][plan.intent]
        sources = ["deals_*.csv"]
        return title + ":\n" + "\n".join(lines), evidence_from_row(rows[0], lang), sources

    # count / sum
    sources = ["deals_*.csv"]
    if lang == "uz":
        ans = (
            f"Tanlangan filtr bo'yicha {fmt_num(row.get('deals'))} ta bitim. "
            f"Jami summa: {fmt_num(row.get('amount_uzs'))} so'm "
            f"(barcha valyutalar usd_rates orqali so'mga keltirilgan). "
            f"Sana: {fmt_num(row.get('min_date'))} — {fmt_num(row.get('max_date'))}."
        )
        if row.get("cancelled") is not None:
            ans += f" Bekor qilingan: {fmt_num(row.get('cancelled'))}."
    else:
        ans = (
            f"По выбранному фильтру {fmt_num(row.get('deals'))} сделок. "
            f"Сумма: {fmt_num(row.get('amount_uzs'))} сум "
            f"(экспорт пересчитан по usd_rates). "
            f"Период: {fmt_num(row.get('min_date'))} — {fmt_num(row.get('max_date'))}."
        )
        if row.get("cancelled") is not None:
            ans += f" Аннулировано: {fmt_num(row.get('cancelled'))}."
    if row.get("deals") == 0:
        return not_found(lang), [], sources
    return ans, ev, sources

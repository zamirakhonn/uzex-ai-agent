from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from . import db
from .config import FUZZY_COMPANY_THRESHOLD
from .textnorm import compact_legal, normalize


@dataclass
class EntityHit:
    kind: str
    key: str
    name: str
    score: float
    extra: dict


class Catalog:
    def __init__(self) -> None:
        self.companies: list[tuple[str, str, dict]] = []
        self.brokers: list[tuple[str, str, dict]] = []
        self.products: list[tuple[str, str, dict]] = []
        self.regions: list[str] = []
        self.ready = False

    def load(self) -> None:
        companies = db.fetchall("SELECT inn, name, region, role, activity FROM participants")
        self.companies = [
            (compact_legal(r["name"]), r["name"], r) for r in companies if r.get("name")
        ]
        brokers = db.fetchall("SELECT code, name, inn, region FROM brokers")
        self.brokers = [(normalize(r["name"]), r["name"], r) for r in brokers]
        products = db.fetchall(
            """
            SELECT product_name, COUNT(*) AS n
            FROM contracts
            WHERE product_name IS NOT NULL
            GROUP BY 1
            ORDER BY n DESC
            """
        )
        self.products = [(normalize(r["product_name"]), r["product_name"], r) for r in products]
        regions = db.fetchall("SELECT DISTINCT region FROM deals_enriched WHERE region IS NOT NULL")
        self.regions = [r["region"] for r in regions]
        self.ready = True

    def find_company(self, query: str, limit: int = 5) -> list[EntityHit]:
        q = compact_legal(query)
        if len(q) < 3:
            return []
        choices = [c[0] for c in self.companies]
        raw = process.extract(q, choices, scorer=fuzz.WRatio, limit=limit)
        hits: list[EntityHit] = []
        seen: set[str] = set()
        for _text, score, idx in raw:
            if score < FUZZY_COMPANY_THRESHOLD:
                continue
            _, name, extra = self.companies[idx]
            inn = extra["inn"]
            if inn in seen:
                continue
            seen.add(inn)
            hits.append(EntityHit("company", inn, name, float(score), extra))
        return hits

    def find_broker(self, query: str) -> list[EntityHit]:
        q = normalize(query)
        code_q = q.upper().replace(" ", "")
        if code_q.startswith("BK"):
            row = db.fetchone("SELECT * FROM brokers WHERE code = ?", [code_q[:5] if len(code_q) >= 5 else code_q])
            if row:
                return [EntityHit("broker", row["code"], row["name"], 100.0, row)]
        choices = [b[0] for b in self.brokers]
        raw = process.extract(q, choices, scorer=fuzz.WRatio, limit=3)
        hits = []
        for _t, score, idx in raw:
            if score < 80:
                continue
            _, name, extra = self.brokers[idx]
            hits.append(EntityHit("broker", extra["code"], name, float(score), extra))
        return hits

    def find_product(self, query: str) -> list[EntityHit]:
        q = normalize(query)
        if len(q) < 3:
            return []
        choices = [p[0] for p in self.products]
        raw = process.extract(q, choices, scorer=fuzz.partial_ratio, limit=5)
        hits = []
        for _t, score, idx in raw:
            if score < 78:
                continue
            _, name, extra = self.products[idx]
            hits.append(EntityHit("product", name, name, float(score), extra))
        return hits

    def find_region(self, query: str) -> str | None:
        q = compact_legal(query)
        best = process.extractOne(q, [compact_legal(r) for r in self.regions], scorer=fuzz.WRatio)
        if best and best[1] >= 80:
            return self.regions[best[2]]
        return None


catalog = Catalog()

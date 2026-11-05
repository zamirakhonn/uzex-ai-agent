from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

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
        self._loaded: set[str] = set()
        self._load_lock = RLock()

    def load(self) -> None:
        self._load_companies()
        self._load_brokers()
        self._load_products()
        self._load_regions()

    def _mark_loaded(self, section: str) -> None:
        self._loaded.add(section)
        self.ready = len(self._loaded) == 4

    def _load_companies(self) -> None:
        if "companies" in self._loaded:
            return
        with self._load_lock:
            if "companies" not in self._loaded:
                rows = db.fetchall("SELECT inn, name FROM participants WHERE name IS NOT NULL")
                self.companies = [
                    (compact_legal(row["name"]), row["name"], {"inn": row["inn"]})
                    for row in rows
                ]
                self._mark_loaded("companies")

    def _load_brokers(self) -> None:
        if "brokers" in self._loaded:
            return
        with self._load_lock:
            if "brokers" not in self._loaded:
                rows = db.fetchall("SELECT code, name, inn, region FROM brokers")
                self.brokers = [(normalize(row["name"]), row["name"], row) for row in rows]
                self._mark_loaded("brokers")

    def _load_products(self) -> None:
        if "products" in self._loaded:
            return
        with self._load_lock:
            if "products" not in self._loaded:
                rows = db.fetchall(
                    """
                    SELECT product_name, COUNT(*) AS n
                    FROM contracts
                    WHERE product_name IS NOT NULL
                    GROUP BY 1
                    ORDER BY n DESC
                    """
                )
                self.products = [
                    (normalize(row["product_name"]), row["product_name"], row)
                    for row in rows
                ]
                self._mark_loaded("products")

    def _load_regions(self) -> None:
        if "regions" in self._loaded:
            return
        with self._load_lock:
            if "regions" not in self._loaded:
                rows = db.fetchall(
                    "SELECT DISTINCT region FROM deals_enriched WHERE region IS NOT NULL"
                )
                self.regions = [row["region"] for row in rows]
                self._mark_loaded("regions")

    def find_company(self, query: str, limit: int = 5) -> list[EntityHit]:
        q = compact_legal(query)
        if len(q) < 3:
            return []
        self._load_companies()
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
        self._load_brokers()
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
        self._load_products()
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
        self._load_regions()
        best = process.extractOne(q, [compact_legal(r) for r in self.regions], scorer=fuzz.WRatio)
        if best and best[1] >= 80:
            return self.regions[best[2]]
        return None


catalog = Catalog()

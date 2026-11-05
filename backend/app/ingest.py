from __future__ import annotations

import json
from pathlib import Path

import duckdb

from .config import DATA_DIR, DB_PATH
from .db import set_connection

DEAL_SELECT = """
SELECT
    TRY_CAST("Номер сделки" AS BIGINT) AS deal_id,
    TRY_STRPTIME(CAST("Дата сделки" AS VARCHAR), '%d.%m.%Y') AS deal_date,
    TRY_CAST("Время сделки" AS TIME) AS deal_time,
    "Тип торгов" AS auction_type,
    TRY_CAST("Количество" AS DOUBLE) AS quantity,
    TRY_CAST(REPLACE(CAST("Сумма сделки" AS VARCHAR), ' ', '') AS DOUBLE) AS amount,
    TRY_CAST(REPLACE(CAST("Стартовая цена" AS VARCHAR), ' ', '') AS DOUBLE) AS start_price,
    TRY_CAST("Номер контракта" AS BIGINT) AS contract_id,
    "Наименование товара" AS product_name,
    TRY_CAST("Лот" AS DOUBLE) AS lot,
    "Единица измерения" AS unit,
    "Регион" AS region,
    "Тип контракта" AS contract_kind,
    "Форма контракта" AS contract_form,
    "Состояние сделки" AS status,
    CAST("ИНН продавца" AS VARCHAR) AS seller_inn,
    CAST("ИНН покупателя" AS VARCHAR) AS buyer_inn,
    "Брокер продавца" AS seller_broker,
    "Брокер покупателя" AS buyer_broker,
    TRY_STRPTIME(NULLIF(CAST("Дата оплаты" AS VARCHAR), ''), '%d.%m.%Y') AS payment_date,
    TRY_STRPTIME(NULLIF(CAST("Дата поставки" AS VARCHAR), ''), '%d.%m.%Y') AS delivery_date,
    TRY_CAST(NULLIF(CAST("Поставлено" AS VARCHAR), '') AS DOUBLE) AS delivered
"""


def _csv_opts(path: Path) -> str:
    return (
        f"read_csv_auto('{path.as_posix()}', header=true, encoding='utf-8', "
        "sample_size=-1, all_varchar=true)"
    )


def build_database(force: bool = False) -> dict:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists() and force:
        DB_PATH.unlink()
        wal = Path(str(DB_PATH) + ".wal")
        if wal.exists():
            wal.unlink()

    if DB_PATH.exists() and not force:
        con = duckdb.connect(str(DB_PATH))
        set_connection(con)
        return _stats(con)

    files = {p.name: p for p in DATA_DIR.iterdir() if p.is_file() and not p.name.startswith(".")}
    deal_files = sorted(p for name, p in files.items() if name.startswith("deals_") and name.endswith(".csv"))
    if not deal_files:
        raise FileNotFoundError("No deals_*.csv files found in /data")

    con = duckdb.connect(str(DB_PATH))
    con.execute("PRAGMA threads=4")

    con.execute(
        f"""
        CREATE TABLE brokers AS
        SELECT
            "Код брокера" AS code,
            "Наименование" AS name,
            CAST("ИНН" AS VARCHAR) AS inn,
            "Регион" AS region
        FROM {_csv_opts(files['brokers.csv'])}
        """
    )

    con.execute(
        f"""
        CREATE TABLE participants AS
        SELECT
            CAST("ИНН" AS VARCHAR) AS inn,
            "Наименование" AS name,
            "Регион" AS region,
            "Вид деятельности" AS activity,
            "Роль" AS role,
            "Плательщик НДС" AS vat_payer
        FROM {_csv_opts(files['participants.csv'])}
        """
    )

    con.execute(
        f"""
        CREATE TABLE contracts AS
        SELECT
            TRY_CAST("Номер контракта" AS BIGINT) AS contract_id,
            "Наименование продукта" AS product_name,
            "Марка товара" AS brand,
            "Размер товара" AS size,
            "Сорт товара" AS grade,
            "Тип товара" AS type_attr,
            "Класс товара" AS class_attr,
            CAST("Код ТН ВЭД" AS VARCHAR) AS hs_code,
            "Группа товара" AS group_name,
            "Категория товара" AS category,
            "Отрасль промышленности" AS industry,
            "Единица измерения" AS unit,
            TRY_CAST("Лот" AS DOUBLE) AS lot,
            "Валюта" AS currency,
            TRY_CAST(REPLACE(CAST("Базисная цена" AS VARCHAR), ' ', '') AS DOUBLE) AS base_price,
            "Сумма залога" AS deposit,
            "Базис поставки" AS delivery_basis,
            "Регион" AS region,
            "Адрес склада" AS warehouse_address,
            "Тип торгов" AS auction_type,
            "Тип контракта" AS contract_kind,
            "Форма контракта" AS contract_form,
            TRY_CAST("Срок оплаты" AS INTEGER) AS payment_days,
            TRY_CAST("Срок поставки" AS INTEGER) AS delivery_days,
            "Упаковка" AS packaging,
            CAST("ИНН продавца" AS VARCHAR) AS seller_inn,
            TRY_STRPTIME(CAST("Дата регистрации" AS VARCHAR), '%d.%m.%Y') AS registered_at,
            TRY_STRPTIME(CAST("Действует до" AS VARCHAR), '%d.%m.%Y') AS valid_until
        FROM {_csv_opts(files['contracts.csv'])}
        """
    )

    con.execute(
        f"""
        CREATE TABLE usd_rates AS
        SELECT
            TRY_STRPTIME(CAST("Дата" AS VARCHAR), '%d.%m.%Y') AS rate_date,
            TRY_CAST("Курс" AS DOUBLE) AS rate
        FROM {_csv_opts(files['usd_rates.csv'])}
        WHERE "Дата" IS NOT NULL
        """
    )

    first = deal_files[0]
    year = int(first.stem.split("_")[1])
    con.execute(
        f"""
        CREATE TABLE deals AS
        {DEAL_SELECT},
        '{first.name}' AS source_file,
        {year} AS file_year
        FROM {_csv_opts(first)}
        WHERE 1=0
        """
    )

    for path in deal_files:
        year = int(path.stem.split("_")[1])
        con.execute(
            f"""
            INSERT INTO deals
            {DEAL_SELECT},
            '{path.name}' AS source_file,
            {year} AS file_year
            FROM {_csv_opts(path)}
            """
        )

    con.execute(
        """
        CREATE TABLE deals_enriched AS
        SELECT
            d.*,
            d.quantity * COALESCE(d.lot, 1) AS volume,
            CASE
                WHEN d.quantity IS NOT NULL AND COALESCE(d.lot, 1) > 0
                THEN d.amount / NULLIF(d.quantity * COALESCE(d.lot, 1), 0)
            END AS unit_price,
            c.currency,
            c.category,
            c.industry,
            c.group_name,
            c.hs_code,
            c.product_name AS contract_product,
            seller.name AS seller_name,
            seller.region AS seller_region,
            buyer.name AS buyer_name,
            buyer.region AS buyer_region,
            sb.name AS seller_broker_name,
            bb.name AS buyer_broker_name,
            r.rate AS usd_rate,
            CASE
                WHEN c.currency = 'Доллар США' AND r.rate IS NOT NULL THEN d.amount * r.rate
                ELSE d.amount
            END AS amount_uzs,
            EXTRACT(YEAR FROM d.deal_date)::INTEGER AS year,
            EXTRACT(MONTH FROM d.deal_date)::INTEGER AS month,
            EXTRACT(DAY FROM d.deal_date)::INTEGER AS day
        FROM deals d
        LEFT JOIN contracts c ON d.contract_id = c.contract_id
        LEFT JOIN participants seller ON d.seller_inn = seller.inn
        LEFT JOIN participants buyer ON d.buyer_inn = buyer.inn
        LEFT JOIN brokers sb ON d.seller_broker = sb.code
        LEFT JOIN brokers bb ON d.buyer_broker = bb.code
        LEFT JOIN usd_rates r ON d.deal_date = r.rate_date
        """
    )

    con.execute("CREATE INDEX idx_deals_date ON deals_enriched(deal_date)")
    con.execute("CREATE INDEX idx_deals_year ON deals_enriched(year)")
    con.execute("CREATE INDEX idx_deals_seller ON deals_enriched(seller_inn)")
    con.execute("CREATE INDEX idx_deals_buyer ON deals_enriched(buyer_inn)")
    con.execute("CREATE INDEX idx_deals_contract ON deals_enriched(contract_id)")
    con.execute("CREATE INDEX idx_deals_status ON deals_enriched(status)")
    con.execute("CREATE INDEX idx_deals_id ON deals_enriched(deal_id)")
    con.execute("CREATE INDEX idx_part_inn ON participants(inn)")
    con.execute("CREATE INDEX idx_brokers_code ON brokers(code)")
    con.execute("CREATE INDEX idx_contracts_id ON contracts(contract_id)")
    con.execute("CREATE INDEX idx_rates_date ON usd_rates(rate_date)")

    con.execute("ANALYZE")
    stats = _stats(con)
    (DB_PATH.parent / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    set_connection(con)
    return stats


def _stats(con: duckdb.DuckDBPyConnection) -> dict:
    row = con.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM deals_enriched) AS deals,
            (SELECT COUNT(*) FROM contracts) AS contracts,
            (SELECT COUNT(*) FROM participants) AS participants,
            (SELECT COUNT(*) FROM brokers) AS brokers,
            (SELECT COUNT(*) FROM usd_rates) AS usd_rates,
            (SELECT MIN(deal_date) FROM deals_enriched) AS min_date,
            (SELECT MAX(deal_date) FROM deals_enriched) AS max_date,
            (SELECT COUNT(*) FROM deals_enriched WHERE status = 'Исполнен') AS executed,
            (SELECT COUNT(*) FROM deals_enriched WHERE contract_kind = 'Экспортный') AS export_deals,
            (SELECT ROUND(SUM(amount_uzs), 2) FROM deals_enriched WHERE year IS NOT NULL) AS amount_uzs_total
        """
    ).fetchone()
    years = con.execute(
        """
        SELECT year, COUNT(*) AS deals, ROUND(SUM(amount_uzs), 2) AS amount_uzs
        FROM deals_enriched
        WHERE year IS NOT NULL
        GROUP BY year
        ORDER BY year
        """
    ).fetchall()
    return {
        "deals": int(row[0]),
        "contracts": int(row[1]),
        "participants": int(row[2]),
        "brokers": int(row[3]),
        "usd_rates": int(row[4]),
        "min_date": str(row[5]),
        "max_date": str(row[6]),
        "executed": int(row[7]),
        "export_deals": int(row[8]),
        "amount_uzs_total": float(row[9] or 0),
        "by_year": [{"year": int(y), "deals": int(c), "amount_uzs": float(a or 0)} for y, c, a in years],
        "db_path": str(DB_PATH),
        "db_mb": round(DB_PATH.stat().st_size / 1024 / 1024, 1) if DB_PATH.exists() else 0,
    }


if __name__ == "__main__":
    stats = build_database(force=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))

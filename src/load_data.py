#!/usr/bin/env python3
"""
UZEX AI Hackathon 2026 - Data Loader
"""

import duckdb
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = Path(__file__).parent.parent / "db" / "uzex.duckdb"

def main():
    print("=" * 60)
    print("UZEX Data Loader")
    print("=" * 60)

    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed old database: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH))

    # 1. BROKERS
    print("\n[1/5] Loading brokers...")
    con.execute("""
        CREATE TABLE brokers AS
        SELECT 
            "Код брокера" AS code,
            "Наименование" AS name,
            CAST("ИНН" AS VARCHAR) AS inn,
            "Регион" AS region
        FROM read_csv_auto(?, header=true)
    """, [str(DATA_DIR / "brokers.csv")])
    print(f"   → {con.execute('SELECT COUNT(*) FROM brokers').fetchone()[0]} brokers")

    # 2. PARTICIPANTS
    print("\n[2/5] Loading participants...")
    con.execute("""
        CREATE TABLE participants AS
        SELECT 
            CAST("ИНН" AS VARCHAR) AS inn,
            "Наименование" AS name,
            "Регион" AS region,
            "Вид деятельности" AS activity,
            "Роль" AS role,
            "Плательщик НДС" AS vat_payer
        FROM read_csv_auto(?, header=true)
    """, [str(DATA_DIR / "participants.csv")])
    print(f"   → {con.execute('SELECT COUNT(*) FROM participants').fetchone()[0]} participants")

    # 3. CONTRACTS
    print("\n[3/5] Loading contracts...")
    con.execute("""
        CREATE TABLE contracts AS
        SELECT 
            "Номер контракта" AS contract_id,
            "Наименование продукта" AS product_name,
            "Марка товара" AS brand,
            "Размер товара" AS size,
            "Сорт товара" AS grade,
            "Тип товара" AS type_attr,
            "Класс товара" AS class_attr,
            "Код ТН ВЭД" AS hs_code,
            "Группа товара" AS group_name,
            "Категория товара" AS category,
            "Отрасль промышленности" AS industry,
            "Единица измерения" AS unit,
            "Лот" AS lot,
            "Валюта" AS currency,
            TRY_CAST(REPLACE(CAST("Базисная цена" AS VARCHAR), ' ', '') AS DOUBLE) AS base_price,
            "Сумма залога" AS deposit,
            "Базис поставки" AS delivery_basis,
            "Регион" AS region,
            "Адрес склада" AS warehouse_address,
            "Тип торгов" AS auction_type,
            "Тип контракта" AS contract_type,
            "Форма контракта" AS form,
            "Срок оплаты" AS payment_days,
            "Срок поставки" AS delivery_days,
            "Упаковка" AS packaging,
            CAST("ИНН продавца" AS VARCHAR) AS seller_inn,
            "Дата регистрации" AS registered_at,
            "Действует до" AS valid_until
        FROM read_csv_auto(?, header=true)
    """, [str(DATA_DIR / "contracts.csv")])
    print(f"   → {con.execute('SELECT COUNT(*) FROM contracts').fetchone()[0]} contracts")

    # 4. USD RATES
    print("\n[4/5] Loading USD rates...")
    con.execute("""
        CREATE TABLE usd_rates AS
        SELECT 
            "Дата" AS rate_date,
            "Курс" AS rate
        FROM read_csv_auto(?, header=true)
        WHERE "Дата" IS NOT NULL
    """, [str(DATA_DIR / "usd_rates.csv")])
    print(f"   → {con.execute('SELECT COUNT(*) FROM usd_rates').fetchone()[0]} daily rates")

    # 5. DEALS
    print("\n[5/5] Loading deals...")
    deal_files = sorted(DATA_DIR.glob("deals_*.csv"))
    
    if not deal_files:
        print("   ⚠️  No deals_*.csv files found in data/ folder!")
        return

    # Create empty table
    first = deal_files[0]
    con.execute("""
        CREATE TABLE deals AS
        SELECT 
            "Номер сделки" AS deal_id,
            "Дата сделки" AS deal_date,
            "Время сделки" AS deal_time,
            "Тип торгов" AS auction_type,
            "Количество" AS quantity,
            TRY_CAST(REPLACE(CAST("Сумма сделки" AS VARCHAR), ' ', '') AS DOUBLE) AS amount,
            TRY_CAST(REPLACE(CAST("Стартовая цена" AS VARCHAR), ' ', '') AS DOUBLE) AS start_price,
            "Номер контракта" AS contract_id,
            "Наименование товара" AS product_name,
            "Лот" AS lot,
            "Единица измерения" AS unit,
            "Регион" AS region,
            "Тип контракта" AS contract_type,
            "Форма контракта" AS form,
            "Состояние сделки" AS status,
            CAST("ИНН продавца" AS VARCHAR) AS seller_inn,
            CAST("ИНН покупателя" AS VARCHAR) AS buyer_inn,
            "Брокер продавца" AS seller_broker,
            "Брокер покупателя" AS buyer_broker,
            "Дата оплаты" AS payment_date,
            "Дата поставки" AS delivery_date,
            "Поставлено" AS delivered
        FROM read_csv_auto(?, header=true)
        WHERE 1=0
    """, [str(first)])

    for f in deal_files:
        print(f"   Loading {f.name} ...", end=" ", flush=True)
        con.execute("""
            INSERT INTO deals
            SELECT 
                "Номер сделки" AS deal_id,
                "Дата сделки" AS deal_date,
                "Время сделки" AS deal_time,
                "Тип торгов" AS auction_type,
                "Количество" AS quantity,
                TRY_CAST(REPLACE(CAST("Сумма сделки" AS VARCHAR), ' ', '') AS DOUBLE) AS amount,
                TRY_CAST(REPLACE(CAST("Стартовая цена" AS VARCHAR), ' ', '') AS DOUBLE) AS start_price,
                "Номер контракта" AS contract_id,
                "Наименование товара" AS product_name,
                "Лот" AS lot,
                "Единица измерения" AS unit,
                "Регион" AS region,
                "Тип контракта" AS contract_type,
                "Форма контракта" AS form,
                "Состояние сделки" AS status,
                CAST("ИНН продавца" AS VARCHAR) AS seller_inn,
                CAST("ИНН покупателя" AS VARCHAR) AS buyer_inn,
                "Брокер продавца" AS seller_broker,
                "Брокер покупателя" AS buyer_broker,
                "Дата оплаты" AS payment_date,
                "Дата поставки" AS delivery_date,
                "Поставлено" AS delivered
            FROM read_csv_auto(?, header=true)
        """, [str(f)])
        cnt = con.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        print(f"OK (total: {cnt})")

    # Indexes
    print("\nCreating indexes...")
    con.execute("CREATE INDEX idx_deals_date ON deals(deal_date)")
    con.execute("CREATE INDEX idx_deals_seller ON deals(seller_inn)")
    con.execute("CREATE INDEX idx_deals_buyer ON deals(buyer_inn)")
    con.execute("CREATE INDEX idx_deals_contract ON deals(contract_id)")
    con.execute("CREATE INDEX idx_deals_status ON deals(status)")
    print("   Indexes created.")

    # Stats
    print("\n" + "=" * 60)
    print("DATABASE READY")
    print("=" * 60)
    print(f"File: {DB_PATH}")
    print(f"Size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB\n")

    stats = con.execute("""
        SELECT 
            (SELECT COUNT(*) FROM deals) AS deals,
            (SELECT COUNT(*) FROM contracts) AS contracts,
            (SELECT COUNT(*) FROM participants) AS participants,
            (SELECT COUNT(*) FROM brokers) AS brokers,
            (SELECT COUNT(*) FROM usd_rates) AS rates
    """).fetchdf()
    print(stats.to_string(index=False))

    print("\nSample – first dates:")
    print(con.execute("""
        SELECT deal_date, COUNT(*) as cnt, 
               ROUND(SUM(amount)/1e9, 2) as sum_billion
        FROM deals 
        WHERE deal_date IS NOT NULL
        GROUP BY deal_date 
        ORDER BY deal_date 
        LIMIT 5
    """).fetchdf().to_string(index=False))

    con.close()
    print("\n✅ Done.")

if __name__ == "__main__":
    main()
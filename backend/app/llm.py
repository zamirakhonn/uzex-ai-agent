from __future__ import annotations

from .config import ENABLE_LLM_SQL, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

SCHEMA = """
TABLE deals_enriched (
  deal_id BIGINT, deal_date DATE, deal_time TIME, auction_type VARCHAR,
  quantity DOUBLE, amount DOUBLE, start_price DOUBLE, contract_id BIGINT,
  product_name VARCHAR, lot DOUBLE, unit VARCHAR, region VARCHAR,
  contract_kind VARCHAR,  -- Внутренний | Экспортный
  contract_form VARCHAR,  -- Спот | Форвард | Фьючерс
  status VARCHAR, seller_inn VARCHAR, buyer_inn VARCHAR,
  seller_broker VARCHAR, buyer_broker VARCHAR, payment_date DATE, delivery_date DATE,
  delivered DOUBLE, source_file VARCHAR, volume DOUBLE, unit_price DOUBLE,
  currency VARCHAR, category VARCHAR, industry VARCHAR, seller_name VARCHAR,
  buyer_name VARCHAR, seller_broker_name VARCHAR, buyer_broker_name VARCHAR,
  usd_rate DOUBLE, amount_uzs DOUBLE, year INTEGER, month INTEGER, day INTEGER
)
TABLE participants (inn VARCHAR, name VARCHAR, region VARCHAR, activity VARCHAR, role VARCHAR, vat_payer VARCHAR)
TABLE contracts (contract_id BIGINT, product_name VARCHAR, currency VARCHAR, seller_inn VARCHAR, category VARCHAR, industry VARCHAR, contract_kind VARCHAR, contract_form VARCHAR)
TABLE brokers (code VARCHAR, name VARCHAR, inn VARCHAR, region VARCHAR)
TABLE usd_rates (rate_date DATE, rate DOUBLE)
amount_uzs = amount for UZS deals, amount * usd_rate for USD (export) deals.
Dates are DATE. Use year, month columns. LIMIT 50. SELECT only.
"""


def llm_sql(question: str) -> str | None:
    if not ENABLE_LLM_SQL or not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write one DuckDB SELECT for UZEX data. Return ONLY SQL. "
                        "If the question cannot be answered from schema, return NONE.\n"
                        + SCHEMA
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        sql = (resp.choices[0].message.content or "").strip()
        if sql.upper() == "NONE":
            return None
        if sql.startswith("```"):
            sql = sql.split("```")[1]
            if sql.lower().startswith("sql"):
                sql = sql[3:]
        return sql.strip()
    except Exception:
        return None

# UZEX Insight

Production-grade Q&A over the **Uzbekistan Commodity Exchange (UZEX)** deal registry.

The system answers **only** from files in `/data`. If a fact is not in the dataset, it returns:

- **UZ:** Ushbu ma'lumot datasetda mavjud emas.
- **RU:** Этой информации нет в предоставленных данных.

No login. No external knowledge. No invented companies, INNs, or amounts.

---

## Why this cannot hallucinate

1. **SQL-first planner** — common judge questions (counts, sums, max deal, company lookup, FX rate, status, year comparison) compile to **parameterized DuckDB SQL**, not free-form generation.
2. **Fail closed** — empty SQL result ⇒ not-found. Fuzzy company match below threshold ⇒ not-found. SQL error ⇒ not-found.
3. **Answer formatter is deterministic** — the model does not write numbers. Templates copy values from query rows.
4. **SQL guard** — only `SELECT`. Writes, `COPY`, `ATTACH`, multi-statements are rejected.
5. **Optional LLM SQL** is **off by default**. If enabled, the same guard + empty-result rule still applies.
6. **Citations** — deal id, INN, contract, date, source file, confidence, runtime.

---

## Dataset (inspected, not assumed)

| File | Rows | Role |
|---|---|---|
| `deals_2022.csv` … `deals_2026.csv` | 500 000 | Deals 03.01.2022 – 30.10.2026 |
| `contracts.csv` | 6 616 | Contract cards, currency, HS code, seller |
| `participants.csv` | 14 392 | Companies (INN, role, region) |
| `brokers.csv` | 120 | Broker offices |
| `usd_rates.csv` | daily | UZS per 1 USD |

**Business rules encoded in SQL (from `data/README.md`):**

- Volume = `quantity × lot`
- Unit price = `amount ÷ (quantity × lot)`
- `Тип контракта`: Внутренний / Экспортный
- `Форма контракта`: Спот / Форвард / Фьючерс
- Export amounts are **USD**; `amount_uzs = amount × usd_rate[deal_date]`

Dates in CSV are `DD.MM.YYYY`. Amounts use spaces as thousands separators.

---

## Architecture

```
Question
  → language detection (UZ / RU)
  → entity extraction (year, month, INN, deal id, company fuzzy match, product, region, status)
  → intent detection
  → parameterized SQL  OR  glossary retrieval
  → DuckDB execute
  → verification (SELECT-only, non-empty, row-bound)
  → deterministic answer + evidence + sources + confidence + ms
```

**Hybrid retrieval**

- **DuckDB** for analytics (counts, rankings, lookups).
- **RapidFuzz** over participants / brokers / products for semantic-ish name matching.
- **Glossary search** over dataset documentation (statuses, volume formula, FX rule).

500k deals are **not** dumped into a vector DB. That would be slow and easy to mis-rank. Entities are searched; facts are queried.

```
frontend/     Next.js 15 + Tailwind (Vercel)
backend/      FastAPI + DuckDB (Render / Railway)
data/         source CSVs
db/           uzex.duckdb (built once, reused)
```

---

## Local run (judges / demo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# first start builds DuckDB (~30–60s), then serves instantly
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). No registration.

Health: `GET http://localhost:8000/health`  
Ask: `POST http://localhost:8000/ask` `{"question":"2025 yilda nechta bitim tuzilgan?"}`

Or: `./scripts/dev.sh`

---

## Multilingual

Language is auto-detected (Uzbek Latin, Uzbek Cyrillic, Russian). The UI can force UZ or RU. The answer language always follows detection or the override.

---

## Tech stack

- Next.js 15, React 19, TypeScript, Tailwind CSS
- FastAPI, Pydantic v2
- DuckDB analytical store + enriched `deals_enriched` table
- RapidFuzz hybrid entity retrieval
- Optional OpenAI-compatible SQL fallback (`ENABLE_LLM_SQL=false` by default)

---

## Deployment

| Part | Target | Notes |
|---|---|---|
| Frontend | Vercel | `frontend/`, env `NEXT_PUBLIC_API_URL` |
| Optional API | Render / Railway | `uvicorn backend.app.main:app` |
| Telegram bot | Render Background Worker | Docker worker defined in `render.yaml` |
| Docker | `docker compose up --build` | API `:8000`, web `:3000` |

The Telegram worker builds DuckDB from the included CSVs if `db/uzex.duckdb` is missing, then loads the entity catalog before polling Telegram.

### Deploy the Telegram Worker to Render

1. Rotate any credentials that have been shared, then push the project to a Git provider connected to Render. `.env` is ignored by Git and must never be committed.
2. In Render, choose **New +** → **Blueprint**, select the repository, and apply the `render.yaml` blueprint. It creates a single Docker-based Background Worker named `uzex-ai-agent`.
3. Set `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` in the worker's Environment settings. The Blueprint marks these as secrets and never stores their values in YAML. `ENABLE_LLM_SQL=true` enables the optional OpenAI SQL fallback.
4. Deploy the worker. On its first start, it creates the local DuckDB from `data/` if needed; this can take a few minutes. Check the service Logs for `UZEX AI Telegram bot started` and `Start polling`.
5. In Telegram, send `/start`, then ask `2025 yilda nechta bitim tuzilgan?`. Confirm the response includes a count and date period. Also try `ABC kompaniyasi qancha bitim qilgan?` and confirm it returns the not-found response.

Keep exactly one active polling worker for this bot token. Running a second local or Render instance causes Telegram `getUpdates` conflicts. Use a paid Background Worker plan for continuous operation; the Blueprint starts with one `1c-2g` instance in Frankfurt.

---

## Tests

```bash
.venv/bin/pytest backend/tests -q
```

---

## Future

- Persistent query cache (Redis)
- Role-based export of CSV slices
- On-disk HNSW only for product catalog if the corpus grows

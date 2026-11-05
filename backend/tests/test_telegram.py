from backend.app.planner import plan_query
from backend.app.schemas import AskResponse, Verification
from backend.app.telegram import (
    DEMO_QUESTIONS,
    MENU_CALLBACKS,
    _menu_question,
    _format_basis,
    format_telegram_answer,
    menu_keyboard,
)


def test_demo_questions_and_menu_are_complete():
    assert DEMO_QUESTIONS == [
        "Сколько сделок было заключено в 2024 году?",
        "Какие компании самые активные?",
        "Какие товары лидируют?",
        "Покажи годовой тренд",
    ]
    assert MENU_CALLBACKS == {
        "statistics",
        "top_companies",
        "annual_trend",
        "largest_deals",
        "top_products",
    }
    assert len(menu_keyboard("uz").inline_keyboard) == 6
    assert len(menu_keyboard("ru").inline_keyboard) == 6
    assert len(menu_keyboard("uz", show_basis=True).inline_keyboard) == 7
    assert menu_keyboard("uz", show_basis=True).inline_keyboard[-2][0].text == "📄 Asos"
    assert menu_keyboard("uz").inline_keyboard[-1][1].text == "🇷🇺 Русский"
    assert menu_keyboard("ru").inline_keyboard[-1][0].text == "🇺🇿 O'zbekcha"


def test_menu_actions_map_to_existing_planner_intents():
    expected = {
        "statistics": "count_deals",
        "top_companies": "top_company",
        "annual_trend": "compare_years",
        "largest_deals": "max_deal",
        "top_products": "top_product",
    }
    for language in ("uz", "ru"):
        for callback, intent in expected.items():
            plan = plan_query(_menu_question(callback, language))
            assert plan.intent == intent
            assert plan.sql


def test_russian_count_formatter_uses_verified_result_rows():
    result = AskResponse(
        question="Сколько сделок было заключено в 2024 году?",
        language="ru",
        found=True,
        answer="106647 deals",
        confidence=0.99,
        intent="count_deals",
        reasoning_summary="SQL rows",
        sql="SELECT COUNT(*) FROM deals_enriched WHERE year = ?",
        rows=[
            {
                "deals": 106647,
                "deals_not_cancelled": 99324,
                "deals_cancelled": 7323,
                "amount_uzs": 45900904000492.24,
                "min_date": "2024-01-02T00:00:00",
                "max_date": "2024-12-31T00:00:00",
            }
        ],
        execution_ms=100,
        verification=Verification(passed=True, method="row_bound"),
        sources=["deals"],
    )

    text = format_telegram_answer(result)

    assert "В 2024 году заключено <b>106 647</b> сделок." in text
    assert "• Без аннулированных:\n99 324" in text
    assert "• Аннулированных:\n7 323" in text
    assert "таблица deals" in text
    assert "Объём торгов" not in text
    assert "deals" in text
    assert "year=2024" in text
    assert "106 647 записей" in text
    assert "📊 Результат" in text
    assert "💡 Что это значит:" in text
    assert "6.9%" in text
    assert "💬 Что спросить дальше:" in text
    assert "Сравните 2024 и 2025 годы" in text
    assert "✓ числа подтверждены" in text
    assert "0.1 с" in text
    assert "run_sql" not in text


def test_unverified_result_is_not_reported_as_verified():
    result = AskResponse(
        question="Сколько сделок было в 2024 году?",
        language="ru",
        found=False,
        answer="Нет проверенных данных.",
        confidence=0,
        intent="count_deals",
        reasoning_summary="No result",
        execution_ms=1,
        verification=Verification(passed=False, method="sql_guard"),
    )

    text = format_telegram_answer(result)

    assert "По имеющимся данным ответ не найден." in text
    assert "Что спросить дальше" not in text
    assert "не пройдена" in text


def test_year_comparison_insight_handles_ascending_year_rows():
    result = AskResponse(
        question="Сравните 2024 и 2025 годы",
        language="ru",
        found=True,
        answer="Comparison",
        confidence=0.95,
        intent="compare_years",
        reasoning_summary="SQL rows",
        rows=[{"year": 2024, "deals": 10}, {"year": 2025, "deals": 15}],
        execution_ms=10,
        verification=Verification(passed=True, method="row_bound"),
    )

    text = format_telegram_answer(result)

    assert "В 2025 году на 5 сделок больше, чем в 2024 году." in text


def test_empty_results_use_localized_not_found_copy():
    result = AskResponse(
        question="Question",
        language="uz",
        found=False,
        answer="Old fallback text",
        confidence=0,
        intent="count_deals",
        reasoning_summary="No rows",
        execution_ms=2,
        verification=Verification(passed=True, method="empty_is_not_found"),
    )

    assert format_telegram_answer(result).startswith(
        "Mavjud ma'lumotlar asosida javob topilmadi."
    )


def test_zero_count_aggregate_row_is_not_called_not_found():
    result = AskResponse(
        question="Сколько сделок было в 2024 году?",
        language="ru",
        found=False,
        answer="Old fallback text",
        confidence=0,
        intent="count_deals",
        reasoning_summary="Aggregate row returned",
        rows=[{"deals": 0, "amount_uzs": 0, "min_date": None, "max_date": None}],
        execution_ms=2,
        verification=Verification(passed=True, method="row_bound"),
    )

    text = format_telegram_answer(result)

    assert text.startswith("По имеющимся данным ответ не найден.")


def test_sql_is_appended_only_when_question_requests_it():
    result = AskResponse(
        question="Как рассчитано? Покажи SQL",
        language="ru",
        found=True,
        answer="Проверенный ответ.",
        confidence=0.9,
        intent="count_deals",
        reasoning_summary="SQL rows",
        sql="SELECT COUNT(*) FROM deals_enriched",
        rows=[{"deals": 12}],
        execution_ms=1,
        verification=Verification(passed=True, method="row_bound"),
    )

    text = format_telegram_answer(result)

    assert "run_sql" in text
    assert "<pre>SELECT COUNT(*) FROM deals_enriched</pre>" in text

    for question in ("SQL ko'rsat", "qanday hisoblangan", "основание"):
        requested = result.model_copy(update={"question": question})
        assert "run_sql" in format_telegram_answer(requested)

    default = result.model_copy(update={"question": "Сколько сделок было в 2024 году?"})
    assert "run_sql" not in format_telegram_answer(default)


def test_basis_view_uses_response_sql_sources_and_question_year():
    result = AskResponse(
        question="2024 yilda nechta bitim bo'lgan?",
        language="uz",
        found=True,
        answer="106647 deals",
        confidence=0.99,
        intent="count_deals",
        reasoning_summary="SQL rows",
        sql="SELECT COUNT(*) FROM deals_enriched WHERE year = ?",
        rows=[{"deals": 106647}],
        execution_ms=100,
        verification=Verification(passed=True, method="row_bound"),
        sources=["deals_*.csv"],
    )

    basis = _format_basis(result)

    assert "deals jadvali" in basis
    assert "year=2024" in basis
    assert "COUNT(*)" in basis
    assert "Tanlangan filtr" in basis


def test_uzbek_count_formatter_uses_uzbek_copy():
    result = AskResponse(
        question="2024 yilda nechta bitim bo'lgan?",
        language="uz",
        found=True,
        answer="106647 deals",
        confidence=0.99,
        intent="count_deals",
        reasoning_summary="SQL rows",
        rows=[
            {
                "deals": 106647,
                "deals_not_cancelled": 99324,
                "deals_cancelled": 7323,
                "amount_uzs": 45900904000492.24,
                "min_date": "2024-01-02T00:00:00",
                "max_date": "2024-12-31T00:00:00",
            }
        ],
        execution_ms=100,
        verification=Verification(passed=True, method="row_bound"),
        sources=["deals_*.csv"],
    )

    text = format_telegram_answer(result)

    assert "2024 yilda <b>106 647 ta</b> bitim tuzilgan." in text
    assert "Bekor qilinmagan:\n99 324" in text
    assert "Bekor qilingan:\n7 323" in text
    assert "✓ raqamlar tasdiqlangan" in text


def test_largest_deal_is_presented_as_a_human_summary():
    result = AskResponse(
        question="Eng katta bitim qaysi?",
        language="uz",
        found=True,
        answer="Bitim #247 890: raw database response",
        confidence=0.98,
        intent="max_deal",
        reasoning_summary="SQL rows",
        rows=[
            {
                "deal_id": 247890,
                "product_name": "ПШЕНИЦА ПРОДОВОЛЬСТВЕННАЯ КЛАСС 4-КЛАСС",
                "amount_uzs": 30190376286,
                "deal_date": "2023-10-09T00:00:00",
                "seller_name": "CHO‘HE KLASTER MCHJ",
                "seller_inn": "902946936",
                "buyer_name": "МИКИ БИЗНЕС ҚК",
                "buyer_inn": "916644459",
                "status": "Исполнен",
            }
        ],
        execution_ms=100,
        verification=Verification(passed=True, method="row_bound"),
        sources=["deals_2023.csv"],
    )

    text = format_telegram_answer(result)

    assert "Eng yirik bitim" in text
    assert "30 190 376 286 so'm" in text
    assert "CHO‘HE KLASTER MCHJ" in text
    assert "902946936" in text
    assert "МИКИ БИЗНЕС ҚК" in text
    assert "916644459" in text
    assert "Bitim #" not in text
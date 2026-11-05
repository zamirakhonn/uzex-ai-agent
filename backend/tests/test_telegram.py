from backend.app.planner import plan_query
from backend.app.schemas import AskResponse, Verification
from backend.app.telegram import (
    DEMO_QUESTIONS,
    MENU_CALLBACKS,
    _menu_question,
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
    assert len(menu_keyboard().inline_keyboard) == 5


def test_menu_actions_map_to_existing_planner_intents():
    expected = {
        "statistics": "count_deals",
        "top_companies": "top_company",
        "annual_trend": "compare_years",
        "largest_deals": "max_deal",
        "top_products": "top_product",
    }
    for callback, intent in expected.items():
        plan = plan_query(_menu_question(callback))
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
        sql="SELECT ...",
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

    assert "В 2024 году заключено <b>106 647</b> сделок." in text
    assert "• Без аннулированных:\n99 324 сделок" in text
    assert "• Аннулированных:\n7 323" in text
    assert "уверенность 99%" in text
    assert "Источник: deals_*.csv" in text


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

    assert "Нет проверенных данных." in text
    assert "не пройдена" in text
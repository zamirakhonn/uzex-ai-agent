from backend.app.language import detect_language


def test_uzbek_latin():
    assert detect_language("2025 yilda nechta bitim tuzilgan?") == "uz"


def test_russian():
    assert detect_language("Сколько сделок было в январе 2024 года?") == "ru"


def test_russian_deal_status_word_is_not_a_status_filter():
    from backend.app.planner import plan_query

    plan = plan_query("Сколько сделок было заключено в 2024 году?")

    assert plan.intent == "count_deals"
    assert plan.params == [2024]

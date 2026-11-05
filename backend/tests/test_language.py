from backend.app.language import detect_language


def test_uzbek_latin():
    assert detect_language("2025 yilda nechta bitim tuzilgan?") == "uz"


def test_russian():
    assert detect_language("Сколько сделок было в январе 2024 года?") == "ru"

from backend.app.pipeline import _safe_sql


def test_select_ok():
    assert _safe_sql("SELECT COUNT(*) FROM deals_enriched")


def test_select_cte_ok():
    assert _safe_sql("WITH totals AS (SELECT 1 AS deals) SELECT deals FROM totals")


def test_drop_blocked():
    assert not _safe_sql("DROP TABLE deals_enriched")
    assert not _safe_sql("SELECT 1; DROP TABLE deals")

from __future__ import annotations

from datetime import date

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def test_compare_series_builds_fact_first_and_ml_fill() -> None:
    payload = {"filters": {}, "compare_series": {}}
    daily_history = [
        {"date": date(2025, 5, 1), "count": 4.0},
        {"date": date(2024, 5, 1), "count": 3.0},
        {"date": date(2023, 5, 2), "count": 5.0},
    ]

    result = ml_core._attach_compare_series(
        payload,
        daily_history=daily_history,
        scenario_temperature=None,
        current_user_day=None,
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        caches=create_default_caches(),
    )

    compare = result.get("compare_series") or {}
    rows = compare.get("rows") or []
    assert rows
    assert rows[0]["a_source"] == "fact"
    assert rows[0]["b_source"] == "fact"
    assert compare["history_has_data"] is True
    assert any(row["a_source"] == "ml" for row in rows[1:])


def test_compare_series_with_empty_history_keeps_rows_empty_and_history_flag_false() -> None:
    payload = {"filters": {}, "compare_series": {}}

    result = ml_core._attach_compare_series(
        payload,
        daily_history=[],
        scenario_temperature=None,
        current_user_day=None,
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        caches=create_default_caches(),
    )

    compare = result.get("compare_series") or {}
    rows = compare.get("rows") or []
    assert rows
    assert compare["history_has_data"] is False
    assert all(row.get("a_value") is None for row in rows)
    assert all(row.get("b_value") is None for row in rows)


def test_compare_series_ml_uses_selected_month_across_prior_years_only() -> None:
    payload = {"filters": {}, "compare_series": {}}
    daily_history = [
        {"date": date(2023, 5, 1), "count": 10.0},
        {"date": date(2024, 5, 2), "count": 20.0},
        {"date": date(2025, 5, 1), "count": 30.0},
        {"date": date(2024, 4, 1), "count": 999.0},
        {"date": date(2025, 6, 1), "count": 999.0},
    ]
    result = ml_core._attach_compare_series(
        payload,
        daily_history=daily_history,
        scenario_temperature=None,
        current_user_day=None,
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2026,
        caches=create_default_caches(),
    )

    compare = result.get("compare_series") or {}
    rows = compare.get("rows") or []
    assert compare.get("history_has_data") is True
    assert rows
    day1 = next(row for row in rows if int(row.get("day") or 0) == 1)
    day2 = next(row for row in rows if int(row.get("day") or 0) == 2)
    day3 = next(row for row in rows if int(row.get("day") or 0) == 3)
    assert float(day1.get("b_value")) == 20.0
    assert float(day2.get("b_value")) == 20.0
    assert float(day3.get("b_value")) == 20.0

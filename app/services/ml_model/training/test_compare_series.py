from __future__ import annotations

from app.services.ml_model.training.compare_series import build_compare_series


def test_compare_series_both_years_fact() -> None:
    daily = [
        {"date": "2024-05-01", "count": 3},
        {"date": "2024-05-02", "count": 4},
        {"date": "2025-05-01", "count": 5},
        {"date": "2025-05-02", "count": 6},
    ]
    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=lambda _y, _m: {},
    )
    assert result["rows"][0]["a_source"] == "fact"
    assert result["rows"][0]["b_source"] == "fact"
    assert result["a_summary"]["fact_days"] >= 2
    assert result["b_summary"]["fact_days"] >= 2


def test_compare_series_year_b_from_ml_when_no_facts() -> None:
    daily = [{"date": "2025-05-01", "count": 5}]

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 7.0} if year == 2024 else {}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    first = result["rows"][0]
    assert first["a_source"] == "fact"
    assert first["b_source"] == "ml"
    assert first["b_value"] == 7.0


def test_compare_series_both_ml_when_no_facts() -> None:
    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: float(year)}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=[],
        ml_month_provider=_provider,
    )
    first = result["rows"][0]
    assert first["a_source"] == "ml"
    assert first["b_source"] == "ml"
    assert first["a_value"] == 2025.0
    assert first["b_value"] == 2024.0


def test_compare_series_partial_fact_hybrid() -> None:
    daily = [{"date": "2025-05-01", "count": 9}]

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 1.0, 2: 2.0} if year == 2025 else {1: 3.0, 2: 4.0}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    assert result["rows"][0]["a_source"] == "fact"
    assert result["rows"][1]["a_source"] == "ml"
    assert result["a_summary"]["fact_days"] == 1
    assert result["a_summary"]["ml_days"] >= 1


def test_compare_series_uses_real_month_length_for_selected_years() -> None:
    result = build_compare_series(
        month=2,
        year_a=2024,
        year_b=2023,
        daily_history=[],
        ml_month_provider=lambda _y, _m: {},
    )
    assert len(result["rows"]) == 29
    assert result["rows"][-1]["day"] == 29

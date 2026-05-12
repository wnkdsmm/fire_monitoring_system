from __future__ import annotations

from app.services.shared.request_state import build_ml_cache_key


def _base_kwargs() -> dict[str, object]:
    return {
        "cache_schema_version": 1,
        "selected_table": "all",
        "source_tables": ["fires_2025", "fires_2026"],
        "cause": "all",
        "object_category": "all",
        "temperature": "",
        "days_ahead": 7,
        "history_window": "all",
        "current_user_date": "2026-05-12",
    }


def test_cache_key_differs_by_compare_year_a() -> None:
    first = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=None,
        period_month=None,
    )
    second = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2024,
        compare_year_b=2024,
        period_year=None,
        period_month=None,
    )
    assert first != second


def test_cache_key_differs_by_compare_month() -> None:
    first = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=None,
        period_month=None,
    )
    second = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=6,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=None,
        period_month=None,
    )
    assert first != second


def test_cache_key_differs_by_compare_year_b() -> None:
    first = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=None,
        period_month=None,
    )
    second = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2023,
        period_year=None,
        period_month=None,
    )
    assert first != second


def test_cache_key_differs_by_period_year_month() -> None:
    first = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=2025,
        period_month=5,
    )
    second = build_ml_cache_key(
        **_base_kwargs(),
        compare_month=5,
        compare_year_a=2025,
        compare_year_b=2024,
        period_year=2025,
        period_month=6,
    )
    assert first != second

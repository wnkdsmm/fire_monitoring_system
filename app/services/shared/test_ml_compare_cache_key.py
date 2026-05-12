from __future__ import annotations

from app.services.shared.request_state import build_ml_compare_cache_key


def test_ml_compare_cache_key_changes_by_year_a() -> None:
    first = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=5,
        year_a=2025,
        year_b=2024,
        current_user_date="2026-05-12",
    )
    second = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=5,
        year_a=2024,
        year_b=2024,
        current_user_date="2026-05-12",
    )
    assert first != second


def test_ml_compare_cache_key_changes_by_month() -> None:
    first = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=5,
        year_a=2025,
        year_b=2024,
        current_user_date="2026-05-12",
    )
    second = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=6,
        year_a=2025,
        year_b=2024,
        current_user_date="2026-05-12",
    )
    assert first != second


def test_ml_compare_cache_key_changes_by_year_b() -> None:
    first = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=5,
        year_a=2025,
        year_b=2024,
        current_user_date="2026-05-12",
    )
    second = build_ml_compare_cache_key(
        cache_schema_version=1,
        selected_tables=("fires",),
        cause="all",
        object_category="all",
        month=5,
        year_a=2025,
        year_b=2023,
        current_user_date="2026-05-12",
    )
    assert first != second

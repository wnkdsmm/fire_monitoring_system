from __future__ import annotations

from app.services.ml_model import core as ml_core


def test_compare_defaults_are_fixed_years_and_current_month_from_user_date() -> None:
    month, year_a, year_b = ml_core._normalize_compare_selection(
        month=None,
        year_a=None,
        year_b=None,
        current_user_date="2026-05-12",
    )
    assert month == 5
    assert year_a == 2024
    assert year_b == 2025

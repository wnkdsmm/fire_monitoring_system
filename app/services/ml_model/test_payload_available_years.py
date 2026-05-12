from __future__ import annotations

from datetime import date

from app.services.ml_model.payloads import _extract_available_years


def test_extract_available_years_builds_descending_option_list() -> None:
    daily_history = [
        {"date": date(2024, 1, 1), "count": 1},
        {"date": "2026-05-12", "count": 2},
        {"date": "2025-03-03", "count": 3},
        {"date": "2026-06-01", "count": 4},
    ]

    options = _extract_available_years(daily_history)

    assert options == [
        {"value": "2026", "label": "2026"},
        {"value": "2025", "label": "2025"},
        {"value": "2024", "label": "2024"},
    ]

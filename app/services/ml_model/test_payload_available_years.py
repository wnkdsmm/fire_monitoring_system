from __future__ import annotations

from datetime import date

from app.services.ml_model.payloads import _extract_available_years


def test_extract_available_years_prefers_years_from_table_names() -> None:
    table_options = [
        {"value": "all", "label": "Все таблицы"},
        {"value": "clean_ekup_Yemelyanovo_2025", "label": "clean_ekup_Yemelyanovo_2025"},
        {"value": "STAT1993_decoded", "label": "STAT1993_decoded"},
        {"value": "fires_2024_archive", "label": "fires_2024_archive"},
    ]
    daily_history = [{"date": "2026-05-12", "count": 2}]

    options = _extract_available_years(table_options, daily_history)

    assert options == [
        {"value": "2025", "label": "2025"},
        {"value": "2024", "label": "2024"},
        {"value": "1993", "label": "1993"},
    ]


def test_extract_available_years_falls_back_to_daily_history_when_no_year_in_table_names() -> None:
    table_options = [
        {"value": "all", "label": "Все таблицы"},
        {"value": "fires_archive", "label": "fires_archive"},
    ]
    daily_history = [
        {"date": date(2024, 1, 1), "count": 1},
        {"date": "2026-05-12", "count": 2},
        {"date": "2025-03-03", "count": 3},
        {"date": "2026-06-01", "count": 4},
    ]

    options = _extract_available_years(table_options, daily_history)

    assert options == [
        {"value": "2026", "label": "2026"},
        {"value": "2025", "label": "2025"},
        {"value": "2024", "label": "2024"},
    ]

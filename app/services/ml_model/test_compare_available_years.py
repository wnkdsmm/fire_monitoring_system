from __future__ import annotations

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def test_extract_available_years_from_table_options_parses_year_tokens() -> None:
    options = [
        {"value": "all", "label": "Все таблицы"},
        {"value": "clean_ekup_Yemelyanovo_2025", "label": "clean_ekup_Yemelyanovo_2025"},
        {"value": "STAT1993_decoded", "label": "STAT1993_decoded"},
        {"value": "fires_2024_archive", "label": "fires_2024_archive"},
    ]
    result = ml_core._extract_available_years_from_table_options(options)
    assert result == [
        {"value": "2025", "label": "2025"},
        {"value": "2024", "label": "2024"},
        {"value": "1993", "label": "1993"},
    ]


def test_compare_response_contains_available_years_in_filters_when_no_sources(monkeypatch) -> None:
    caches = create_default_caches()

    def _fake_request_state(**_kwargs):
        return {
            "table_options": [
                {"value": "all", "label": "Все таблицы"},
                {"value": "clean_ekup_Yemelyanovo_2025", "label": "clean_ekup_Yemelyanovo_2025"},
                {"value": "STAT1993_decoded", "label": "STAT1993_decoded"},
            ],
            "selected_table": "all",
            "selected_tables": [],
            "source_tables": [],
            "selected_history_window": "all",
            "scenario_temperature": None,
            "current_user_date": "2026-05-12",
            "selected_compare_month": 5,
            "selected_compare_year_a": 2025,
            "selected_compare_year_b": 2024,
        }

    monkeypatch.setattr(ml_core, "_build_ml_request_state", _fake_request_state)
    payload = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    years = (payload.get("filters") or {}).get("available_years") or []
    assert {"value": "2025", "label": "2025"} in years
    assert {"value": "1993", "label": "1993"} in years


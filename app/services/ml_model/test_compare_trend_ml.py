from __future__ import annotations

from datetime import date

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def test_compare_ml_does_not_backfill_with_heuristics_when_ml_not_ready(monkeypatch) -> None:
    caches = create_default_caches()

    def _fake_request_state(**_kwargs):
        return {
            "table_options": [{"value": "all", "label": "Все таблицы"}, {"value": "fires_2023", "label": "fires_2023"}],
            "selected_table": "all",
            "selected_tables": ["fires_2023"],
            "source_tables": ["fires_2023"],
            "selected_history_window": "all",
            "scenario_temperature": None,
            "current_user_date": "2026-05-12",
            "selected_compare_month": 5,
            "selected_compare_year_a": 2026,
            "selected_compare_year_b": 2024,
        }

    def _fake_filter_bundle(**_kwargs):
        return {
            "metadata_items": [],
            "preload_notes": [],
            "option_catalog": {"causes": [], "object_categories": []},
            "selected_cause": "all",
            "selected_object_category": "all",
        }

    # Sparse history: ML training is not ready, so compare mode should not inject heuristic values.
    daily_history = [
        {"date": date(2021, 5, 1), "count": 1.0},
        {"date": date(2022, 5, 1), "count": 3.0},
        {"date": date(2023, 5, 1), "count": 5.0},
        {"date": date(2024, 5, 1), "count": 7.0},
    ]

    def _fake_aggregation_inputs(**_kwargs):
        return {"daily_history": daily_history, "filtered_records_count": 4}

    monkeypatch.setattr(ml_core, "_build_ml_request_state", _fake_request_state)
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", _fake_filter_bundle)
    monkeypatch.setattr(ml_core, "_load_ml_aggregation_inputs", _fake_aggregation_inputs)

    payload = ml_core.get_ml_compare_series_data(month=5, year_a=2026, year_b=2024, caches=caches)
    rows = (payload.get("compare_series") or {}).get("rows") or []
    first = rows[0]
    assert first["a_source"] == "ml"
    assert first["a_value"] is None

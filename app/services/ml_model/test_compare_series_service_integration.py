from __future__ import annotations

from datetime import date, timedelta

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def _fake_request_state(*, month: int, year_a: int, year_b: int, source_tables: list[str] | None = None) -> dict[str, object]:
    return {
        "selected_compare_month": month,
        "selected_compare_year_a": year_a,
        "selected_compare_year_b": year_b,
        "source_tables": source_tables if source_tables is not None else ["fires"],
        "selected_history_window": "all",
        "current_user_date": "2026-05-12",
        "selected_table": "all",
        "selected_tables": source_tables if source_tables is not None else ["fires"],
        "scenario_temperature": None,
    }


def _fake_ml_train(*_args, **kwargs):
    anchor = kwargs.get("current_user_date")
    target = anchor + timedelta(days=1)
    return {
        "forecast_rows": [
            {"date": f"{target.year:04d}-{target.month:02d}-01", "forecast_value": 11.0},
            {"date": f"{target.year:04d}-{target.month:02d}-02", "forecast_value": 12.0},
        ]
    }


def test_compare_service_switching_year_a_changes_response(monkeypatch) -> None:
    caches = create_default_caches()

    def _state_builder(**kwargs):
        return _fake_request_state(
            month=int(kwargs.get("month") or 5),
            year_a=int(kwargs.get("year_a") or 2025),
            year_b=int(kwargs.get("year_b") or 2024),
        )

    monkeypatch.setattr(ml_core, "_build_ml_request_state", _state_builder)
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", lambda **_k: {"option_catalog": {}, "metadata_items": [], "preload_notes": [], "selected_cause": "all", "selected_object_category": "all"})
    monkeypatch.setattr(ml_core, "_load_ml_aggregation_inputs", lambda **_k: {"daily_history": [], "filtered_records_count": 0})
    monkeypatch.setattr(ml_core, "_train_ml_model", _fake_ml_train)

    first = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    second = ml_core.get_ml_compare_series_data(month=5, year_a=2024, year_b=2024, caches=caches)

    assert first["compare_series"]["year_a"] == 2025
    assert second["compare_series"]["year_a"] == 2024


def test_compare_service_does_not_return_stale_for_different_year_pairs(monkeypatch) -> None:
    caches = create_default_caches()

    def _state_builder(**kwargs):
        return _fake_request_state(
            month=int(kwargs.get("month") or 5),
            year_a=int(kwargs.get("year_a") or 2025),
            year_b=int(kwargs.get("year_b") or 2024),
        )

    monkeypatch.setattr(ml_core, "_build_ml_request_state", _state_builder)
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", lambda **_k: {"option_catalog": {}, "metadata_items": [], "preload_notes": [], "selected_cause": "all", "selected_object_category": "all"})
    monkeypatch.setattr(ml_core, "_load_ml_aggregation_inputs", lambda **_k: {"daily_history": [], "filtered_records_count": 0})
    monkeypatch.setattr(ml_core, "_train_ml_model", _fake_ml_train)

    first = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    second = ml_core.get_ml_compare_series_data(month=5, year_a=2024, year_b=2023, caches=caches)

    assert first["compare_series"]["year_a"] == 2025
    assert first["compare_series"]["year_b"] == 2024
    assert second["compare_series"]["year_a"] == 2024
    assert second["compare_series"]["year_b"] == 2023
    assert first["compare_series"] != second["compare_series"]


def test_compare_service_marks_fact_source_when_facts_exist(monkeypatch) -> None:
    caches = create_default_caches()
    monkeypatch.setattr(ml_core, "_build_ml_request_state", lambda **kwargs: _fake_request_state(month=5, year_a=2025, year_b=2024))
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", lambda **_k: {"option_catalog": {}, "metadata_items": [], "preload_notes": [], "selected_cause": "all", "selected_object_category": "all"})
    monkeypatch.setattr(
        ml_core,
        "_load_ml_aggregation_inputs",
        lambda **_k: {
            "daily_history": [
                {"date": date(2025, 5, 1), "count": 4.0},
                {"date": date(2024, 5, 1), "count": 3.0},
            ],
            "filtered_records_count": 2,
        },
    )
    monkeypatch.setattr(ml_core, "_train_ml_model", _fake_ml_train)

    payload = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    first = payload["compare_series"]["rows"][0]
    assert first["a_source"] == "fact"
    assert first["b_source"] == "fact"


def test_compare_service_marks_ml_source_when_facts_absent(monkeypatch) -> None:
    caches = create_default_caches()
    monkeypatch.setattr(ml_core, "_build_ml_request_state", lambda **kwargs: _fake_request_state(month=5, year_a=2025, year_b=2024))
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", lambda **_k: {"option_catalog": {}, "metadata_items": [], "preload_notes": [], "selected_cause": "all", "selected_object_category": "all"})
    monkeypatch.setattr(ml_core, "_load_ml_aggregation_inputs", lambda **_k: {"daily_history": [], "filtered_records_count": 0})
    monkeypatch.setattr(ml_core, "_train_ml_model", _fake_ml_train)

    payload = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    first = payload["compare_series"]["rows"][0]
    assert first["a_source"] == "ml"
    assert first["b_source"] == "ml"


def test_compare_service_builds_hybrid_when_partial_facts_exist(monkeypatch) -> None:
    caches = create_default_caches()
    monkeypatch.setattr(ml_core, "_build_ml_request_state", lambda **kwargs: _fake_request_state(month=5, year_a=2025, year_b=2024))
    monkeypatch.setattr(ml_core, "_load_ml_filter_bundle", lambda **_k: {"option_catalog": {}, "metadata_items": [], "preload_notes": [], "selected_cause": "all", "selected_object_category": "all"})
    monkeypatch.setattr(
        ml_core,
        "_load_ml_aggregation_inputs",
        lambda **_k: {
            "daily_history": [
                {"date": date(2025, 5, 1), "count": 9.0},
            ],
            "filtered_records_count": 1,
        },
    )
    monkeypatch.setattr(ml_core, "_train_ml_model", _fake_ml_train)

    payload = ml_core.get_ml_compare_series_data(month=5, year_a=2025, year_b=2024, caches=caches)
    rows = payload["compare_series"]["rows"]
    assert rows[0]["a_source"] == "fact"
    assert rows[1]["a_source"] == "ml"

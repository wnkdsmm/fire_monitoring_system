from __future__ import annotations

from datetime import date, timedelta

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def test_compare_future_year_avoids_flat_zero_when_positive_history_exists(monkeypatch) -> None:
    caches = create_default_caches()
    month = 5
    year_a = 2025
    year_b = 2026

    def _fake_request_state(**kwargs):
        return {
            "selected_compare_month": kwargs.get("month", month),
            "selected_compare_year_a": kwargs.get("year_a", year_a),
            "selected_compare_year_b": kwargs.get("year_b", year_b),
            "selected_history_window": "all",
            "selected_table": "all",
            "selected_tables": [],
            "table_options": [],
            "source_tables": ["dummy"],
            "scenario_temperature": None,
            "current_user_date": "",
            "current_user_day": None,
            "cache_key": ("x",),
        }

    start = date(2025, month, 1)
    daily_history = []
    for offset in range(31):
        day = start + timedelta(days=offset)
        if day.month != month:
            break
        daily_history.append({"date": day.isoformat(), "count": float(10 + (offset % 7))})
        daily_history.append({"date": (day.replace(year=2024)).isoformat(), "count": 0.0})

    monkeypatch.setattr(ml_core, "_build_ml_request_state", _fake_request_state)
    monkeypatch.setattr(
        ml_core,
        "_load_ml_filter_bundle",
        lambda **_: {"selected_cause": "all", "selected_object_category": "all"},
    )
    monkeypatch.setattr(
        ml_core,
        "_load_ml_aggregation_inputs",
        lambda **_: {"daily_history": daily_history},
    )

    payload = ml_core.get_ml_compare_series_data(month=month, year_a=year_a, year_b=year_b, caches=caches)
    rows = (payload.get("compare_series") or {}).get("rows") or []
    b_values = [float(row.get("b_value")) for row in rows if row.get("b_value") is not None]
    assert b_values
    assert any(value > 0 for value in b_values)


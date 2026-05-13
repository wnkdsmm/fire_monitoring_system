from __future__ import annotations

from datetime import date, timedelta

from app.services.ml_model import core


def _build_daily_series(start: date, days: int, *, base: float = 2.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(days):
        current = start + timedelta(days=i)
        rows.append({"date": current.isoformat(), "count": float(base + (i % 5))})
    return rows


def test_poisson_predictor_falls_back_on_small_history() -> None:
    daily_history = _build_daily_series(date(2025, 1, 1), 40, base=1.0)
    preds, summary = core._predict_month_poisson_ml(
        daily_history=daily_history,
        target_year=2026,
        target_month=5,
    )
    assert len(preds) == 31
    assert summary["model_days"] == 0
    assert summary["clipped_days"] == 31
    assert all((value is not None and value >= 0.0) for value in preds.values())


def test_poisson_predictor_returns_full_month_for_future_year() -> None:
    daily_history = _build_daily_series(date(2024, 1, 1), 240, base=3.0)
    preds, summary = core._predict_month_poisson_ml(
        daily_history=daily_history,
        target_year=2026,
        target_month=6,
    )
    assert len(preds) == 30
    assert summary["model_days"] == 30
    assert summary["clipped_days"] >= 0
    assert all((value is not None and value >= 0.0) for value in preds.values())


def test_compare_series_payload_contains_poisson_line_contract(monkeypatch) -> None:
    def _fake_request_state(**_kwargs):
        return {
            "selected_compare_month": 5,
            "selected_compare_year_a": 2025,
            "selected_compare_year_b": 2024,
            "selected_compare_year_ml": 2027,
            "table_options": [{"value": "fires_2025", "label": "fires_2025"}],
            "source_tables": ["fires_2025"],
            "selected_table": "fires_2025",
            "selected_tables": ["fires_2025"],
            "current_user_date": "2026-05-13",
        }

    monkeypatch.setattr(core, "_build_ml_request_state", _fake_request_state)
    monkeypatch.setattr(core, "_load_ml_filter_bundle", lambda **_kwargs: {})
    monkeypatch.setattr(
        core,
        "_load_ml_aggregation_inputs",
        lambda **_kwargs: {"daily_history": _build_daily_series(date(2024, 1, 1), 200, base=2.0)},
    )

    payload = core.get_ml_compare_series_data(
        table_name="fires_2025",
        month=5,
        year_a=2025,
        year_b=2024,
        year_ml=2027,
    )
    compare = payload["compare_series"]
    assert compare["year_model"] == 2027
    assert "d_summary" in compare
    assert "model_days" in compare["d_summary"]
    assert "clipped_days" in compare["d_summary"]
    assert compare["rows"]
    first = compare["rows"][0]
    assert "d_value" in first
    assert first["d_source"] == "ml_model"

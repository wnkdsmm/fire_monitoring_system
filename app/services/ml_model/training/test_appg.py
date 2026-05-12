from __future__ import annotations

from app.services.ml_model.training.appg import compute_appg_series


def test_compute_appg_series_regular_case() -> None:
    target_rows = [
        {"date": "2026-05-11", "forecast_value": 12.0},
    ]
    history_rows = [
        {"date": "2025-05-11", "count": 9.0},
    ]

    result = compute_appg_series(target_rows, history_rows)

    assert len(result) == 1
    row = result[0]
    assert row["current_date"] == "2026-05-11"
    assert row["current_value"] == 12.0
    assert row["appg_date"] == "2025-05-11"
    assert row["appg_value"] == 9.0
    assert row["appg_delta_abs"] == 3.0
    assert round(float(row["appg_delta_pct"]), 6) == round((12.0 / 9.0 - 1.0) * 100.0, 6)
    assert row["appg_available"] is True


def test_compute_appg_series_missing_previous_year_date() -> None:
    target_rows = [
        {"date": "2026-05-11", "forecast_value": 12.0},
    ]
    history_rows = [
        {"date": "2025-05-10", "count": 9.0},
    ]

    result = compute_appg_series(target_rows, history_rows)

    assert len(result) == 1
    row = result[0]
    assert row["appg_date"] == "2025-05-11"
    assert row["appg_available"] is False
    assert row["appg_value"] is None
    assert row["appg_delta_abs"] is None
    assert row["appg_delta_pct"] is None


def test_compute_appg_series_leap_to_non_leap_transition() -> None:
    target_rows = [
        {"date": "2024-02-29", "forecast_value": 7.0},
    ]
    history_rows = [
        {"date": "2023-02-28", "count": 5.0},
    ]

    result = compute_appg_series(target_rows, history_rows)

    assert len(result) == 1
    row = result[0]
    assert row["current_date"] == "2024-02-29"
    assert row["appg_date"] == "2023-02-28"
    assert row["appg_available"] is True
    assert row["appg_value"] == 5.0
    assert row["appg_delta_abs"] == 2.0
    assert round(float(row["appg_delta_pct"]), 6) == 40.0

from __future__ import annotations

from datetime import date

from app.services.ml_model.core import _apply_period_filter


def test_period_appg_series_is_built_from_daily_history_for_historical_month() -> None:
    payload = {
        "forecast_rows": [],
        "appg_series": [],
        "appg_period_series": [],
        "filters": {},
        "charts": {},
    }
    daily_history = [
        {"date": date(2024, 5, 1), "count": 2.0},
        {"date": date(2024, 5, 2), "count": 3.0},
        {"date": date(2025, 5, 1), "count": 4.0},
        {"date": date(2025, 5, 2), "count": 5.0},
        {"date": date(2026, 1, 1), "count": 1.0},
    ]

    filtered = _apply_period_filter(
        payload,
        daily_history=daily_history,
        year=2025,
        month=5,
    )

    appg_period = filtered.get("appg_period_series") or []
    assert len(appg_period) == 2
    assert appg_period[0]["current_date"] == "2025-05-01"
    assert appg_period[0]["appg_date"] == "2024-05-01"
    assert appg_period[0]["appg_available"] is True


def test_period_appg_series_is_built_for_full_year_when_month_not_set() -> None:
    payload = {
        "forecast_rows": [],
        "appg_series": [],
        "appg_period_series": [],
        "filters": {},
        "charts": {},
    }
    daily_history = [
        {"date": date(2024, 1, 10), "count": 2.0},
        {"date": date(2024, 8, 10), "count": 3.0},
        {"date": date(2025, 1, 10), "count": 4.0},
        {"date": date(2025, 8, 10), "count": 5.0},
    ]

    filtered = _apply_period_filter(
        payload,
        daily_history=daily_history,
        year=2025,
        month=None,
    )

    appg_period = filtered.get("appg_period_series") or []
    assert len(appg_period) == 2
    assert all(row["current_date"].startswith("2025-") for row in appg_period)
    assert all(row["appg_date"].startswith("2024-") for row in appg_period)

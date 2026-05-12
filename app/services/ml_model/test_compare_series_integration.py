from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.services.ml_model import core as ml_core
from app.services.ml_model.caches import create_default_caches


def test_compare_series_builds_from_history_and_ml_fallback() -> None:
    payload = {"filters": {}, "compare_series": {}}
    daily_history = [
        {"date": date(2025, 5, 1), "count": 4.0},
        {"date": date(2025, 5, 2), "count": 6.0},
    ]

    def _fake_train(*_args, **kwargs):
        anchor = kwargs.get("current_user_date")
        year = anchor.year + 1
        month = anchor.month % 12 + 1
        return {
            "forecast_rows": [
                {"date": f"{year:04d}-{month:02d}-01", "forecast_value": 2.0},
                {"date": f"{year:04d}-{month:02d}-02", "forecast_value": 3.0},
            ]
        }

    with patch.object(ml_core, "_train_ml_model", side_effect=_fake_train):
        result = ml_core._attach_compare_series(
            payload,
            daily_history=daily_history,
            scenario_temperature=None,
            current_user_day=None,
            compare_month=5,
            compare_year_a=2025,
            compare_year_b=2024,
            caches=create_default_caches(),
        )

    compare = result.get("compare_series") or {}
    rows = compare.get("rows") or []
    assert rows
    assert rows[0]["a_source"] == "fact"
    assert rows[0]["b_source"] == "ml"
    assert "appg_series" not in result or isinstance(result.get("appg_series"), list)

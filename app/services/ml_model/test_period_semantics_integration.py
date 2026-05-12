from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.services.ml_model import core as ml_core


def test_period_filter_uses_daily_history_for_appg_even_when_forecast_is_future_year() -> None:
    request_state = {
        "table_options": [{"value": "fires", "label": "fires"}],
        "selected_table": "fires",
        "selected_tables": ["fires"],
        "selected_table_label": "fires",
        "source_tables": ["fires"],
        "source_table_notes": [],
        "days_ahead": 7,
        "selected_history_window": "all",
        "scenario_temperature": None,
        "cache_key": ("ml", "fires", "all"),
        "current_user_day": date(2026, 5, 12),
        "selected_year": 2025,
        "selected_month": 5,
    }
    daily_history = [
        {"date": date(2024, 5, 1), "count": 2.0},
        {"date": date(2024, 5, 2), "count": 3.0},
        {"date": date(2025, 5, 1), "count": 4.0},
        {"date": date(2025, 5, 2), "count": 5.0},
        {"date": date(2026, 5, 11), "count": 1.0},
    ]
    ml_result = {
        "is_ready": True,
        "forecast_rows": [{"date": "2026-05-12", "forecast_value": 2.0}],
        "feature_importance": [],
    }

    def _fake_payload(**_kwargs):
        return {
            "has_data": True,
            "summary": {},
            "quality_assessment": {},
            "features": [],
            "notes": [],
            "filters": {},
            "charts": {},
            "forecast_rows": [{"date": "2026-05-12", "forecast_value": 2.0}],
            "appg_series": [],
            "appg_period_series": [],
            "feature_importance": [],
        }

    with (
        patch.object(ml_core, "_build_ml_request_state", return_value=request_state),
        patch.object(ml_core, "_cache_get", return_value=None),
        patch.object(
            ml_core,
            "_load_ml_filter_bundle",
            return_value={
                "metadata_items": [],
                "preload_notes": [],
                "option_catalog": {"causes": [], "object_categories": []},
                "selected_cause": "all",
                "selected_object_category": "all",
            },
        ),
        patch.object(
            ml_core,
            "_load_ml_aggregation_inputs",
            return_value={"daily_history": daily_history, "filtered_records_count": len(daily_history)},
        ),
        patch.object(ml_core, "_train_ml_model", return_value=ml_result),
        patch.object(ml_core, "_temperature_quality_from_daily_history", return_value={}),
        patch.object(ml_core, "_build_ml_payload", side_effect=_fake_payload),
    ):
        payload = ml_core.get_ml_model_data(
            table_name="fires",
            year=2025,
            month=5,
        )

    period_rows = payload.get("appg_period_series") or []
    assert len(period_rows) >= 2
    assert period_rows[0]["current_date"].startswith("2025-05")
    assert period_rows[0]["appg_date"].startswith("2024-05")

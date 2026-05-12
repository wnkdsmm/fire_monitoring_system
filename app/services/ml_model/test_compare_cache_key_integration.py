from __future__ import annotations

from app.services.ml_model import jobs as ml_jobs
from app.services.shared.request_state import build_ml_cache_key


def _request_state_for_compare(year_a: int, year_b: int) -> dict[str, object]:
    return {
        "cache_key": build_ml_cache_key(
            cache_schema_version=1,
            selected_table="all",
            source_tables=["fires"],
            cause="all",
            object_category="all",
            temperature="",
            days_ahead=7,
            history_window="all",
            current_user_date="2026-05-12",
            compare_month=5,
            compare_year_a=year_a,
            compare_year_b=year_b,
            period_year=None,
            period_month=None,
        )
    }


def test_ml_compare_requests_with_different_years_do_not_reuse_same_cached_payload(monkeypatch) -> None:
    session_id = "ml-compare-cache-key-it"
    ml_jobs._ML_JOB_IDS_BY_CACHE_KEY.clear()

    observed_cache_keys: list[tuple[object, ...]] = []

    def _fake_build_ml_request_state(**kwargs):
        return _request_state_for_compare(
            year_a=int(kwargs.get("year_a") or 0),
            year_b=int(kwargs.get("year_b") or 0),
        )

    def _fake_cache_get(cache_key):
        observed_cache_keys.append(tuple(cache_key))
        if 2025 in cache_key and 2024 in cache_key:
            return {"compare_series": {"year_a": 2025, "year_b": 2024}, "filters": {}, "summary": {}, "notes": [], "charts": {}, "forecast_rows": [], "feature_importance": [], "features": [], "quality_assessment": {}}
        if 2024 in cache_key and 2023 in cache_key:
            return {"compare_series": {"year_a": 2024, "year_b": 2023}, "filters": {}, "summary": {}, "notes": [], "charts": {}, "forecast_rows": [], "feature_importance": [], "features": [], "quality_assessment": {}}
        return None

    monkeypatch.setattr(ml_jobs, "_build_ml_request_state", _fake_build_ml_request_state)
    monkeypatch.setattr(ml_jobs, "_cache_get", _fake_cache_get)

    first = ml_jobs.start_ml_model_job(
        session_id=session_id,
        table_name="all",
        year_a=2025,
        year_b=2024,
        month=5,
    )
    second = ml_jobs.start_ml_model_job(
        session_id=session_id,
        table_name="all",
        year_a=2024,
        year_b=2023,
        month=5,
    )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first["result"]["compare_series"]["year_a"] == 2025
    assert first["result"]["compare_series"]["year_b"] == 2024
    assert second["result"]["compare_series"]["year_a"] == 2024
    assert second["result"]["compare_series"]["year_b"] == 2023
    assert len(observed_cache_keys) >= 2
    assert observed_cache_keys[0] != observed_cache_keys[1]

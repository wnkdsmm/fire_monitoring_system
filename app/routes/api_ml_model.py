from __future__ import annotations

from fastapi import APIRouter, Body, Request

from .api_common import job_status_response, run_session_json_action, utf8_json

router = APIRouter()

_INVALID_ML_MODEL_MESSAGE = "Не удалось обработать параметры ML-анализа."
_FAILED_ML_MODEL_MESSAGE = "Не удалось рассчитать ML-анализ. Попробуйте повторить запрос."


def start_ml_model_job(**kwargs):
    from app.services.ml_model.jobs import start_ml_model_job as _start_ml_model_job

    return _start_ml_model_job(**kwargs)


def get_ml_job_status(**kwargs):
    from app.services.ml_model.jobs import get_ml_job_status as _get_ml_job_status

    return _get_ml_job_status(**kwargs)


def get_ml_compare_series_data(**kwargs):
    from app.services.ml_model.core import get_ml_compare_series_data as _get_ml_compare_series_data

    return _get_ml_compare_series_data(**kwargs)


def _parse_optional_int(payload: dict, key: str) -> int | None:
    raw_value = payload.get(key)
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"Параметр {key} должен быть целым числом.")


@router.post("/api/ml-model-jobs")
def start_ml_model_job_endpoint(request: Request, payload: dict = Body(...)):
    try:
        raw_table_names = payload.get("table_names")
        table_names = (
            [str(item or "").strip() for item in raw_table_names if str(item or "").strip()]
            if isinstance(raw_table_names, list)
            else []
        )
        year = _parse_optional_int(payload, "year")
        month = _parse_optional_int(payload, "month")
        year_a = _parse_optional_int(payload, "year_a")
        year_b = _parse_optional_int(payload, "year_b")
        raw_district = payload.get("district_id")
        if raw_district in (None, ""):
            raw_district = payload.get("district")
        district_id = str(raw_district or "all")

        raw_horizon = payload.get("horizon")
        if raw_horizon in (None, ""):
            raw_horizon = payload.get("forecast_days")
        if raw_horizon in (None, ""):
            horizon = 7
        else:
            try:
                horizon = int(raw_horizon)
            except (TypeError, ValueError):
                raise ValueError("Параметр horizon должен быть целым числом.")

        raw_temperature_scenario = payload.get("temperature_scenario")
        if raw_temperature_scenario in (None, ""):
            raw_temperature_scenario = payload.get("temperature")
        temperature_scenario = str(raw_temperature_scenario or "")

        return run_session_json_action(
            request,
            lambda session_id: start_ml_model_job(
                session_id=session_id,
                table_name=str(payload.get("table_name") or "all"),
                table_names=table_names,
                district_id=district_id,
                horizon=horizon,
                temperature_scenario=temperature_scenario,
                cause=str(payload.get("cause") or "all"),
                object_category=str(payload.get("object_category") or "all"),
                current_user_date=str(payload.get("current_user_date") or ""),
                year=year,
                month=month,
                year_a=year_a,
                year_b=year_b,
            ),
        )
    except ValueError as exc:
        return utf8_json({"status": "failed", "error_message": str(exc) or _INVALID_ML_MODEL_MESSAGE}, status_code=400)
    except Exception:
        return utf8_json({"status": "failed", "error_message": _FAILED_ML_MODEL_MESSAGE}, status_code=500)


@router.get("/api/ml-model-jobs/{job_id}")
def ml_model_job_status_endpoint(request: Request, job_id: str):
    return job_status_response(request, job_id, get_ml_job_status)


@router.post("/api/ml-compare-series")
def ml_compare_series_endpoint(request: Request, payload: dict = Body(...)):
    try:
        raw_table_names = payload.get("table_names")
        table_names = (
            [str(item or "").strip() for item in raw_table_names if str(item or "").strip()]
            if isinstance(raw_table_names, list)
            else []
        )
        month = _parse_optional_int(payload, "month")
        year_a = _parse_optional_int(payload, "year_a")
        year_b = _parse_optional_int(payload, "year_b")
        if month is None or year_a is None or year_b is None:
            return utf8_json(
                {"status": "failed", "error_message": "Параметры month, year_a и year_b обязательны."},
                status_code=400,
            )
        return run_session_json_action(
            request,
            lambda _session_id: {
                "status": "completed",
                "result": get_ml_compare_series_data(
                    table_name=str(payload.get("table_name") or "all"),
                    table_names=table_names,
                    cause=str(payload.get("cause") or "all"),
                    object_category=str(payload.get("object_category") or "all"),
                    month=month,
                    year_a=year_a,
                    year_b=year_b,
                    current_user_date=str(payload.get("current_user_date") or ""),
                ),
            },
        )
    except ValueError as exc:
        return utf8_json({"status": "failed", "error_message": str(exc) or _INVALID_ML_MODEL_MESSAGE}, status_code=400)
    except Exception:
        return utf8_json({"status": "failed", "error_message": _FAILED_ML_MODEL_MESSAGE}, status_code=500)

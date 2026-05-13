from __future__ import annotations

from fastapi import APIRouter, Body, Request

from .api_common import run_session_json_action, utf8_json

router = APIRouter()

_INVALID_ML_MODEL_MESSAGE = "Не удалось обработать параметры ML-анализа."
_FAILED_ML_MODEL_MESSAGE = "Не удалось рассчитать ML-анализ. Попробуйте повторить запрос."


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

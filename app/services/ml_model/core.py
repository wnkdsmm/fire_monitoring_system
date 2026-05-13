from __future__ import annotations

from calendar import monthrange
from datetime import datetime
import re
from typing import Any, Sequence

from app.services.forecasting.data import (
    _build_forecasting_table_options,
    _resolve_forecasting_selection,
    _selected_source_table_notes,
    _selected_source_tables,
    clear_forecasting_sql_cache,
)
from app.services.forecasting.utils import _parse_optional_iso_date
from app.services.shared.request_state import (
    build_ml_compare_cache_key as _build_ml_compare_cache_key,
    build_ml_request_state as _build_ml_request_state_impl,
)

from .caches import MLModelCaches, create_default_caches
from .ml_model_config_types import FIXED_FORECAST_DAYS, ML_CACHE_SCHEMA_VERSION
from .training.compare_series import build_compare_series
from .training.data_access import (
    clear_ml_model_input_cache,
    load_ml_aggregation_inputs as _load_ml_aggregation_inputs_impl,
    load_ml_filter_bundle as _load_ml_filter_bundle_impl,
)

_DEFAULT_CACHES = create_default_caches()
_MIN_SELECTABLE_YEAR = 1990
_MAX_SELECTABLE_YEAR = 2100
_DEFAULT_COMPARE_YEAR_A = 2024
_DEFAULT_COMPARE_YEAR_B = 2025
_YEAR_TOKEN_RE = re.compile(r"(19\d{2}|20\d{2}|2100)")


def _selected_table_label(table_names: Sequence[str], *, selected_table: str) -> str:
    concrete = [str(item or "").strip() for item in table_names if str(item or "").strip()]
    if selected_table == "all":
        return "Все таблицы"
    if not concrete:
        return "Нет таблицы"
    if len(concrete) == 1:
        return concrete[0]
    preview = ", ".join(concrete[:2])
    suffix = "" if len(concrete) <= 2 else f" +{len(concrete) - 2}"
    return f"{preview}{suffix}"


def _extract_available_years_from_table_options(table_options: list[dict[str, str]]) -> list[dict[str, str]]:
    years: set[int] = set()
    for option in table_options:
        value = str((option or {}).get("value") or "").strip()
        if not value or value == "all":
            continue
        for token in _YEAR_TOKEN_RE.findall(value):
            year = int(token)
            if 1900 <= year <= 2100:
                years.add(year)
    return [{"value": str(year), "label": str(year)} for year in sorted(years, reverse=True)]


def _normalize_compare_selection(
    *,
    month: int | None,
    year_a: int | None,
    year_b: int | None,
    current_user_date: str,
) -> tuple[int, int, int]:
    parsed_current = _parse_optional_iso_date(current_user_date)
    baseline = parsed_current or datetime.now().date()
    normalized_month = int(month) if month is not None else int(baseline.month)
    if normalized_month < 1 or normalized_month > 12:
        raise ValueError("Параметр month должен быть в диапазоне 1..12.")
    normalized_year_a = int(year_a) if year_a is not None else _DEFAULT_COMPARE_YEAR_A
    normalized_year_b = int(year_b) if year_b is not None else _DEFAULT_COMPARE_YEAR_B
    if normalized_year_a < _MIN_SELECTABLE_YEAR or normalized_year_a > _MAX_SELECTABLE_YEAR:
        raise ValueError(f"Параметр year_a должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.")
    if normalized_year_b < _MIN_SELECTABLE_YEAR or normalized_year_b > _MAX_SELECTABLE_YEAR:
        raise ValueError(f"Параметр year_b должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.")
    return normalized_month, normalized_year_a, normalized_year_b


def _build_ml_request_state(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    current_user_date: str = "",
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
) -> dict[str, Any]:
    parsed_current_user_date = _parse_optional_iso_date(current_user_date)
    normalized_current_user_date = parsed_current_user_date.isoformat() if parsed_current_user_date is not None else ""
    selected_compare_month, selected_compare_year_a, selected_compare_year_b = _normalize_compare_selection(
        month=month,
        year_a=year_a,
        year_b=year_b,
        current_user_date=normalized_current_user_date,
    )

    state = _build_ml_request_state_impl(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        temperature="",
        forecast_days=str(FIXED_FORECAST_DAYS),
        history_window="all",
        current_user_date=normalized_current_user_date,
        cache_schema_version=ML_CACHE_SCHEMA_VERSION,
        table_options_builder=_build_forecasting_table_options,
        selection_resolver=_resolve_forecasting_selection,
        source_tables_resolver=_selected_source_tables,
        source_notes_resolver=_selected_source_table_notes,
    )

    selected_table = str(state.get("selected_table") or "all")
    selected_tables = list(state.get("source_tables") or [])
    state["selected_tables"] = selected_tables
    state["selected_table_label"] = _selected_table_label(selected_tables, selected_table=selected_table)
    state["selected_compare_month"] = selected_compare_month
    state["selected_compare_year_a"] = selected_compare_year_a
    state["selected_compare_year_b"] = selected_compare_year_b
    state["current_user_date"] = normalized_current_user_date
    return state


def get_ml_model_shell_context(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    temperature: str = "",
    forecast_days: str = str(FIXED_FORECAST_DAYS),
    history_window: str = "all",
    current_user_date: str = "",
    prefer_cached: bool = False,
    caches: MLModelCaches | None = None,
) -> dict[str, Any]:
    del temperature, forecast_days, history_window, prefer_cached, caches
    request_state = _build_ml_request_state(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        current_user_date=current_user_date,
    )
    table_options = list(request_state.get("table_options") or [])
    selected_table = str(request_state.get("selected_table") or "all")
    selected_tables = list(request_state.get("selected_tables") or [])
    selected_table_label = str(request_state.get("selected_table_label") or _selected_table_label(selected_tables, selected_table=selected_table))

    initial_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "has_data": bool(table_options),
        "summary": {
            "selected_table_label": selected_table_label,
            "history_period_label": "По всем доступным годам",
            "fires_count_display": "-",
        },
        "compare_series": {},
        "filters": {
            "table_name": selected_table,
            "table_names": selected_tables,
            "available_tables": table_options,
            "available_years": _extract_available_years_from_table_options(table_options),
            "cause": str(cause or "all"),
            "object_category": str(object_category or "all"),
            "compare_month": int(request_state.get("selected_compare_month") or datetime.now().month),
            "year_a": int(request_state.get("selected_compare_year_a") or _DEFAULT_COMPARE_YEAR_A),
            "year_b": int(request_state.get("selected_compare_year_b") or _DEFAULT_COMPARE_YEAR_B),
        },
    }
    return {
        "generated_at": initial_data["generated_at"],
        "initial_data": initial_data,
        "plotly_js": "",
        "has_data": bool(table_options),
    }


def _load_ml_filter_bundle(*, source_tables: list[str], cause: str, object_category: str) -> dict[str, Any]:
    from app.services.forecasting.data import (
        _build_option_catalog_sql,
        _collect_forecasting_metadata,
    )
    from app.services.forecasting.utils import _resolve_option_value

    return _load_ml_filter_bundle_impl(
        source_tables=source_tables,
        selected_history_window="all",
        cause=cause,
        object_category=object_category,
        collect_forecasting_metadata=_collect_forecasting_metadata,
        build_option_catalog_sql=_build_option_catalog_sql,
        resolve_option_value=_resolve_option_value,
    )


def _load_ml_aggregation_inputs(*, source_tables: list[str], filter_bundle: dict[str, Any]) -> dict[str, Any]:
    from app.services.forecasting.data import (
        _build_daily_history_sql,
        _count_forecasting_records_sql,
    )

    return _load_ml_aggregation_inputs_impl(
        source_tables=source_tables,
        selected_history_window="all",
        filter_bundle=filter_bundle,
        build_daily_history_sql=_build_daily_history_sql,
        count_forecasting_records_sql=_count_forecasting_records_sql,
    )


def _build_compare_series_payload(
    *,
    month: int,
    year_a: int,
    year_b: int,
    daily_history: list[dict[str, Any]],
) -> dict[str, Any]:
    ml_rows_cache: dict[tuple[int, int], dict[int, float | None]] = {}
    history_has_data = bool(daily_history)

    def _predict_month_with_trained_ml(target_year: int, target_month: int) -> dict[int, float | None]:
        month_days = int(monthrange(int(target_year), int(target_month))[1])
        history_before_month: list[dict[str, Any]] = []
        for row in daily_history:
            row_date = _parse_optional_iso_date(str(row.get("date") or ""))
            if row_date is None:
                continue
            if row_date.month != int(target_month) or row_date.year >= int(target_year):
                continue
            raw_count = row.get("count")
            if raw_count is None:
                continue
            try:
                count_value = float(raw_count)
            except (TypeError, ValueError):
                continue
            history_before_month.append({"date": row_date.isoformat(), "count": count_value})

        if not history_before_month:
            return {}

        by_day: dict[int, list[float]] = {}
        all_values: list[float] = []
        for item in history_before_month:
            item_date = _parse_optional_iso_date(str(item.get("date") or ""))
            if item_date is None:
                continue
            numeric_value = float(item.get("count") or 0.0)
            by_day.setdefault(int(item_date.day), []).append(numeric_value)
            all_values.append(numeric_value)

        if not all_values:
            return {}

        overall_mean = sum(all_values) / float(len(all_values))
        result: dict[int, float | None] = {}
        for day in range(1, month_days + 1):
            day_values = by_day.get(day) or []
            result[day] = max(0.0, sum(day_values) / float(len(day_values))) if day_values else max(0.0, overall_mean)
        return result

    facts_by_year_day: dict[tuple[int, int], set[int]] = {}
    for row in daily_history:
        row_date = _parse_optional_iso_date(str(row.get("date") or ""))
        if row_date is None or row_date.month != int(month):
            continue
        raw_value = row.get("count")
        if raw_value is None:
            continue
        try:
            float(raw_value)
        except (TypeError, ValueError):
            continue
        key = (int(row_date.year), int(row_date.month))
        facts_by_year_day.setdefault(key, set()).add(int(row_date.day))

    month_days_a = int(monthrange(int(year_a), int(month))[1])
    month_days_b = int(monthrange(int(year_b), int(month))[1])
    required_days_by_year: dict[int, set[int]] = {
        int(year_a): {day for day in range(1, month_days_a + 1) if day not in facts_by_year_day.get((int(year_a), int(month)), set())},
        int(year_b): {day for day in range(1, month_days_b + 1) if day not in facts_by_year_day.get((int(year_b), int(month)), set())},
    }
    ml_invoked_by_year: dict[int, bool] = {int(year_a): False, int(year_b): False}

    def _ml_month_provider(year_value: int, month_value: int) -> dict[int, float | None]:
        cache_key = (int(year_value), int(month_value))
        if cache_key in ml_rows_cache:
            return ml_rows_cache[cache_key]
        needed_days = required_days_by_year.get(int(year_value), set())
        if not needed_days or not history_has_data:
            ml_rows_cache[cache_key] = {}
            return ml_rows_cache[cache_key]
        ml_invoked_by_year[int(year_value)] = True
        month_rows = _predict_month_with_trained_ml(int(year_value), int(month_value))
        month_rows = {int(day): month_rows.get(int(day)) for day in needed_days} if month_rows else {}
        ml_rows_cache[cache_key] = month_rows
        return month_rows

    compare_payload = build_compare_series(
        month=int(month),
        year_a=int(year_a),
        year_b=int(year_b),
        daily_history=daily_history,
        ml_month_provider=_ml_month_provider,
        history_date_key="date",
        history_value_key="count",
    )

    a_summary = compare_payload.get("a_summary") or {}
    b_summary = compare_payload.get("b_summary") or {}

    def _resolve_mode(summary: dict[str, Any]) -> str:
        fact_days = int(summary.get("fact_days") or 0)
        ml_days = int(summary.get("ml_days") or 0)
        if fact_days > 0 and ml_days == 0:
            return "fact"
        if fact_days == 0 and ml_days > 0:
            return "ml"
        if fact_days > 0 and ml_days > 0:
            return "mixed"
        return "empty"

    a_mode = _resolve_mode(a_summary)
    b_mode = _resolve_mode(b_summary)
    if a_mode == "fact" and b_mode == "fact":
        overall_mode = "fact_fact"
    elif a_mode == "ml" and b_mode == "ml":
        overall_mode = "ml_ml"
    elif a_mode == "empty" and b_mode == "empty":
        overall_mode = "empty"
    else:
        overall_mode = "mixed"

    compare_payload["ml_usage"] = {
        "year_a": {
            "year": int(year_a),
            "fact_points": int(a_summary.get("fact_days") or 0),
            "ml_points": int(a_summary.get("ml_days") or 0),
            "ml_invoked": bool(ml_invoked_by_year.get(int(year_a), False)),
        },
        "year_b": {
            "year": int(year_b),
            "fact_points": int(b_summary.get("fact_days") or 0),
            "ml_points": int(b_summary.get("ml_days") or 0),
            "ml_invoked": bool(ml_invoked_by_year.get(int(year_b), False)),
        },
    }
    compare_payload["modes"] = {"year_a": a_mode, "year_b": b_mode, "overall": overall_mode}
    compare_payload["history_has_data"] = history_has_data
    return compare_payload


def get_ml_compare_series_data(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    current_user_date: str = "",
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    caches: MLModelCaches | None = None,
) -> dict[str, Any]:
    cache_set = caches or _DEFAULT_CACHES
    request_state = _build_ml_request_state(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        current_user_date=current_user_date,
        month=month,
        year_a=year_a,
        year_b=year_b,
    )

    selected_compare_month = int(request_state.get("selected_compare_month") or 0)
    selected_compare_year_a = int(request_state.get("selected_compare_year_a") or 0)
    selected_compare_year_b = int(request_state.get("selected_compare_year_b") or 0)
    available_years = _extract_available_years_from_table_options(list(request_state.get("table_options") or []))

    compare_cache_key = _build_ml_compare_cache_key(
        cache_schema_version=ML_CACHE_SCHEMA_VERSION,
        selected_tables=tuple(request_state.get("source_tables") or []),
        cause=str(cause or "all"),
        object_category=str(object_category or "all"),
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_b,
        current_user_date=str(request_state.get("current_user_date") or ""),
    )

    cached = cache_set.compare_cache.get(compare_cache_key)
    if isinstance(cached, dict):
        return cached

    source_tables = list(request_state.get("source_tables") or [])
    if not source_tables:
        result_payload = {
            "compare_series": {
                "month": selected_compare_month,
                "year_a": selected_compare_year_a,
                "year_b": selected_compare_year_b,
                "rows": [],
                "a_summary": {"fact_days": 0, "ml_days": 0},
                "b_summary": {"fact_days": 0, "ml_days": 0},
                "history_has_data": False,
            },
            "filters": {
                "table_name": request_state.get("selected_table", "all"),
                "table_names": list(request_state.get("selected_tables") or []),
                "available_tables": list(request_state.get("table_options") or []),
                "available_years": available_years,
                "cause": cause or "all",
                "object_category": object_category or "all",
                "compare_month": selected_compare_month,
                "year_a": selected_compare_year_a,
                "year_b": selected_compare_year_b,
            },
        }
        return cache_set.compare_cache.set(compare_cache_key, result_payload)

    filter_bundle = _load_ml_filter_bundle(
        source_tables=source_tables,
        cause=cause,
        object_category=object_category,
    )
    aggregation_inputs = _load_ml_aggregation_inputs(source_tables=source_tables, filter_bundle=filter_bundle)
    daily_history = aggregation_inputs.get("daily_history", [])
    compare_series = _build_compare_series_payload(
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_b,
        daily_history=daily_history,
    )
    result_payload = {
        "compare_series": compare_series,
        "filters": {
            "table_name": request_state.get("selected_table", "all"),
            "table_names": list(request_state.get("selected_tables") or []),
            "available_tables": list(request_state.get("table_options") or []),
            "available_years": available_years,
            "cause": cause or "all",
            "object_category": object_category or "all",
            "compare_month": selected_compare_month,
            "year_a": selected_compare_year_a,
            "year_b": selected_compare_year_b,
        },
    }
    return cache_set.compare_cache.set(compare_cache_key, result_payload)


def clear_ml_model_cache(caches: MLModelCaches | None = None) -> None:
    cache_set = caches or _DEFAULT_CACHES
    cache_set.ml_cache.clear()
    cache_set.compare_cache.clear()
    clear_ml_model_input_cache()
    clear_forecasting_sql_cache()

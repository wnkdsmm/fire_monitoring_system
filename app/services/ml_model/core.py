from __future__ import annotations

from calendar import isleap, monthrange
from datetime import date, datetime, timedelta
import math
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
_DEFAULT_COMPARE_YEAR_ML_OFFSET = 3
_YEAR_TOKEN_RE = re.compile(r"(19\d{2}|20\d{2}|2100)")


def _load_poisson_dependencies() -> tuple[Any, Any] | None:
    try:
        import numpy as np  # type: ignore
        from sklearn.linear_model import PoissonRegressor  # type: ignore
    except Exception:
        return None
    return np, PoissonRegressor


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
    year_ml: int | None,
    current_user_date: str,
) -> tuple[int, int, int, int]:
    parsed_current = _parse_optional_iso_date(current_user_date)
    baseline = parsed_current or datetime.now().date()
    normalized_month = int(month) if month is not None else int(baseline.month)
    if normalized_month < 1 or normalized_month > 12:
        raise ValueError("Параметр month должен быть в диапазоне 1..12.")
    normalized_year_a = int(year_a) if year_a is not None else _DEFAULT_COMPARE_YEAR_A
    normalized_year_b = int(year_b) if year_b is not None else _DEFAULT_COMPARE_YEAR_B
    normalized_year_ml = int(year_ml) if year_ml is not None else int(baseline.year)
    if normalized_year_a < _MIN_SELECTABLE_YEAR or normalized_year_a > _MAX_SELECTABLE_YEAR:
        raise ValueError(f"Параметр year_a должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.")
    if normalized_year_b < _MIN_SELECTABLE_YEAR or normalized_year_b > _MAX_SELECTABLE_YEAR:
        raise ValueError(f"Параметр year_b должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.")
    if normalized_year_ml < _MIN_SELECTABLE_YEAR or normalized_year_ml > _MAX_SELECTABLE_YEAR:
        raise ValueError(f"Параметр year_ml должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.")
    return normalized_month, normalized_year_a, normalized_year_b, normalized_year_ml


def _build_ml_request_state(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    current_user_date: str = "",
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    year_ml: int | None = None,
) -> dict[str, Any]:
    parsed_current_user_date = _parse_optional_iso_date(current_user_date)
    normalized_current_user_date = parsed_current_user_date.isoformat() if parsed_current_user_date is not None else ""
    selected_compare_month, selected_compare_year_a, selected_compare_year_b, selected_compare_year_ml = _normalize_compare_selection(
        month=month,
        year_a=year_a,
        year_b=year_b,
        year_ml=year_ml,
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
    state["selected_compare_year_ml"] = selected_compare_year_ml
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
            "year_ml": int(request_state.get("selected_compare_year_ml") or datetime.now().year),
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
        by_year: dict[int, list[float]] = {}
        by_day_year: dict[int, dict[int, list[float]]] = {}
        for item in history_before_month:
            item_date = _parse_optional_iso_date(str(item.get("date") or ""))
            if item_date is None:
                continue
            numeric_value = float(item.get("count") or 0.0)
            by_day.setdefault(int(item_date.day), []).append(numeric_value)
            all_values.append(numeric_value)
            by_year.setdefault(int(item_date.year), []).append(numeric_value)
            by_day_year.setdefault(int(item_date.day), {}).setdefault(int(item_date.year), []).append(numeric_value)

        if not all_values:
            return {}

        overall_mean = sum(all_values) / float(len(all_values))
        latest_history_year = max(by_year.keys()) if by_year else int(target_year)
        future_year_shift = max(0, int(target_year) - int(latest_history_year))

        def _ols_slope_capped(xs: list[float], ys: list[float], y_mean: float) -> float:
            x_mean = sum(xs) / float(len(xs))
            denom = sum((x - x_mean) ** 2 for x in xs)
            if denom <= 0:
                return 0.0
            raw_slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
            slope_limit = max(1.0, abs(y_mean)) * 0.15
            return max(-slope_limit, min(slope_limit, raw_slope))

        # Month-level trend: fallback when a day has too few years to fit reliably.
        trend_month = 0.0
        _need_trend = by_year and int(target_year) > int(latest_history_year) and len(by_year) >= 2
        if _need_trend:
            years_sorted = sorted(by_year.keys())
            xs_m = [float(y) for y in years_sorted]
            ys_m = [sum(by_year[y]) / float(len(by_year[y])) for y in years_sorted]
            trend_month = _ols_slope_capped(xs_m, ys_m, sum(ys_m) / float(len(ys_m)))

        _MIN_YEARS_DAY_TREND = 10

        def _day_slope(day: int) -> float:
            if not _need_trend:
                return 0.0
            day_year_map = by_day_year.get(int(day)) or {}
            if len(day_year_map) < _MIN_YEARS_DAY_TREND:
                return trend_month
            year_keys = sorted(day_year_map.keys())
            xs_d = [float(y) for y in year_keys]
            ys_d = [sum(day_year_map[y]) / float(len(day_year_map[y])) for y in year_keys]
            return _ols_slope_capped(xs_d, ys_d, sum(ys_d) / float(len(ys_d)))

        result: dict[int, float | None] = {}
        for day in range(1, month_days + 1):
            day_values = by_day.get(day) or []
            base_value = (sum(day_values) / float(len(day_values))) if day_values else overall_mean
            if future_year_shift > 0:
                slope = _day_slope(day)
                if slope != 0.0:
                    base_value = base_value + slope * float(future_year_shift)
            result[day] = max(0.0, base_value)
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


def _predict_month_poisson_ml(
    *,
    daily_history: list[dict[str, Any]],
    target_year: int,
    target_month: int,
) -> tuple[dict[int, float | None], dict[str, int]]:
    month_days = int(monthrange(int(target_year), int(target_month))[1])
    first_target_day = date(int(target_year), int(target_month), 1)
    parsed_history: list[tuple[date, float]] = []
    for row in daily_history:
        row_date = _parse_optional_iso_date(str(row.get("date") or ""))
        if row_date is None or row_date >= first_target_day:
            continue
        raw_value = row.get("count")
        if raw_value is None:
            continue
        try:
            count_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(count_value):
            continue
        parsed_history.append((row_date, max(0.0, count_value)))

    summary = {"model_days": 0, "clipped_days": 0}
    if not parsed_history:
        return ({day: None for day in range(1, month_days + 1)}, summary)

    parsed_history.sort(key=lambda item: item[0])
    series_by_date: dict[date, float] = {dt: value for dt, value in parsed_history}

    same_month_history = [(dt, value) for dt, value in parsed_history if dt.month == int(target_month)]
    stat_source = same_month_history if same_month_history else parsed_history
    stat_values = [value for _, value in stat_source]
    global_mean = sum(stat_values) / float(len(stat_values)) if stat_values else 0.0
    global_mean = max(0.0, global_mean)

    by_day_of_month: dict[int, list[float]] = {}
    for dt, value in stat_source:
        by_day_of_month.setdefault(int(dt.day), []).append(float(value))

    def _baseline_for_day(day: int) -> float:
        day_values = by_day_of_month.get(int(day)) or []
        if day_values:
            return max(0.0, float(sum(day_values) / float(len(day_values))))
        return global_mean

    def _build_month_baseline() -> dict[int, float]:
        return {day: _baseline_for_day(day) for day in range(1, month_days + 1)}

    # Fall back to day-of-month baseline when history is too short for lag features.
    if len(parsed_history) < 60:
        baseline = _build_month_baseline()
        summary["clipped_days"] = month_days
        return baseline, summary

    deps = _load_poisson_dependencies()
    if deps is None:
        baseline = _build_month_baseline()
        summary["clipped_days"] = month_days
        return baseline, summary
    np, PoissonRegressor = deps

    def _build_features(day: date, value_lookup: dict[date, float], predicted_lookup: dict[date, float]) -> list[float]:
        def _lag_value(offset: int) -> float:
            lag_day = day - timedelta(days=int(offset))
            if lag_day in value_lookup:
                return float(value_lookup[lag_day])
            if lag_day in predicted_lookup:
                return float(predicted_lookup[lag_day])
            return global_mean

        def _rolling_mean(window: int) -> float:
            values: list[float] = []
            for step in range(1, int(window) + 1):
                source_day = day - timedelta(days=step)
                if source_day in value_lookup:
                    values.append(float(value_lookup[source_day]))
                elif source_day in predicted_lookup:
                    values.append(float(predicted_lookup[source_day]))
            if values:
                return float(sum(values) / float(len(values)))
            return global_mean

        day_of_year = int(day.timetuple().tm_yday)
        year_days = 366.0 if isleap(day.year) else 365.0
        phase = 2.0 * math.pi * float(day_of_year) / year_days
        return [
            float(day.day),
            float(day.month),
            float(day.weekday()),
            1.0 if day.weekday() >= 5 else 0.0,
            _lag_value(7),
            _lag_value(14),
            _rolling_mean(7),
            _rolling_mean(14),
            math.sin(phase),
            math.cos(phase),
        ]

    training_dates = [dt for dt, _ in parsed_history]
    X_train: list[list[float]] = []
    y_train: list[float] = []
    for dt in training_dates:
        X_train.append(_build_features(dt, series_by_date, {}))
        y_train.append(float(series_by_date[dt]))

    try:
        model = PoissonRegressor(alpha=0.05, max_iter=500)
        model.fit(np.asarray(X_train, dtype=float), np.asarray(y_train, dtype=float))
    except Exception:
        baseline = _build_month_baseline()
        summary["clipped_days"] = month_days
        return baseline, summary

    predicted_dates: dict[date, float] = {}
    result: dict[int, float | None] = {}
    for day in range(1, month_days + 1):
        current_day = date(int(target_year), int(target_month), int(day))
        used_fallback = False
        try:
            features = _build_features(current_day, series_by_date, predicted_dates)
            raw_pred = float(model.predict(np.asarray([features], dtype=float))[0])
        except Exception:
            raw_pred = _baseline_for_day(day)
            used_fallback = True
        if not math.isfinite(raw_pred):
            raw_pred = _baseline_for_day(day)
            used_fallback = True
        pred = max(0.0, raw_pred)
        predicted_dates[current_day] = pred
        result[int(day)] = pred
        summary["model_days"] += 1
        if used_fallback:
            summary["clipped_days"] += 1
    return result, summary


def _append_compare_series_line(
    *,
    compare_payload: dict[str, Any],
    compare_line_payload: dict[str, Any],
    year_ml: int,
) -> dict[str, Any]:
    rows = list(compare_payload.get("rows") or [])
    compare_rows = list(compare_line_payload.get("rows") or [])
    c_by_day: dict[int, dict[str, Any]] = {}
    for row in compare_rows:
        day = row.get("day")
        if day is None:
            continue
        c_by_day[int(day)] = {
            "c_value": row.get("b_value"),
            "c_source": row.get("b_source") or "ml",
        }

    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        day = normalized.get("day")
        c_row = c_by_day.get(int(day)) if day is not None else None
        if c_row is None:
            normalized["c_value"] = None
            normalized["c_source"] = "ml"
        else:
            normalized["c_value"] = c_row.get("c_value")
            normalized["c_source"] = str(c_row.get("c_source") or "ml")
        merged_rows.append(normalized)

    merged_payload = dict(compare_payload)
    merged_payload["rows"] = merged_rows
    merged_payload["year_ml"] = int(year_ml)
    merged_payload["c_summary"] = dict(compare_line_payload.get("b_summary") or {"fact_days": 0, "ml_days": 0})
    merged_payload["ml_usage"] = {
        **dict(compare_payload.get("ml_usage") or {}),
        "year_ml": dict((compare_line_payload.get("ml_usage") or {}).get("year_b") or {}),
    }
    merged_modes = dict(compare_payload.get("modes") or {})
    merged_modes["year_ml"] = str(((compare_line_payload.get("modes") or {}).get("year_b") or "empty"))
    merged_payload["modes"] = merged_modes
    return merged_payload


def _append_poisson_ml_line(
    *,
    compare_payload: dict[str, Any],
    daily_history: list[dict[str, Any]],
    year_ml: int,
) -> dict[str, Any]:
    month = int(compare_payload.get("month") or 0)
    rows = list(compare_payload.get("rows") or [])
    predicted_by_day, d_summary = _predict_month_poisson_ml(
        daily_history=daily_history,
        target_year=int(year_ml),
        target_month=month,
    )
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        day = int(normalized.get("day") or 0)
        d_value = predicted_by_day.get(day)
        normalized["d_value"] = float(d_value) if d_value is not None and math.isfinite(float(d_value)) else None
        normalized["d_source"] = "ml_model"
        merged_rows.append(normalized)
    merged = dict(compare_payload)
    merged["rows"] = merged_rows
    merged["year_model"] = int(year_ml)
    merged["d_summary"] = {
        "model_days": int(d_summary.get("model_days") or 0),
        "clipped_days": int(d_summary.get("clipped_days") or 0),
    }
    return merged


def _evaluate_poisson_backtest(
    *,
    daily_history: list[dict[str, Any]],
    target_month: int,
    year_ml: int,
) -> dict[str, Any]:
    default = {
        "quality_available": False,
        "mae": None,
        "rmse": None,
        "smape": None,
        "sample_size": 0,
        "folds_used": 0,
        "reason": "insufficient_history",
    }
    try:
        if _load_poisson_dependencies() is None:
            return {**default, "reason": "model_unavailable"}

        facts_by_year_day: dict[int, dict[int, float]] = {}
        for row in daily_history:
            row_date = _parse_optional_iso_date(str(row.get("date") or ""))
            if row_date is None or row_date.month != int(target_month) or row_date.year >= int(year_ml):
                continue
            raw = row.get("count")
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            facts_by_year_day.setdefault(int(row_date.year), {})[int(row_date.day)] = max(0.0, float(value))

        candidate_years = sorted(facts_by_year_day.keys())
        if len(candidate_years) < 2:
            return default
        fold_years = candidate_years[-5:]

        abs_errors: list[float] = []
        sq_errors: list[float] = []
        smape_values: list[float] = []
        folds_used = 0

        for test_year in fold_years:
            actual_by_day = facts_by_year_day.get(int(test_year)) or {}
            if not actual_by_day:
                continue
            pred_by_day, _summary = _predict_month_poisson_ml(
                daily_history=daily_history,
                target_year=int(test_year),
                target_month=int(target_month),
            )
            fold_count = 0
            for day, actual in actual_by_day.items():
                pred = pred_by_day.get(int(day))
                if pred is None:
                    continue
                pred_value = float(pred)
                if not math.isfinite(pred_value):
                    continue
                err = pred_value - float(actual)
                abs_errors.append(abs(err))
                sq_errors.append(err * err)
                denom = abs(float(actual)) + abs(pred_value)
                smape_values.append((200.0 * abs(err) / denom) if denom > 0.0 else 0.0)
                fold_count += 1
            if fold_count > 0:
                folds_used += 1

        sample_size = len(abs_errors)
        if folds_used == 0 or sample_size == 0:
            return {**default, "reason": "insufficient_targets", "folds_used": int(folds_used), "sample_size": int(sample_size)}

        mae = sum(abs_errors) / float(sample_size)
        rmse = math.sqrt(sum(sq_errors) / float(sample_size))
        smape = sum(smape_values) / float(sample_size)
        if not (math.isfinite(mae) and math.isfinite(rmse) and math.isfinite(smape)):
            return {**default, "reason": "insufficient_targets", "folds_used": int(folds_used), "sample_size": int(sample_size)}

        return {
            "quality_available": True,
            "mae": float(mae),
            "rmse": float(rmse),
            "smape": float(smape),
            "sample_size": int(sample_size),
            "folds_used": int(folds_used),
            "reason": None,
        }
    except Exception:
        return {**default, "reason": "evaluation_error"}


def get_ml_compare_series_data(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    current_user_date: str = "",
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    year_ml: int | None = None,
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
        year_ml=year_ml,
    )

    selected_compare_month = int(request_state.get("selected_compare_month") or 0)
    selected_compare_year_a = int(request_state.get("selected_compare_year_a") or 0)
    selected_compare_year_b = int(request_state.get("selected_compare_year_b") or 0)
    selected_compare_year_ml = int(request_state.get("selected_compare_year_ml") or 0)
    available_years = _extract_available_years_from_table_options(list(request_state.get("table_options") or []))

    compare_cache_key = _build_ml_compare_cache_key(
        cache_schema_version=ML_CACHE_SCHEMA_VERSION,
        selected_tables=tuple(request_state.get("source_tables") or []),
        cause=str(cause or "all"),
        object_category=str(object_category or "all"),
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_b,
        year_ml=selected_compare_year_ml,
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
                "year_ml": selected_compare_year_ml,
                "rows": [],
                "a_summary": {"fact_days": 0, "ml_days": 0},
                "b_summary": {"fact_days": 0, "ml_days": 0},
                "c_summary": {"fact_days": 0, "ml_days": 0},
                "d_summary": {"model_days": 0, "clipped_days": 0},
                "d_quality": {
                    "quality_available": False,
                    "mae": None,
                    "rmse": None,
                    "smape": None,
                    "sample_size": 0,
                    "folds_used": 0,
                    "reason": "insufficient_history",
                },
                "year_model": selected_compare_year_ml,
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
                "year_ml": selected_compare_year_ml,
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
    compare_series_ml = _build_compare_series_payload(
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_ml,
        daily_history=daily_history,
    )
    compare_series = _append_compare_series_line(
        compare_payload=compare_series,
        compare_line_payload=compare_series_ml,
        year_ml=selected_compare_year_ml,
    )
    compare_series = _append_poisson_ml_line(
        compare_payload=compare_series,
        daily_history=daily_history,
        year_ml=selected_compare_year_ml,
    )
    compare_series["d_quality"] = _evaluate_poisson_backtest(
        daily_history=daily_history,
        target_month=selected_compare_month,
        year_ml=selected_compare_year_ml,
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
            "year_ml": selected_compare_year_ml,
        },
    }
    return cache_set.compare_cache.set(compare_cache_key, result_payload)


def _load_cause_counts_by_year(
    *,
    metadata_items: list[Any],
    target_month: int,
    year_a: int,
    year_b: int,
    object_category: str = "all",
    top_n: int = 10,
) -> tuple[list[dict[str, Any]], list[str]]:
    from app.services.forecasting.utils import _date_expression, _text_expression
    from app.services.forecasting.selection import _normalize_filter_value
    from app.shared.sql_utils import quote_identifier
    from config.db import engine
    from sqlalchemy import text as sqltext

    obj_cat = _normalize_filter_value(str(object_category or "all"))
    cause_totals: dict[str, dict[int, int]] = {}
    errors: list[str] = []

    for meta in (metadata_items or []):
        table_name = str((meta or {}).get("table_name") or "")
        resolved = dict((meta or {}).get("resolved_columns") or {})
        cause_col = resolved.get("cause") or ""
        date_col = resolved.get("date") or ""
        if not table_name or not cause_col or not date_col:
            continue

        date_expr = _date_expression(date_col)
        cause_expr = _text_expression(cause_col)
        src = quote_identifier(table_name)

        conds = [
            f"{date_expr} IS NOT NULL",
            f"{cause_expr} IS NOT NULL",
            f"EXTRACT(MONTH FROM {date_expr}) = :month",
            f"EXTRACT(YEAR FROM {date_expr}) IN (:year_a, :year_b)",
        ]
        params: dict[str, Any] = {"month": int(target_month), "year_a": int(year_a), "year_b": int(year_b)}

        if obj_cat != "all":
            obj_col = resolved.get("object_category") or ""
            if obj_col:
                conds.append(f"{_text_expression(obj_col)} = :object_category")
                params["object_category"] = obj_cat

        sql = sqltext(
            f"SELECT {cause_expr} AS cause_value,"
            f" EXTRACT(YEAR FROM {date_expr})::int AS yr,"
            f" COUNT(*) AS cnt"
            f" FROM {src}"
            f" WHERE {' AND '.join(conds)}"
            f" GROUP BY {cause_expr}, EXTRACT(YEAR FROM {date_expr})::int"
        )

        try:
            with engine.connect() as conn:
                for row in conn.execute(sql, params).mappings():
                    cause_val = str(row.get("cause_value") or "").strip()
                    yr = int(row.get("yr") or 0)
                    cnt = int(row.get("cnt") or 0)
                    if cause_val and yr in (int(year_a), int(year_b)):
                        cause_totals.setdefault(cause_val, {}).setdefault(yr, 0)
                        cause_totals[cause_val][yr] += cnt
        except Exception as exc:
            errors.append(f"{table_name}: {exc}")
            continue

    ranked = sorted(
        [(cause, counts.get(int(year_a), 0), counts.get(int(year_b), 0)) for cause, counts in cause_totals.items()],
        key=lambda t: t[1] + t[2],
        reverse=True,
    )
    return [{"cause": t[0], "year_a_count": t[1], "year_b_count": t[2]} for t in ranked[:int(top_n)]], errors


def get_ml_causes_chart_data(
    table_name: str = "all",
    table_names: Sequence[str] | None = None,
    cause: str = "all",
    object_category: str = "all",
    current_user_date: str = "",
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
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
    selected_month = int(request_state.get("selected_compare_month") or 0)
    selected_year_a = int(request_state.get("selected_compare_year_a") or 0)
    selected_year_b = int(request_state.get("selected_compare_year_b") or 0)
    source_tables = list(request_state.get("source_tables") or [])

    empty = {"causes": [], "year_a": selected_year_a, "year_b": selected_year_b, "month": selected_month, "top_n": int(top_n)}
    if not source_tables:
        return empty

    filter_bundle = _load_ml_filter_bundle(
        source_tables=source_tables,
        cause=cause,
        object_category=object_category,
    )
    metadata_items = list(filter_bundle.get("metadata_items") or [])
    causes, errors = _load_cause_counts_by_year(
        metadata_items=metadata_items,
        target_month=selected_month,
        year_a=selected_year_a,
        year_b=selected_year_b,
        object_category=str(filter_bundle.get("selected_object_category") or "all"),
        top_n=int(top_n),
    )
    return {
        "causes": causes,
        "year_a": selected_year_a,
        "year_b": selected_year_b,
        "month": selected_month,
        "top_n": int(top_n),
        "debug_errors": errors,
        "debug_tables": [str((m or {}).get("table_name") or "") for m in metadata_items],
    }


def clear_ml_model_cache(caches: MLModelCaches | None = None) -> None:
    cache_set = caches or _DEFAULT_CACHES
    cache_set.ml_cache.clear()
    cache_set.compare_cache.clear()
    clear_ml_model_input_cache()
    clear_forecasting_sql_cache()

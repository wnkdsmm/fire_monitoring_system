from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from calendar import monthrange
from datetime import date, datetime
import re
from typing import Any, Sequence

from app.perf import current_perf_trace, profiled
from app.services.forecasting.data import (
    _build_daily_history_sql,
    _build_forecasting_table_options,
    _build_option_catalog_sql,
    _collect_forecasting_metadata,
    _count_forecasting_records_sql,
    _resolve_forecasting_selection,
    _selected_source_table_notes,
    _selected_source_tables,
    _temperature_quality_from_daily_history,
    clear_forecasting_sql_cache,
)
from app.services.forecasting.utils import (
    _format_datetime,
    _parse_optional_iso_date,
    _resolve_option_value,
)
from app.services.forecasting.selection import _canonicalize_source_tables
from app.services.shared.request_state import (
    build_ml_cache_key as _build_ml_cache_key,
    build_ml_compare_cache_key as _build_ml_compare_cache_key,
    build_ml_request_state as _build_ml_request_state_impl,
)
from config.db import engine

from .ml_model_config_types import FIXED_FORECAST_DAYS, MIN_DAILY_HISTORY, ML_CACHE_SCHEMA_VERSION, MlProgressCallback, _emit_progress
from .caches import MLModelCaches, create_default_caches
from .training.data_access import (
    clear_ml_model_input_cache,
    load_ml_aggregation_inputs as _load_ml_aggregation_inputs_impl,
    load_ml_filter_bundle as _load_ml_filter_bundle_impl,
)
from .training.types import MlAggregationInputs, MlContext, MlFilterBundle, MlPayload, MlRequestState
from .training.appg import compute_appg_period_series
from .training.compare_series import build_compare_series
from .payloads import _build_ml_payload, _compact_ui_notes, _empty_ml_model_data
from .training.training import _train_ml_model, clear_training_artifact_cache

_DEFAULT_CACHES = create_default_caches()
_MIN_SELECTABLE_YEAR = 1990
_MAX_SELECTABLE_YEAR = 2100
_DEFAULT_COMPARE_YEAR_A = 2024
_DEFAULT_COMPARE_YEAR_B = 2025
_YEAR_TOKEN_RE = re.compile(r"(19\d{2}|20\d{2}|2100)")


def _build_ml_context(initial_data: MlPayload) -> MlContext:
    return {
        'generated_at': _format_datetime(datetime.now()),
        'initial_data': initial_data,
        'plotly_js': '',
        'has_data': bool(initial_data['filters']['available_tables']),
    }


def _selected_table_label(table_names: Sequence[str], *, selected_table: str) -> str:
    concrete = [str(item or "").strip() for item in table_names if str(item or "").strip()]
    if selected_table == 'all':
        return 'Все таблицы'
    if not concrete:
        return 'Нет таблицы'
    if len(concrete) == 1:
        return concrete[0]
    preview = ', '.join(concrete[:2])
    suffix = '' if len(concrete) <= 2 else f' +{len(concrete) - 2}'
    return f'{preview}{suffix}'


def _build_ml_deferred_shell_data(
    request_state: MlRequestState,
    *,
    cause: str,
    object_category: str,
) -> MlPayload:
    initial_data = _empty_ml_model_data(
        request_state['table_options'],
        request_state['selected_table'],
        request_state['selected_tables'],
        request_state['selected_table_label'],
        request_state['days_ahead'],
        "",
        request_state['selected_history_window'],
    )
    initial_data['bootstrap_mode'] = 'deferred'
    initial_data['charts']['importance']['empty_message'] = (
        'Собираем драйверы прогноза: блок заполнится после фонового расчёта.'
    )
    initial_data['notes'].extend(request_state['source_table_notes'])
    initial_data['notes'] = _compact_ui_notes(initial_data['notes'])
    initial_data['filters']['cause'] = cause or 'all'
    initial_data['filters']['object_category'] = object_category or 'all'
    return initial_data


def _build_no_source_ml_payload(
    base_payload: MlPayload,
    *,
    source_table_notes: list[str],
) -> MlPayload:
    base_payload['notes'].extend(source_table_notes)
    base_payload['notes'].append('\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u0442\u0430\u0431\u043b\u0438\u0446 \u0434\u043b\u044f ML-\u043c\u043e\u0434\u0435\u043b\u0438.')
    base_payload['notes'] = _compact_ui_notes(base_payload['notes'])
    return base_payload


def _load_ml_filter_bundle(
    *,
    source_tables: list[str],
    selected_history_window: str,
    cause: str,
    object_category: str,
) -> MlFilterBundle:
    return _load_ml_filter_bundle_impl(
        source_tables=source_tables,
        selected_history_window=selected_history_window,
        cause=cause,
        object_category=object_category,
        collect_forecasting_metadata=_collect_forecasting_metadata,
        build_option_catalog_sql=_build_option_catalog_sql,
        resolve_option_value=_resolve_option_value,
    )


def _load_ml_aggregation_inputs(
    *,
    source_tables: list[str],
    selected_history_window: str,
    filter_bundle: MlFilterBundle,
) -> MlAggregationInputs:
    return _load_ml_aggregation_inputs_impl(
        source_tables=source_tables,
        selected_history_window=selected_history_window,
        filter_bundle=filter_bundle,
        build_daily_history_sql=_build_daily_history_sql,
        count_forecasting_records_sql=_count_forecasting_records_sql,
    )


def get_ml_model_shell_context(
    table_name: str = 'all',
    table_names: Sequence[str] | None = None,
    cause: str = 'all',
    object_category: str = 'all',
    current_user_date: str = '',
    prefer_cached: bool = False,
    caches: MLModelCaches | None = None,
) -> MlContext:
    cache_set = caches or _DEFAULT_CACHES
    request_state = _build_ml_request_state(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        current_user_date=current_user_date,
    )
    cached = _cache_get(request_state['cache_key'], cache_set) if prefer_cached else None
    if cached is not None:
        return _build_ml_context(cached)

    initial_data = _build_ml_deferred_shell_data(
        request_state,
        cause=cause,
        object_category=object_category,
    )
    return _build_ml_context(initial_data)

@profiled('ml_model', engine=engine)


def get_ml_model_data(
    table_name: str = 'all',
    table_names: Sequence[str] | None = None,
    cause: str = 'all',
    object_category: str = 'all',
    current_user_date: str = '',
    year: int | None = None,
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    _prebuilt_cache_key: tuple[Any, ...] | None = None,
    progress_callback: MlProgressCallback | None = None,
    caches: MLModelCaches | None = None,
) -> MlPayload:
    cache_set = caches or _DEFAULT_CACHES
    perf = current_perf_trace()
    request_state = _build_ml_request_state(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        current_user_date=current_user_date,
        year=year,
        month=month,
        year_a=year_a,
        year_b=year_b,
    )
    table_options = request_state['table_options']
    selected_table = request_state['selected_table']
    selected_tables = request_state['selected_tables']
    selected_table_label = request_state['selected_table_label']
    source_tables = request_state['source_tables']
    source_table_notes = request_state['source_table_notes']
    days_ahead = request_state['days_ahead']
    selected_history_window = request_state['selected_history_window']
    scenario_temperature = request_state['scenario_temperature']
    cache_key = _prebuilt_cache_key if _prebuilt_cache_key is not None else request_state['cache_key']
    if perf is not None:
        perf.update(
            requested_table=table_name,
            requested_cause=cause,
            requested_object_category=object_category,
            selected_table=selected_table,
            source_tables=len(source_tables),
            forecast_horizon_days=days_ahead,
            history_window=selected_history_window,
        )
    cached = _cache_get(cache_key, cache_set)
    if cached is not None:
        period_daily_history: list[dict[str, Any]] = []
        if (request_state.get('selected_year') is not None or request_state.get('selected_compare_month') is not None) and source_tables:
            try:
                filter_bundle = _load_ml_filter_bundle(
                    source_tables=source_tables,
                    selected_history_window=selected_history_window,
                    cause=cause,
                    object_category=object_category,
                )
                aggregation_inputs = _load_ml_aggregation_inputs(
                    source_tables=source_tables,
                    selected_history_window=selected_history_window,
                    filter_bundle=filter_bundle,
                )
                period_daily_history = aggregation_inputs.get('daily_history', [])
            except Exception:
                period_daily_history = []
        filtered_cached = _apply_period_filter(
            deepcopy(cached),
            daily_history=period_daily_history,
            year=request_state.get('selected_year'),
            month=request_state.get('selected_month'),
        )
        filtered_cached = _attach_compare_series(
            filtered_cached,
            daily_history=period_daily_history,
            scenario_temperature=request_state.get('scenario_temperature'),
            current_user_day=request_state.get('current_user_day'),
            compare_month=request_state.get('selected_compare_month'),
            compare_year_a=request_state.get('selected_compare_year_a'),
            compare_year_b=request_state.get('selected_compare_year_b'),
            caches=cache_set,
        )
        if perf is not None:
            perf.update(cache_hit=True, payload_has_data=bool(filtered_cached.get('has_data')))
        _emit_progress(progress_callback, 'ml_model.completed', '\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 ML-\u0430\u043d\u0430\u043b\u0438\u0437\u0430 \u0432\u0437\u044f\u0442 \u0438\u0437 \u043a\u044d\u0448\u0430.')
        return filtered_cached

    if perf is not None:
        perf.update(cache_hit=False)
    base = _empty_ml_model_data(
        table_options,
        selected_table,
        selected_tables,
        selected_table_label,
        days_ahead,
        "",
        selected_history_window,
    )
    if not source_tables:
        base = _build_no_source_ml_payload(base, source_table_notes=source_table_notes)
        if perf is not None:
            perf.update(payload_has_data=False, payload_notes=len(base['notes']))
        return _cache_store(cache_key, base, cache_set)

    _emit_progress(progress_callback, 'ml_model.running', '\u0421\u043e\u0431\u0438\u0440\u0430\u0435\u043c SQL-\u0430\u0433\u0440\u0435\u0433\u0430\u0442\u044b \u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0444\u0438\u043b\u044c\u0442\u0440\u044b \u0434\u043b\u044f ML-\u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0430.')
    filter_prep_context = perf.span('filter_prep') if perf is not None else nullcontext()
    with filter_prep_context:
        filter_bundle = _load_ml_filter_bundle(
            source_tables=source_tables,
            selected_history_window=selected_history_window,
            cause=cause,
            object_category=object_category,
        )
        metadata_items = filter_bundle['metadata_items']
        preload_notes = filter_bundle['preload_notes']
        option_catalog = filter_bundle['option_catalog']
        selected_cause = filter_bundle['selected_cause']
        selected_object_category = filter_bundle['selected_object_category']
        if perf is not None:
            perf.update(
                metadata_tables=len(metadata_items),
                available_causes=len(option_catalog['causes']),
                available_object_categories=len(option_catalog['object_categories']),
            )

    aggregation_context = perf.span('aggregation') if perf is not None else nullcontext()
    with aggregation_context:
        aggregation_inputs = _load_ml_aggregation_inputs(
            source_tables=source_tables,
            selected_history_window=selected_history_window,
            filter_bundle=filter_bundle,
        )
        daily_history = aggregation_inputs['daily_history']
        filtered_records_count = aggregation_inputs['filtered_records_count']
        if perf is not None:
            perf.update(input_rows=filtered_records_count, history_days=len(daily_history))
    _emit_progress(
        progress_callback,
        'ml_model.running',
        f"\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d \u0434\u043d\u0435\u0432\u043d\u043e\u0439 \u0440\u044f\u0434: {len(daily_history)} \u0434\u043d\u0435\u0439 \u0438\u0441\u0442\u043e\u0440\u0438\u0438, {filtered_records_count} \u043f\u043e\u0436\u0430\u0440\u043e\u0432 \u043f\u043e\u0441\u043b\u0435 \u0444\u0438\u043b\u044c\u0442\u0440\u043e\u0432.",
    )
    model_training_context = perf.span('model_training') if perf is not None else nullcontext()
    with model_training_context:
        ml_result = _train_ml_model(
            daily_history,
            days_ahead,
            scenario_temperature,
            current_user_date=request_state.get('current_user_day'),
            progress_callback=progress_callback,
            caches=cache_set,
        )
        temperature_quality = _temperature_quality_from_daily_history(daily_history)
    _emit_progress(progress_callback, 'ml_model.running', '\u0424\u043e\u0440\u043c\u0438\u0440\u0443\u0435\u043c \u0438\u0442\u043e\u0433\u043e\u0432\u044b\u0435 \u043c\u0435\u0442\u0440\u0438\u043a\u0438, \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0438 \u0442\u0430\u0431\u043b\u0438\u0446\u044b ML-\u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0430.')
    payload_render_context = perf.span('payload_render') if perf is not None else nullcontext()
    with payload_render_context:
        payload = _build_ml_payload(
            table_options=table_options,
            selected_table=selected_table,
            selected_tables=selected_tables,
            selected_table_label=selected_table_label,
            selected_cause=selected_cause,
            selected_object_category=selected_object_category,
            temperature="",
            days_ahead=days_ahead,
            selected_history_window=selected_history_window,
            option_catalog=option_catalog,
            filtered_records_count=filtered_records_count,
            metadata_items=metadata_items,
            preload_notes=preload_notes,
            source_table_notes=source_table_notes,
            source_tables=source_tables,
            daily_history=daily_history,
            ml_result=ml_result,
            scenario_temperature=scenario_temperature,
            temperature_quality=temperature_quality,
        )
        payload = _apply_period_filter(
            payload,
            daily_history=daily_history,
            year=request_state.get('selected_year'),
            month=request_state.get('selected_month'),
        )
        payload = _attach_compare_series(
            payload,
            daily_history=daily_history,
            scenario_temperature=scenario_temperature,
            current_user_day=request_state.get('current_user_day'),
            compare_month=request_state.get('selected_compare_month'),
            compare_year_a=request_state.get('selected_compare_year_a'),
            compare_year_b=request_state.get('selected_compare_year_b'),
            caches=cache_set,
        )
        if perf is not None:
            perf.update(
                payload_has_data=bool(payload['has_data']),
                payload_notes=len(payload['notes']),
                feature_importance_rows=len(payload['feature_importance']),
                forecast_rows=len(payload['forecast_rows']),
            )
    _emit_progress(progress_callback, 'ml_model.completed', 'ML-\u0430\u043d\u0430\u043b\u0438\u0437 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d, \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u0433\u043e\u0442\u043e\u0432 \u043a \u0432\u044b\u0434\u0430\u0447\u0435.')
    return _cache_store(cache_key, payload, cache_set)


def _cache_get(
    cache_key: tuple[Any, ...],
    caches: MLModelCaches | None = None,
) -> MlPayload | None:
    cache_set = caches or _DEFAULT_CACHES
    return cache_set.ml_cache.get(cache_key)


def _cache_store(
    cache_key: tuple[Any, ...],
    payload: MlPayload,
    caches: MLModelCaches | None = None,
) -> MlPayload:
    cache_set = caches or _DEFAULT_CACHES
    cache_set.ml_cache.set(cache_key, payload)
    return payload


def _build_ml_request_state(
    table_name: str = 'all',
    table_names: Sequence[str] | None = None,
    cause: str = 'all',
    object_category: str = 'all',
    current_user_date: str = '',
    year: int | None = None,
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
) -> MlRequestState:
    period_month = month if year is not None else None
    selected_year, selected_month = _normalize_period_selection(year=year, month=period_month)
    selected_compare_month, selected_compare_year_a, selected_compare_year_b = _normalize_compare_selection(
        month=month,
        year_a=year_a,
        year_b=year_b,
        current_user_date=current_user_date,
    )
    parsed_current_user_date = _parse_optional_iso_date(current_user_date)
    normalized_current_user_date = (
        parsed_current_user_date.isoformat() if parsed_current_user_date is not None else ''
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
    normalized_requested = [str(item or "").strip() for item in (table_names or []) if str(item or "").strip()]
    if normalized_requested and 'all' not in normalized_requested:
        available = {
            str(item.get('value') or '').strip()
            for item in state['table_options']
            if str(item.get('value') or '').strip() and str(item.get('value') or '').strip() != 'all'
        }
        raw_selected = [name for name in normalized_requested if name in available]
        if raw_selected:
            normalized_sources, dedupe_notes = _canonicalize_source_tables(raw_selected)
            state['source_tables'] = normalized_sources
            state['source_table_notes'] = dedupe_notes
            state['selected_table'] = normalized_sources[0] if len(normalized_sources) == 1 else 'multi'
    state['selected_tables'] = list(state['source_tables'])
    state['selected_table_label'] = _selected_table_label(
        state['selected_tables'],
        selected_table=str(state['selected_table'] or ''),
    )
    state['cache_key'] = _build_ml_cache_key(
        cache_schema_version=ML_CACHE_SCHEMA_VERSION,
        selected_table=state['selected_table'],
        source_tables=state['source_tables'],
        cause=cause,
        object_category=object_category,
        temperature="",
        days_ahead=state['days_ahead'],
        history_window=state['selected_history_window'],
        current_user_date=normalized_current_user_date,
        compare_month=selected_compare_month,
        compare_year_a=selected_compare_year_a,
        compare_year_b=selected_compare_year_b,
        period_year=selected_year,
        period_month=selected_month,
    )
    state['current_user_date'] = normalized_current_user_date
    state['current_user_day'] = parsed_current_user_date
    state['selected_year'] = selected_year
    state['selected_month'] = selected_month
    state['selected_compare_month'] = selected_compare_month
    state['selected_compare_year_a'] = selected_compare_year_a
    state['selected_compare_year_b'] = selected_compare_year_b
    return state


def _normalize_period_selection(*, year: int | None, month: int | None) -> tuple[int | None, int | None]:
    if year is None and month is None:
        return None, None
    if year is None:
        raise ValueError('Параметр year обязателен, если указан month.')
    normalized_year = int(year)
    if normalized_year < _MIN_SELECTABLE_YEAR or normalized_year > _MAX_SELECTABLE_YEAR:
        raise ValueError(f'Параметр year должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.')
    normalized_month: int | None = None
    if month is not None:
        normalized_month = int(month)
        if normalized_month < 1 or normalized_month > 12:
            raise ValueError('Параметр month должен быть в диапазоне 1..12.')
    return normalized_year, normalized_month


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
        raise ValueError('Параметр month должен быть в диапазоне 1..12.')
    normalized_year_a = int(year_a) if year_a is not None else _DEFAULT_COMPARE_YEAR_A
    normalized_year_b = int(year_b) if year_b is not None else _DEFAULT_COMPARE_YEAR_B
    if normalized_year_a < _MIN_SELECTABLE_YEAR or normalized_year_a > _MAX_SELECTABLE_YEAR:
        raise ValueError(f'Параметр year_a должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.')
    if normalized_year_b < _MIN_SELECTABLE_YEAR or normalized_year_b > _MAX_SELECTABLE_YEAR:
        raise ValueError(f'Параметр year_b должен быть в диапазоне {_MIN_SELECTABLE_YEAR}..{_MAX_SELECTABLE_YEAR}.')
    return normalized_month, normalized_year_a, normalized_year_b


def _extract_available_years_from_table_options(table_options: list[dict[str, str]]) -> list[dict[str, str]]:
    years: set[int] = set()
    for option in table_options:
        value = str((option or {}).get('value') or '').strip()
        if not value or value == 'all':
            continue
        for token in _YEAR_TOKEN_RE.findall(value):
            year = int(token)
            if 1900 <= year <= 2100:
                years.add(year)
    return [{'value': str(year), 'label': str(year)} for year in sorted(years, reverse=True)]


def _date_matches_period(date_text: str, *, year: int | None, month: int | None) -> bool:
    parsed = _parse_optional_iso_date(str(date_text or ''))
    if parsed is None:
        return False
    if year is not None and parsed.year != year:
        return False
    if month is not None and parsed.month != month:
        return False
    return True


def _apply_period_filter(
    payload: MlPayload,
    *,
    daily_history: list[dict[str, Any]],
    year: int | None,
    month: int | None,
) -> MlPayload:
    if year is None and month is None:
        return payload
    forecast_rows = [row for row in payload.get('forecast_rows', []) if _date_matches_period(row.get('date', ''), year=year, month=month)]
    appg_series = [row for row in payload.get('appg_series', []) if _date_matches_period(row.get('current_date', ''), year=year, month=month)]
    appg_period_series = [row for row in payload.get('appg_period_series', []) if _date_matches_period(row.get('current_date', ''), year=year, month=month)]
    if year is not None and daily_history:
        appg_period_series = compute_appg_period_series(
            daily_history,
            year=year,
            month=month,
            history_date_key='date',
            history_value_key='count',
        )
    payload['forecast_rows'] = forecast_rows
    payload['appg_series'] = appg_series
    payload['appg_period_series'] = appg_period_series
    filters = payload.get('filters') or {}
    filters['year'] = year
    filters['month'] = month
    payload['filters'] = filters
    return payload


def _attach_compare_series(
    payload: MlPayload,
    *,
    daily_history: list[dict[str, Any]],
    scenario_temperature: float | None,
    current_user_day: date | None,
    compare_month: int | None,
    compare_year_a: int | None,
    compare_year_b: int | None,
    caches: MLModelCaches,
) -> MlPayload:
    del current_user_day
    if compare_month is None or compare_year_a is None or compare_year_b is None:
        payload['compare_series'] = {}
        return payload

    payload['compare_series'] = _build_compare_series_payload(
        month=int(compare_month),
        year_a=int(compare_year_a),
        year_b=int(compare_year_b),
        daily_history=daily_history,
        scenario_temperature=scenario_temperature,
        caches=caches,
    )
    filters = payload.get('filters') or {}
    filters['year_a'] = int(compare_year_a)
    filters['year_b'] = int(compare_year_b)
    filters['compare_month'] = int(compare_month)
    payload['filters'] = filters
    return payload


def _build_compare_series_payload(
    *,
    month: int,
    year_a: int,
    year_b: int,
    daily_history: list[dict[str, Any]],
    scenario_temperature: float | None,
    caches: MLModelCaches,
) -> dict[str, Any]:
    ml_rows_cache: dict[tuple[int, int], dict[int, float | None]] = {}
    history_has_data = bool(daily_history)

    def _predict_month_with_trained_ml(target_year: int, target_month: int) -> dict[int, float | None]:
        month_days = int(monthrange(int(target_year), int(target_month))[1])
        history_before_month: list[dict[str, Any]] = []
        for row in daily_history:
            row_date = _parse_optional_iso_date(str(row.get('date') or ''))
            if row_date is None:
                continue
            # Compare-series ML mode: train only on the same calendar month across prior years.
            if row_date.month != int(target_month) or row_date.year >= int(target_year):
                continue
            raw_count = row.get('count')
            if raw_count is None:
                continue
            try:
                count_value = float(raw_count)
            except (TypeError, ValueError):
                continue
            history_before_month.append(
                {
                    'date': row_date.isoformat(),
                    'count': count_value,
                    'avg_temperature': row.get('avg_temperature'),
                }
            )

        def _month_history_profile() -> dict[int, float | None]:
            if not history_before_month:
                return {}
            by_day: dict[int, list[float]] = {}
            all_values: list[float] = []
            for item in history_before_month:
                item_date = _parse_optional_iso_date(str(item.get('date') or ''))
                if item_date is None:
                    continue
                raw_value = item.get('count')
                try:
                    numeric_value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                by_day.setdefault(int(item_date.day), []).append(numeric_value)
                all_values.append(numeric_value)
            if not all_values:
                return {}
            overall_mean = sum(all_values) / float(len(all_values))
            result: dict[int, float | None] = {}
            for day in range(1, month_days + 1):
                day_values = by_day.get(day) or []
                if day_values:
                    result[day] = max(0.0, sum(day_values) / float(len(day_values)))
                else:
                    result[day] = max(0.0, overall_mean)
            return result

        # Compare-series mode should follow month-across-years logic directly:
        # use the selected month from prior years as the profile for target year.
        return _month_history_profile()

    facts_by_year_day: dict[tuple[int, int], set[int]] = {}
    for row in daily_history:
        row_date = _parse_optional_iso_date(str(row.get('date') or ''))
        if row_date is None:
            continue
        if row_date.month != int(month):
            continue
        raw_value = row.get('count')
        if raw_value is None:
            continue
        try:
            float(raw_value)
        except (TypeError, ValueError):
            continue
        key = (int(row_date.year), int(row_date.month))
        if key not in facts_by_year_day:
            facts_by_year_day[key] = set()
        facts_by_year_day[key].add(int(row_date.day))

    month_days_a = int(monthrange(int(year_a), int(month))[1])
    month_days_b = int(monthrange(int(year_b), int(month))[1])
    required_days_by_year: dict[int, set[int]] = {
        int(year_a): {
            day for day in range(1, month_days_a + 1)
            if day not in facts_by_year_day.get((int(year_a), int(month)), set())
        },
        int(year_b): {
            day for day in range(1, month_days_b + 1)
            if day not in facts_by_year_day.get((int(year_b), int(month)), set())
        },
    }
    ml_invoked_by_year: dict[int, bool] = {
        int(year_a): False,
        int(year_b): False,
    }

    def _ml_month_provider(year_value: int, month_value: int) -> dict[int, float | None]:
        cache_key = (int(year_value), int(month_value))
        if cache_key in ml_rows_cache:
            return ml_rows_cache[cache_key]
        needed_days = required_days_by_year.get(int(year_value), set())
        if not needed_days:
            ml_rows_cache[cache_key] = {}
            return ml_rows_cache[cache_key]
        if not history_has_data:
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
        history_date_key='date',
        history_value_key='count',
    )
    a_summary = compare_payload.get('a_summary') or {}
    b_summary = compare_payload.get('b_summary') or {}
    def _resolve_mode(summary: dict[str, Any]) -> str:
        fact_days = int(summary.get('fact_days') or 0)
        ml_days = int(summary.get('ml_days') or 0)
        if fact_days > 0 and ml_days == 0:
            return 'fact'
        if fact_days == 0 and ml_days > 0:
            return 'ml'
        if fact_days > 0 and ml_days > 0:
            return 'mixed'
        return 'empty'

    a_mode = _resolve_mode(a_summary)
    b_mode = _resolve_mode(b_summary)
    if a_mode == 'fact' and b_mode == 'fact':
        overall_mode = 'fact_fact'
    elif a_mode == 'ml' and b_mode == 'ml':
        overall_mode = 'ml_ml'
    elif a_mode == 'empty' and b_mode == 'empty':
        overall_mode = 'empty'
    else:
        overall_mode = 'mixed'

    compare_payload['ml_usage'] = {
        'year_a': {
            'year': int(year_a),
            'fact_points': int(a_summary.get('fact_days') or 0),
            'ml_points': int(a_summary.get('ml_days') or 0),
            'ml_invoked': bool(ml_invoked_by_year.get(int(year_a), False)),
        },
        'year_b': {
            'year': int(year_b),
            'fact_points': int(b_summary.get('fact_days') or 0),
            'ml_points': int(b_summary.get('ml_days') or 0),
            'ml_invoked': bool(ml_invoked_by_year.get(int(year_b), False)),
        },
    }
    compare_payload['modes'] = {
        'year_a': a_mode,
        'year_b': b_mode,
        'overall': overall_mode,
    }
    compare_payload['history_has_data'] = history_has_data
    return compare_payload


def get_ml_compare_series_data(
    table_name: str = 'all',
    table_names: Sequence[str] | None = None,
    cause: str = 'all',
    object_category: str = 'all',
    current_user_date: str = '',
    month: int | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    caches: MLModelCaches | None = None,
) -> dict[str, Any]:
    def _is_numeric_point(value: Any) -> bool:
        if value is None:
            return False
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False
        return not (numeric != numeric)

    def _normalize_compare_payload(payload: dict[str, Any]) -> dict[str, Any]:
        compare_series = payload.get('compare_series')
        if not isinstance(compare_series, dict):
            compare_series = {}
            payload['compare_series'] = compare_series
        rows = compare_series.get('rows')
        if not isinstance(rows, list):
            rows = []
            compare_series['rows'] = rows
        has_points = any(
            isinstance(row, dict) and (
                _is_numeric_point(row.get('a_value'))
                or _is_numeric_point(row.get('b_value'))
            )
            for row in rows
        )
        compare_series['history_has_data'] = bool(compare_series.get('history_has_data') or has_points)
        return payload

    cache_set = caches or _DEFAULT_CACHES
    request_state = _build_ml_request_state(
        table_name=table_name,
        table_names=table_names,
        cause=cause,
        object_category=object_category,
        current_user_date=current_user_date,
        year=None,
        month=month,
        year_a=year_a,
        year_b=year_b,
    )
    selected_compare_month = int(request_state.get('selected_compare_month') or 0)
    selected_compare_year_a = int(request_state.get('selected_compare_year_a') or 0)
    selected_compare_year_b = int(request_state.get('selected_compare_year_b') or 0)
    available_years = _extract_available_years_from_table_options(list(request_state.get('table_options') or []))
    compare_cache_key = _build_ml_compare_cache_key(
        cache_schema_version=ML_CACHE_SCHEMA_VERSION,
        selected_tables=tuple(request_state.get('source_tables') or []),
        cause=str(cause or 'all'),
        object_category=str(object_category or 'all'),
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_b,
        current_user_date=str(request_state.get('current_user_date') or ''),
    )
    cached = cache_set.compare_cache.get(compare_cache_key)
    source_tables = list(request_state.get('source_tables') or [])
    scenario_temperature = request_state.get('scenario_temperature')
    if cached is not None:
        cached_compare_series = (cached or {}).get('compare_series') if isinstance(cached, dict) else None
        if isinstance(cached_compare_series, dict) and ('history_has_data' in cached_compare_series):
            return _normalize_compare_payload(cached)

    if not source_tables:
        result_payload = {
            'compare_series': {
                'month': selected_compare_month,
                'year_a': selected_compare_year_a,
                'year_b': selected_compare_year_b,
                'rows': [],
                'a_summary': {'fact_days': 0, 'ml_days': 0},
                'b_summary': {'fact_days': 0, 'ml_days': 0},
                'history_has_data': False,
            },
            'filters': {
                'table_name': request_state.get('selected_table', 'all'),
                'table_names': list(request_state.get('selected_tables') or []),
                'available_tables': list(request_state.get('table_options') or []),
                'available_years': available_years,
                'cause': cause or 'all',
                'object_category': object_category or 'all',
                'compare_month': selected_compare_month,
                'year_a': selected_compare_year_a,
                'year_b': selected_compare_year_b,
            },
        }
        cache_set.compare_cache.set(compare_cache_key, result_payload)
        return _normalize_compare_payload(result_payload)

    filter_bundle = _load_ml_filter_bundle(
        source_tables=source_tables,
        selected_history_window=str(request_state.get('selected_history_window') or 'all'),
        cause=cause,
        object_category=object_category,
    )
    aggregation_inputs = _load_ml_aggregation_inputs(
        source_tables=source_tables,
        selected_history_window=str(request_state.get('selected_history_window') or 'all'),
        filter_bundle=filter_bundle,
    )
    daily_history = aggregation_inputs.get('daily_history', [])
    compare_series = _build_compare_series_payload(
        month=selected_compare_month,
        year_a=selected_compare_year_a,
        year_b=selected_compare_year_b,
        daily_history=daily_history,
        scenario_temperature=scenario_temperature,
        caches=cache_set,
    )
    result_payload = {
        'compare_series': compare_series,
        'filters': {
            'table_name': request_state.get('selected_table', 'all'),
            'table_names': list(request_state.get('selected_tables') or []),
            'available_tables': list(request_state.get('table_options') or []),
            'available_years': available_years,
            'cause': cause or 'all',
            'object_category': object_category or 'all',
            'compare_month': selected_compare_month,
            'year_a': selected_compare_year_a,
            'year_b': selected_compare_year_b,
        },
    }
    result_payload = _normalize_compare_payload(result_payload)
    cache_set.compare_cache.set(compare_cache_key, result_payload)
    return result_payload


def clear_ml_model_cache(caches: MLModelCaches | None = None) -> None:
    cache_set = caches or _DEFAULT_CACHES
    cache_set.ml_cache.clear()
    cache_set.compare_cache.clear()
    clear_ml_model_input_cache()
    clear_training_artifact_cache(cache_set)
    clear_forecasting_sql_cache()

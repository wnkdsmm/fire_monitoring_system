from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
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
    _format_float_for_input,
    _parse_float,
    _parse_forecast_days,
    _parse_history_window,
    _parse_optional_iso_date,
    _resolve_option_value,
)
from app.services.forecasting.selection import _canonicalize_source_tables
from app.services.shared.request_state import (
    build_ml_cache_key as _build_ml_cache_key,
    build_ml_request_state as _build_ml_request_state_impl,
)
from config.db import engine

from .ml_model_config_types import FIXED_FORECAST_DAYS, ML_CACHE_SCHEMA_VERSION, MlProgressCallback, _emit_progress
from .caches import MLModelCaches, create_default_caches
from .training.data_access import (
    clear_ml_model_input_cache,
    load_ml_aggregation_inputs as _load_ml_aggregation_inputs_impl,
    load_ml_filter_bundle as _load_ml_filter_bundle_impl,
)
from .training.types import MlAggregationInputs, MlContext, MlFilterBundle, MlPayload, MlRequestState
from .payloads import _build_ml_payload, _compact_ui_notes, _empty_ml_model_data
from .training.training import _train_ml_model, clear_training_artifact_cache

_DEFAULT_CACHES = create_default_caches()


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
    temperature: str = '',
    forecast_days: str = '7',
    history_window: str = 'all',
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
        temperature="",
        forecast_days=str(FIXED_FORECAST_DAYS),
        history_window="all",
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
    temperature: str = '',
    forecast_days: str = '7',
    history_window: str = 'all',
    current_user_date: str = '',
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
        temperature="",
        forecast_days=str(FIXED_FORECAST_DAYS),
        history_window="all",
        current_user_date=current_user_date,
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
    cache_key = request_state['cache_key']
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
        if perf is not None:
            perf.update(cache_hit=True, payload_has_data=bool(cached.get('has_data')))
        _emit_progress(progress_callback, 'ml_model.completed', '\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 ML-\u0430\u043d\u0430\u043b\u0438\u0437\u0430 \u0432\u0437\u044f\u0442 \u0438\u0437 \u043a\u044d\u0448\u0430.')
        return cached

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
    temperature: str = '',
    forecast_days: str = '7',
    history_window: str = 'all',
    current_user_date: str = '',
) -> MlRequestState:
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
        forecast_days_parser=_parse_forecast_days,
        history_window_parser=_parse_history_window,
        temperature_parser=_parse_float,
        temperature_formatter=_format_float_for_input,
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
        temperature=_format_float_for_input(state['scenario_temperature']) if state['scenario_temperature'] is not None else "",
        days_ahead=state['days_ahead'],
        history_window=state['selected_history_window'],
        current_user_date=normalized_current_user_date,
    )
    state['current_user_date'] = normalized_current_user_date
    state['current_user_day'] = parsed_current_user_date
    return state


def clear_ml_model_cache(caches: MLModelCaches | None = None) -> None:
    cache_set = caches or _DEFAULT_CACHES
    cache_set.ml_cache.clear()
    clear_ml_model_input_cache()
    clear_training_artifact_cache(cache_set)
    clear_forecasting_sql_cache()

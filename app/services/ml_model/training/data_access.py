from __future__ import annotations

from typing import Any, Callable, Sequence

from app.cache import build_immutable_payload_ttl_cache, callable_cache_scope
from app.services.forecasting.selection import _canonicalize_source_tables, _normalize_filter_value
from app.services.forecasting.types import ForecastingDailyHistoryRow, ForecastingOptionCatalog, ForecastingTableMetadata
from app.services.shared.data_base import DataLoader

_ML_FILTER_BUNDLE_CACHE = build_immutable_payload_ttl_cache(ttl_seconds=None)
_ML_AGGREGATION_INPUT_CACHE = build_immutable_payload_ttl_cache(ttl_seconds=None)


def clear_ml_model_input_cache() -> None:
    _ML_FILTER_BUNDLE_CACHE.clear()
    _ML_AGGREGATION_INPUT_CACHE.clear()


def load_ml_filter_bundle(
    *,
    source_tables: Sequence[str],
    selected_history_window: str,
    cause: str,
    object_category: str,
    collect_forecasting_metadata: Callable[[Sequence[str]], tuple[list[ForecastingTableMetadata], list[str]]],
    build_option_catalog_sql: Callable[..., ForecastingOptionCatalog],
    resolve_option_value: Callable[[Sequence[dict[str, str]], str], str],
) -> dict[str, Any]:
    bundle = _load_ml_filter_bundle(
        source_tables=source_tables,
        selected_history_window=selected_history_window,
        collect_forecasting_metadata=collect_forecasting_metadata,
        build_option_catalog_sql=build_option_catalog_sql,
    )
    option_catalog = bundle["option_catalog"]
    return {
        **bundle,
        "selected_cause": resolve_option_value(option_catalog["causes"], cause),
        "selected_object_category": resolve_option_value(option_catalog["object_categories"], object_category),
    }


def load_ml_aggregation_inputs(
    *,
    source_tables: Sequence[str],
    selected_history_window: str,
    filter_bundle: dict[str, Any],
    build_daily_history_sql: Callable[..., list[ForecastingDailyHistoryRow]],
    count_forecasting_records_sql: Callable[..., int],
) -> dict[str, Any]:
    cache_key = _ml_aggregation_input_cache_key(
        source_tables,
        selected_history_window,
        str(filter_bundle.get("selected_cause") or "all"),
        str(filter_bundle.get("selected_object_category") or "all"),
        build_daily_history_sql=build_daily_history_sql,
        count_forecasting_records_sql=count_forecasting_records_sql,
    )
    cached_inputs = _ML_AGGREGATION_INPUT_CACHE.get(cache_key)
    if cached_inputs is not None:
        return cached_inputs

    metadata_items = filter_bundle.get("metadata_items") or []
    payload = {
        **filter_bundle,
        "daily_history": build_daily_history_sql(
            source_tables,
            history_window=selected_history_window,
            cause=str(filter_bundle.get("selected_cause") or "all"),
            object_category=str(filter_bundle.get("selected_object_category") or "all"),
            metadata_items=metadata_items,
        ),
    }
    payload["filtered_records_count"] = count_forecasting_records_sql(
        source_tables,
        history_window=selected_history_window,
        cause=str(payload.get("selected_cause") or "all"),
        object_category=str(payload.get("selected_object_category") or "all"),
        metadata_items=metadata_items,
    )
    return _ML_AGGREGATION_INPUT_CACHE.set(cache_key, payload)


def _load_ml_filter_bundle(
    *,
    source_tables: Sequence[str],
    selected_history_window: str,
    collect_forecasting_metadata: Callable[[Sequence[str]], tuple[list[ForecastingTableMetadata], list[str]]],
    build_option_catalog_sql: Callable[..., ForecastingOptionCatalog],
) -> dict[str, Any]:
    cache_key = _ml_filter_bundle_cache_key(
        source_tables,
        selected_history_window,
        collect_forecasting_metadata=collect_forecasting_metadata,
        build_option_catalog_sql=build_option_catalog_sql,
    )
    cached_bundle = _ML_FILTER_BUNDLE_CACHE.get(cache_key)
    if cached_bundle is not None:
        return cached_bundle

    metadata_items, preload_notes = collect_forecasting_metadata(source_tables)
    payload = {
        "metadata_items": metadata_items,
        "preload_notes": preload_notes,
        "option_catalog": build_option_catalog_sql(
            source_tables,
            history_window=selected_history_window,
            metadata_items=metadata_items,
        ),
    }
    return _ML_FILTER_BUNDLE_CACHE.set(cache_key, payload)


def _ml_filter_bundle_cache_key(
    source_tables: Sequence[str],
    selected_history_window: str,
    *,
    collect_forecasting_metadata: Callable[..., Any],
    build_option_catalog_sql: Callable[..., Any],
) -> tuple[Any, ...]:
    normalized_tables = _canonicalize_source_tables(source_tables)[0]
    return (
        "ml_filter_bundle",
        *callable_cache_scope(collect_forecasting_metadata, build_option_catalog_sql),
        *normalized_tables,
        selected_history_window,
    )


def _ml_aggregation_input_cache_key(
    source_tables: Sequence[str],
    selected_history_window: str,
    selected_cause: str,
    selected_object_category: str,
    *,
    build_daily_history_sql: Callable[..., Any],
    count_forecasting_records_sql: Callable[..., Any],
) -> tuple[Any, ...]:
    normalized_tables = _canonicalize_source_tables(source_tables)[0]
    return (
        "ml_aggregation_inputs",
        *callable_cache_scope(build_daily_history_sql, count_forecasting_records_sql),
        *normalized_tables,
        selected_history_window,
        _normalize_filter_value(selected_cause),
        _normalize_filter_value(selected_object_category),
    )


class MlModelDataLoader(DataLoader):
    def __init__(self) -> None:
        super().__init__(cache=None, cache_namespace="ml_model_data")

    def clear_cache(self) -> None:
        clear_ml_model_input_cache()


__all__ = [
    "MlModelDataLoader",
    "clear_ml_model_input_cache",
    "load_ml_filter_bundle",
    "load_ml_aggregation_inputs",
]

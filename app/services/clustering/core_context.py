from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from app.plotly_bundle import get_plotly_bundle
from app.cache import CopyingTtlCache
from app.services.charting import build_empty_chart_bundle as _empty_chart_bundle
from config.constants import CLUSTER_COUNT_OPTIONS

from .data import (
    _build_table_options,
    _parse_cluster_count,
    _resolve_selected_table,
)
from .quality_silhouette import _empty_clustering_quality_assessment
from app.services.shared.formatting import (
    format_datetime as _format_datetime,
    format_integer as _format_integer,
)

_CLUSTERING_CACHE = CopyingTtlCache(ttl_seconds=None)
_CLUSTERING_CACHE_SCHEMA_VERSION = "v4_no_sample_limit"


def clear_clustering_cache() -> None:
    _CLUSTERING_CACHE.clear()


def _normalize_clustering_cache_value(value: str) -> str:
    return str(value or "").strip()


def _build_clustering_cache_key(
    selected_table: str,
    selected_table_names: Sequence[str] | None,
    cluster_count: int,
    feature_columns: Sequence[str] | None,
    cluster_count_is_explicit: bool,
) -> tuple[str, ...]:
    return (
        _CLUSTERING_CACHE_SCHEMA_VERSION,
        selected_table,
        *tuple(
            "table:" + str(item).strip()
            for item in (selected_table_names or [])
            if str(item).strip()
        ),
        str(cluster_count),
        "manual_k" if cluster_count_is_explicit else "auto_k",
        *tuple(str(item).strip() for item in (feature_columns or []) if str(item).strip()),
    )


def _normalize_feature_columns(feature_columns: Sequence[str] | None) -> list[str]:
    return [str(item).strip() for item in (feature_columns or []) if str(item).strip()]


def _normalize_table_names(table_options: Sequence[dict[str, str]], table_names: Sequence[str] | None) -> list[str]:
    allowed = {
        str(item.get("value") or "").strip()
        for item in table_options
        if str(item.get("value") or "").strip() and str(item.get("value") or "").strip() != "all"
    }
    normalized: list[str] = []
    for item in (table_names or []):
        value = str(item or "").strip()
        if not value or value == "all" or value not in allowed:
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


def _build_clustering_request_state(
    table_name: str = "",
    table_names: Sequence[str] | None = None,
    cluster_count: str = "4",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    table_options = _build_table_options()
    selected_table_names = _normalize_table_names(table_options, table_names)
    if len(selected_table_names) == 1:
        selected_table = selected_table_names[0]
    elif len(selected_table_names) > 1:
        selected_table = "all"
    else:
        selected_table = _resolve_selected_table(table_options, table_name)
        if selected_table and selected_table != "all":
            selected_table_names = [selected_table]
    requested_cluster_count = _parse_cluster_count(cluster_count)
    normalized_feature_columns = _normalize_feature_columns(feature_columns)
    cache_key = _build_clustering_cache_key(
        selected_table=selected_table,
        selected_table_names=selected_table_names,
        cluster_count=requested_cluster_count,
        feature_columns=normalized_feature_columns,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    return {
        "table_options": table_options,
        "selected_table": selected_table,
        "selected_table_names": selected_table_names,
        "cluster_count": requested_cluster_count,
        "feature_columns": normalized_feature_columns,
        "cluster_count_is_explicit": bool(cluster_count_is_explicit),
        "cache_key": cache_key,
    }


def get_clustering_page_context(
    table_name: str = "",
    table_names: Sequence[str] | None = None,
    cluster_count: str = "4",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    from .core_runner import get_clustering_data

    initial_data = get_clustering_data(
        table_name=table_name,
        table_names=table_names,
        cluster_count=cluster_count,
        feature_columns=feature_columns,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    return {
        "generated_at": _format_datetime(datetime.now()),
        "initial_data": initial_data,
        "plotly_js": get_plotly_bundle(),
        "has_data": bool(initial_data["filters"]["available_tables"]),
    }


def get_clustering_shell_context(
    table_name: str = "",
    table_names: Sequence[str] | None = None,
    cluster_count: str = "4",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    request_state = _build_clustering_request_state(
        table_name=table_name,
        table_names=table_names,
        cluster_count=cluster_count,
        feature_columns=feature_columns,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    table_options = request_state["table_options"]
    selected_table = request_state["selected_table"]
    selected_table_names = request_state["selected_table_names"]
    requested_cluster_count = request_state["cluster_count"]
    initial_data = _empty_clustering_data(
        table_options=table_options,
        selected_table=selected_table,
        selected_table_names=selected_table_names,
        cluster_count=requested_cluster_count,
    )
    initial_data["bootstrap_mode"] = "deferred"
    if feature_columns:
        initial_data["filters"]["feature_columns"] = [str(item).strip() for item in feature_columns if str(item).strip()]
    return {
        "generated_at": _format_datetime(datetime.now()),
        "initial_data": initial_data,
        "plotly_js": "",
        "has_data": bool(initial_data["filters"]["available_tables"]),
    }


def _empty_clustering_data(
    table_options: list[dict[str, str]],
    selected_table: str,
    selected_table_names: Sequence[str] | None,
    cluster_count: int,
) -> dict[str, Any]:
    normalized_table_names = [str(item).strip() for item in (selected_table_names or []) if str(item).strip()]
    selected_table_label = next(
        (item.get("label") for item in table_options if str(item.get("value") or "") == selected_table),
        selected_table or "Нет таблицы",
    )
    if len(normalized_table_names) > 1:
        selected_table_label = f"Выбрано таблиц: {len(normalized_table_names)}"
    return {
        "generated_at": _format_datetime(datetime.now()),
        "has_data": False,
        "model_description": "",
        "summary": {
            "selected_table_label": str(selected_table_label),
            "total_incidents_display": "0",
            "total_entities_display": "0",
            "sampled_entities_display": "0",
            "clustered_entities_display": "0",
            "excluded_entities_display": "0",
            "candidate_features_display": "0",
            "selected_features_display": "0",
            "cluster_count_display": _format_integer(cluster_count),
            "cluster_count_requested_display": _format_integer(cluster_count),
            "cluster_count_note": f"Сейчас основной вывод показан для k={_format_integer(cluster_count)}.",
            "suggested_cluster_count_label": "Рекомендуемый k",
            "suggested_cluster_count_display": "—",
            "suggested_cluster_count_note": "Диагностика k появится, когда хватит данных для сравнения нескольких вариантов.",
            "elbow_cluster_count_display": "—",
            "silhouette_display": "—",
            "pca_variance_display": "0%",
            "inertia_display": "0",
        },
        "quality_assessment": _empty_clustering_quality_assessment(),
        "cluster_profiles": [],
        "centroid_columns": [],
        "centroid_rows": [],
        "representative_columns": [],
        "representative_rows": [],
        "cluster_risk": [],
        "charts": {
            "feature_importance_chart": _empty_chart_bundle(
                "Вклад признаков в разделение кластеров",
                "Недостаточно данных, чтобы оценить вклад признаков в разделение кластеров.",
            ),
            "radar_chart": _empty_chart_bundle(
                "Профили кластеров по признакам",
                "Недостаточно данных для построения радар-графика профилей кластеров.",
            ),
            "scatter": _empty_chart_bundle(
                "Кластеры территорий на двумерной проекции",
                "Недостаточно данных, чтобы показать типы территорий на проекции главных компонент.",
            ),
            "distribution": _empty_chart_bundle(
                "Размеры кластеров по числу территорий",
                "Распределение территорий по типам появится после расчёта.",
            ),
            "diagnostics": _empty_chart_bundle(
                "Подсказка по числу кластеров",
                "Диагностика k появится, когда хватит территорий для сравнения нескольких вариантов.",
            ),
        },
        "notes": [],
        "filters": {
            "table_name": selected_table,
            "table_names": normalized_table_names,
            "cluster_count": str(cluster_count),
            "feature_columns": [],
            "available_tables": table_options,
            "available_cluster_counts": [
                {"value": str(item), "label": f"{item} кластера" if item < 5 else f"{item} кластеров"}
                for item in CLUSTER_COUNT_OPTIONS
            ],
            "available_features": [],
        },
    }

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
    _parse_sampling_strategy,
    _resolve_selected_table,
)
from .data_impl import SAMPLING_STRATEGY_OPTIONS
from .quality_silhouette import _empty_clustering_quality_assessment
from .utils import _format_datetime, _format_integer

_CLUSTERING_CACHE = CopyingTtlCache(ttl_seconds=None)
_CLUSTERING_CACHE_SCHEMA_VERSION = "v4_no_sample_limit"


def clear_clustering_cache() -> None:
    _CLUSTERING_CACHE.clear()


def _normalize_clustering_cache_value(value: str) -> str:
    return str(value or "").strip()


def _build_clustering_cache_key(
    selected_table: str,
    cluster_count: int,
    sampling_strategy: str,
    feature_columns: Sequence[str] | None,
    cluster_count_is_explicit: bool,
) -> tuple[str, ...]:
    return (
        _CLUSTERING_CACHE_SCHEMA_VERSION,
        selected_table,
        str(cluster_count),
        _normalize_clustering_cache_value(sampling_strategy),
        "manual_k" if cluster_count_is_explicit else "auto_k",
        *tuple(str(item).strip() for item in (feature_columns or []) if str(item).strip()),
    )


def _normalize_feature_columns(feature_columns: Sequence[str] | None) -> list[str]:
    return [str(item).strip() for item in (feature_columns or []) if str(item).strip()]


def _build_clustering_request_state(
    table_name: str = "",
    cluster_count: str = "4",
    sampling_strategy: str = "stratified",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    table_options = _build_table_options()
    selected_table = _resolve_selected_table(table_options, table_name)
    requested_cluster_count = _parse_cluster_count(cluster_count)
    selected_sampling_strategy = _parse_sampling_strategy(sampling_strategy)
    normalized_feature_columns = _normalize_feature_columns(feature_columns)
    cache_key = _build_clustering_cache_key(
        selected_table=selected_table,
        cluster_count=requested_cluster_count,
        sampling_strategy=selected_sampling_strategy,
        feature_columns=normalized_feature_columns,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    return {
        "table_options": table_options,
        "selected_table": selected_table,
        "cluster_count": requested_cluster_count,
        "sampling_strategy": selected_sampling_strategy,
        "feature_columns": normalized_feature_columns,
        "cluster_count_is_explicit": bool(cluster_count_is_explicit),
        "cache_key": cache_key,
    }


def get_clustering_page_context(
    table_name: str = "",
    cluster_count: str = "4",
    sampling_strategy: str = "stratified",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    from .core_runner import get_clustering_data

    initial_data = get_clustering_data(
        table_name=table_name,
        cluster_count=cluster_count,
        sampling_strategy=sampling_strategy,
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
    cluster_count: str = "4",
    sampling_strategy: str = "stratified",
    feature_columns: Sequence[str] | None = None,
    cluster_count_is_explicit: bool = False,
) -> dict[str, Any]:
    table_options = _build_table_options()
    selected_table = _resolve_selected_table(table_options, table_name)
    requested_cluster_count = _parse_cluster_count(cluster_count)
    selected_sampling_strategy = _parse_sampling_strategy(sampling_strategy)
    initial_data = _empty_clustering_data(
        table_options=table_options,
        selected_table=selected_table,
        cluster_count=requested_cluster_count,
        sampling_strategy=selected_sampling_strategy,
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
    cluster_count: int,
    sampling_strategy: str,
) -> dict[str, Any]:
    selected_table_label = next(
        (item.get("label") for item in table_options if str(item.get("value") or "") == selected_table),
        selected_table or "РќРµС‚ С‚Р°Р±Р»РёС†С‹",
    )
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
            "cluster_count_note": f"РЎРµР№С‡Р°СЃ РѕСЃРЅРѕРІРЅРѕР№ РІС‹РІРѕРґ РїРѕРєР°Р·Р°РЅ РґР»СЏ k={_format_integer(cluster_count)}.",
            "suggested_cluster_count_label": "Р РµРєРѕРјРµРЅРґСѓРµРјС‹Р№ k",
            "suggested_cluster_count_display": "вЂ”",
            "suggested_cluster_count_note": "Р”РёР°РіРЅРѕСЃС‚РёРєР° k РїРѕСЏРІРёС‚СЃСЏ, РєРѕРіРґР° С…РІР°С‚РёС‚ РґР°РЅРЅС‹С… РґР»СЏ СЃСЂР°РІРЅРµРЅРёСЏ РЅРµСЃРєРѕР»СЊРєРёС… РІР°СЂРёР°РЅС‚РѕРІ.",
            "elbow_cluster_count_display": "вЂ”",
            "silhouette_display": "вЂ”",
            "pca_variance_display": "0%",
            "inertia_display": "0",
            "sampling_strategy_label": next(
                (item["label"] for item in SAMPLING_STRATEGY_OPTIONS if item["value"] == sampling_strategy),
                SAMPLING_STRATEGY_OPTIONS[0]["label"],
            ),
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
                "Р’РєР»Р°Рґ РїСЂРёР·РЅР°РєРѕРІ РІ СЂР°Р·РґРµР»РµРЅРёРµ РєР»Р°СЃС‚РµСЂРѕРІ",
                "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С…, С‡С‚РѕР±С‹ РѕС†РµРЅРёС‚СЊ РІРєР»Р°Рґ РїСЂРёР·РЅР°РєРѕРІ РІ СЂР°Р·РґРµР»РµРЅРёРµ РєР»Р°СЃС‚РµСЂРѕРІ.",
            ),
            "radar_chart": _empty_chart_bundle(
                "РџСЂРѕС„РёР»Рё РєР»Р°СЃС‚РµСЂРѕРІ РїРѕ РїСЂРёР·РЅР°РєР°Рј",
                "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С… РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ СЂР°РґР°СЂ-РіСЂР°С„РёРєР° РїСЂРѕС„РёР»РµР№ РєР»Р°СЃС‚РµСЂРѕРІ.",
            ),
            "scatter": _empty_chart_bundle(
                "РљР»Р°СЃС‚РµСЂС‹ С‚РµСЂСЂРёС‚РѕСЂРёР№ РЅР° РґРІСѓРјРµСЂРЅРѕР№ РїСЂРѕРµРєС†РёРё",
                "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С…, С‡С‚РѕР±С‹ РїРѕРєР°Р·Р°С‚СЊ С‚РёРїС‹ С‚РµСЂСЂРёС‚РѕСЂРёР№ РЅР° РїСЂРѕРµРєС†РёРё РіР»Р°РІРЅС‹С… РєРѕРјРїРѕРЅРµРЅС‚.",
            ),
            "distribution": _empty_chart_bundle(
                "Р Р°Р·РјРµСЂС‹ РєР»Р°СЃС‚РµСЂРѕРІ РїРѕ С‡РёСЃР»Сѓ С‚РµСЂСЂРёС‚РѕСЂРёР№",
                "Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ С‚РµСЂСЂРёС‚РѕСЂРёР№ РїРѕ С‚РёРїР°Рј РїРѕСЏРІРёС‚СЃСЏ РїРѕСЃР»Рµ СЂР°СЃС‡С‘С‚Р°.",
            ),
            "diagnostics": _empty_chart_bundle(
                "РџРѕРґСЃРєР°Р·РєР° РїРѕ С‡РёСЃР»Сѓ РєР»Р°СЃС‚РµСЂРѕРІ",
                "Р”РёР°РіРЅРѕСЃС‚РёРєР° k РїРѕСЏРІРёС‚СЃСЏ, РєРѕРіРґР° С…РІР°С‚РёС‚ С‚РµСЂСЂРёС‚РѕСЂРёР№ РґР»СЏ СЃСЂР°РІРЅРµРЅРёСЏ РЅРµСЃРєРѕР»СЊРєРёС… РІР°СЂРёР°РЅС‚РѕРІ.",
            ),
        },
        "notes": [],
        "filters": {
            "table_name": selected_table,
            "cluster_count": str(cluster_count),
            "sampling_strategy": sampling_strategy,
            "feature_columns": [],
            "available_tables": table_options,
            "available_cluster_counts": [
                {"value": str(item), "label": f"{item} РєР»Р°СЃС‚РµСЂР°" if item < 5 else f"{item} РєР»Р°СЃС‚РµСЂРѕРІ"}
                for item in CLUSTER_COUNT_OPTIONS
            ],
            "available_sampling_strategies": SAMPLING_STRATEGY_OPTIONS,
            "available_features": [],
        },
    }

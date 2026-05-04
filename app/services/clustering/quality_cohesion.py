from __future__ import annotations

from typing import Sequence

from config.constants import LOW_SUPPORT_TERRITORY_THRESHOLD
from .quality_assessment import (
    compute_method_algorithm_key,
    compute_segmentation_strength,
)
from .types import ClusterLabel, ClusterMethod, ClusterMetrics
from .utils import _format_integer, _format_number, _format_percent


def _summarize_segmentation_strength(
    clustering: ClusterMetrics,
    selected_method: ClusterMethod | None = None,
    recommended_method: ClusterMethod | None = None,
    cluster_count: int | None = None,
    recommended_k: int | None = None,
) -> ClusterLabel:
    return compute_segmentation_strength(
        clustering,
        selected_method=selected_method,
        recommended_method=recommended_method,
        cluster_count=cluster_count,
        recommended_k=recommended_k,
    )


def _build_stability_note(clustering: ClusterMetrics, resample_share_label: str) -> str:
    stability_ari = clustering.get("stability_ari")
    initialization_ari = clustering.get("initialization_ari")
    if stability_ari is None:
        return "РћС†РµРЅРёС‚СЊ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ РЅР° РїРѕРІС‚РѕСЂРЅС‹С… РїРѕРґРІС‹Р±РѕСЂРєР°С… РЅРµ СѓРґР°Р»РѕСЃСЊ: РІ С‚РµРєСѓС‰РµРј СЃСЂРµР·Рµ СЃР»РёС€РєРѕРј РјР°Р»Рѕ С‚РµСЂСЂРёС‚РѕСЂРёР№ РґР»СЏ РЅР°РґС‘Р¶РЅРѕРіРѕ СЃСЂР°РІРЅРµРЅРёСЏ РїРµСЂРµСЃСЌРјРїР»РѕРІ."
    if initialization_ari is None:
        return (
            f"РџСЂРѕРІРµСЂРєР° РЅР° РїРѕРІС‚РѕСЂРЅС‹С… {resample_share_label}-РїРѕРґРІС‹Р±РѕСЂРєР°С… РґР°Р»Р° "
            f"{_format_number(stability_ari, 3)}: С‚Р°Рє РІРёРґРЅРѕ, РЅР°СЃРєРѕР»СЊРєРѕ СЂРµР·СѓР»СЊС‚Р°С‚ РїРѕРІС‚РѕСЂСЏРµС‚СЃСЏ РЅРµ С‚РѕР»СЊРєРѕ РЅР° С‚РµС… Р¶Рµ РґР°РЅРЅС‹С…."
        )

    gap = float(initialization_ari) - float(stability_ari)
    if gap >= 0.15:
        return (
            f"РќР° РѕРґРЅРёС… Рё С‚РµС… Р¶Рµ РґР°РЅРЅС‹С… СЂР°Р·Р±РёРµРЅРёРµ РїРѕС‡С‚Рё РЅРµ РјРµРЅСЏРµС‚СЃСЏ ({_format_number(initialization_ari, 3)}), "
            f"РЅРѕ РЅР° РїРѕРІС‚РѕСЂРЅС‹С… {resample_share_label}-РїРѕРґРІС‹Р±РѕСЂРєР°С… СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ Р·Р°РјРµС‚РЅРѕ РЅРёР¶Рµ "
            f"({_format_number(stability_ari, 3)}), РїРѕСЌС‚РѕРјСѓ СЂРµР·СѓР»СЊС‚Р°С‚ С‡СѓРІСЃС‚РІРёС‚РµР»РµРЅ Рє СЃРѕСЃС‚Р°РІСѓ РІС‹Р±РѕСЂРєРё."
        )
    return (
        f"РќР° РїРѕРІС‚РѕСЂРЅС‹С… {resample_share_label}-РїРѕРґРІС‹Р±РѕСЂРєР°С… СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ СЃРѕСЃС‚Р°РІР»СЏРµС‚ "
        f"{_format_number(stability_ari, 3)}; СЌС‚Рѕ Р±Р»РёР·РєРѕ Рє РїСЂРѕРІРµСЂРєРµ РЅР° С‚РµС… Р¶Рµ РґР°РЅРЅС‹С… "
        f"({_format_number(initialization_ari, 3)})."
    )


def _build_method_recommendation_note(
    selected_method: ClusterMethod | None,
    recommended_method: ClusterMethod | None,
) -> str:
    selected_label = str((selected_method or {}).get("method_label") or "KMeans")
    recommended_label = str((recommended_method or {}).get("method_label") or selected_label)
    if not selected_method:
        return f"Р”Р»СЏ С‚РµРєСѓС‰РµРіРѕ СЃСЂРµР·Р° СЂР°Р±РѕС‡РёРј РјРµС‚РѕРґРѕРј РѕСЃС‚Р°С‘С‚СЃСЏ {recommended_label}."
    if (recommended_method or {}).get("method_key") != (selected_method or {}).get("method_key"):
        if _resolve_method_algorithm_key(recommended_method) == _resolve_method_algorithm_key(selected_method):
            return (
                f"РќР° СЃС‚СЂР°РЅРёС†Рµ СЃРµР№С‡Р°СЃ РїРѕРєР°Р·Р°РЅ РІС‹РІРѕРґ {selected_label}, РЅРѕ РЅР° С‚РѕРј Р¶Рµ Р°Р»РіРѕСЂРёС‚РјРµ Р±РѕР»РµРµ СѓР±РµРґРёС‚РµР»СЊРЅРѕ РІС‹РіР»СЏРґРёС‚ "
                f"РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ {recommended_label}: С‚Р°Рє СЌС„С„РµРєС‚ СЃС‚СЂР°С‚РµРіРёРё РІРµСЃРѕРІ РЅРµ СЃРјРµС€РёРІР°РµС‚СЃСЏ СЃ СЌС„С„РµРєС‚РѕРј СЃР°РјРѕРіРѕ РјРµС‚РѕРґР°."
            )
        return (
            f"РўРµРєСѓС‰РёР№ РІС‹РІРѕРґ РЅР° СЃС‚СЂР°РЅРёС†Рµ РїРѕСЃС‚СЂРѕРµРЅ РјРµС‚РѕРґРѕРј {selected_label}, РЅРѕ РїРѕ СЃРѕРІРѕРєСѓРїРЅРѕСЃС‚Рё РјРµС‚СЂРёРє Рё СЂР°Р·РјРµСЂРѕРІ РєР»Р°СЃС‚РµСЂРѕРІ РґР»СЏ СЌС‚РѕРіРѕ СЃСЂРµР·Р° Р»СѓС‡С€Рµ РІС‹РіР»СЏРґРёС‚ {recommended_label}."
        )
    return f"{selected_label} РѕСЃС‚Р°С‘С‚СЃСЏ РїСЂРµРґРїРѕС‡С‚РёС‚РµР»СЊРЅС‹Рј РјРµС‚РѕРґРѕРј: Р°Р»СЊС‚РµСЂРЅР°С‚РёРІС‹ РЅРµ РґР°СЋС‚ Р±РѕР»РµРµ СЃРёР»СЊРЅРѕРіРѕ РєР°С‡РµСЃС‚РІР° Р±РµР· СѓС…СѓРґС€РµРЅРёСЏ СЂР°Р·РјРµСЂРѕРІ РєР»Р°СЃС‚РµСЂРѕРІ."


def _build_method_comparison_scope_note(method_comparison: Sequence[ClusterMethod]) -> str:
    selected_method = next((row for row in method_comparison if row.get("is_selected")), None)
    if not selected_method:
        return ""
    selected_algorithm = _resolve_method_algorithm_key(selected_method)
    selected_key = str((selected_method or {}).get("method_key") or "")
    same_algorithm_alternatives = [
        row
        for row in method_comparison
        if row is not selected_method
        and _resolve_method_algorithm_key(row) == selected_algorithm
        and str(row.get("method_key") or "") != selected_key
    ]
    if not same_algorithm_alternatives:
        return ""
    return (
        "Р”Р»СЏ С‡РµСЃС‚РЅРѕРіРѕ СЃСЂР°РІРЅРµРЅРёСЏ РІР»РёСЏРЅРёРµ РІРµСЃРѕРІ РІС‹РЅРµСЃРµРЅРѕ РѕС‚РґРµР»СЊРЅРѕ: СЂСЏРґРѕРј СЃ СЂР°Р±РѕС‡РµР№ РєРѕРЅС„РёРіСѓСЂР°С†РёРµР№ KMeans РїРѕРєР°Р·Р°РЅ KMeans "
        "СЃ РґСЂСѓРіРѕР№ СЃС‚СЂР°С‚РµРіРёРµР№ РІРµСЃРѕРІ, РїРѕСЌС‚РѕРјСѓ СЂРµРєРѕРјРµРЅРґР°С†РёСЏ РїРѕ РјРµС‚РѕРґСѓ РЅРµ СЃРјРµС€РёРІР°РµС‚ СЌС„С„РµРєС‚ Р°Р»РіРѕСЂРёС‚РјР° Рё СЌС„С„РµРєС‚ РІРµСЃРѕРІ."
    )


def _resolve_method_algorithm_key(method_row: ClusterMethod | None) -> str:
    return compute_method_algorithm_key(method_row)


def _build_cluster_shape_note(clustering: ClusterMetrics) -> str:
    smallest_cluster_size = int(clustering.get("smallest_cluster_size") or 0)
    largest_cluster_size = int(clustering.get("largest_cluster_size") or 0)
    balance_ratio = float(clustering.get("cluster_balance_ratio") or 0.0)
    microcluster_threshold = int(clustering.get("microcluster_threshold") or 0)
    if clustering.get("has_microclusters"):
        return (
            f"Р•СЃС‚СЊ РјРёРєСЂРѕРєР»Р°СЃС‚РµСЂС‹: СЃР°РјС‹Р№ РјР°Р»РµРЅСЊРєРёР№ РєР»Р°СЃС‚РµСЂ СЃРѕРґРµСЂР¶РёС‚ {_format_integer(smallest_cluster_size)} С‚РµСЂСЂРёС‚РѕСЂРёР№ РїСЂРё РїРѕСЂРѕРіРµ РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёСЏ {_format_integer(microcluster_threshold)}, "
            "РїРѕСЌС‚РѕРјСѓ С‡Р°СЃС‚СЊ СЃРµРіРјРµРЅС‚Р°С†РёРё РјРѕР¶РµС‚ РґРµСЂР¶Р°С‚СЊСЃСЏ РЅР° РѕС‡РµРЅСЊ РјР°Р»РѕР№ РіСЂСѓРїРїРµ РЅР°Р±Р»СЋРґРµРЅРёР№."
        )
    if balance_ratio < 0.12:
        return (
            f"РљР»Р°СЃС‚РµСЂС‹ Р·Р°РјРµС‚РЅРѕ РЅРµСЃР±Р°Р»Р°РЅСЃРёСЂРѕРІР°РЅС‹: min/max = {_format_integer(smallest_cluster_size)} / {_format_integer(largest_cluster_size)} "
            f"({ _format_percent(balance_ratio) }), РїРѕСЌС‚РѕРјСѓ СЂРµР·СѓР»СЊС‚Р°С‚ СЃС‚РѕРёС‚ С‚СЂР°РєС‚РѕРІР°С‚СЊ РѕСЃС‚РѕСЂРѕР¶РЅРµРµ."
        )
    if balance_ratio < 0.18:
        return (
            f"РљР»Р°СЃС‚РµСЂС‹ СѓРјРµСЂРµРЅРЅРѕ РЅРµСЃР±Р°Р»Р°РЅСЃРёСЂРѕРІР°РЅС‹: min/max = {_format_integer(smallest_cluster_size)} / {_format_integer(largest_cluster_size)} "
            f"({ _format_percent(balance_ratio) })."
        )
    return ""

__all__ = [
    '_summarize_segmentation_strength',
    '_build_stability_note',
    '_build_method_recommendation_note',
    '_build_method_comparison_scope_note',
    '_resolve_method_algorithm_key',
    '_build_cluster_shape_note',
    'compute_method_algorithm_key',
    'compute_segmentation_strength',
]

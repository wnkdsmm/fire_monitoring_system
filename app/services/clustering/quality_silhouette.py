from __future__ import annotations

from typing import Any, Sequence

from config.constants import LOW_SUPPORT_TERRITORY_THRESHOLD, STABILITY_RESAMPLE_RATIO
from .count_guidance import _build_cluster_count_guidance
from .quality_cohesion import (
    _build_cluster_shape_note,
    _build_method_comparison_scope_note,
    _build_method_recommendation_note,
    _build_stability_note,
    _resolve_method_algorithm_key,
    _summarize_segmentation_strength,
)
from .types import (
    ClusterCountGuidance,
    ClusterLabel,
    ClusterMethod,
    ClusterMetrics,
    ClusteringQualityAssessment,
    FeatureAblationRow,
    FeatureSelectionReport,
    MethodComparisonRow,
    QualityConfigurationContext,
    QualityDiagnostics,
    QualityLabelContext,
    QualityNoteContext,
    QualityScore,
    SupportSummary,
)
from .utils import _format_integer, _format_number, _format_percent

def _format_configuration_label(configuration: ClusterMethod | None) -> str:
    if not configuration:
        return "вЂ”"
    method_label = str(configuration.get("method_label") or "РњРµС‚РѕРґ")
    cluster_count = configuration.get("cluster_count")
    if cluster_count:
        return f"{method_label}, k={_format_integer(cluster_count)}"
    return method_label


def _empty_clustering_quality_assessment() -> ClusteringQualityAssessment:
    return {
        "ready": False,
        "title": "РћС†РµРЅРєР° РєР°С‡РµСЃС‚РІР° РєР»Р°СЃС‚РµСЂРёР·Р°С†РёРё",
        "subtitle": "РџРѕСЃР»Рµ СЂР°СЃС‡РµС‚Р° Р·РґРµСЃСЊ РїРѕСЏРІРёС‚СЃСЏ РїРѕРЅСЏС‚РЅР°СЏ СЃРІРѕРґРєР°: РЅР°СЃРєРѕР»СЊРєРѕ РіСЂСѓРїРїС‹ СЂР°Р·Р»РёС‡Р°СЋС‚СЃСЏ, РЅР°СЃРєРѕР»СЊРєРѕ СЂРµР·СѓР»СЊС‚Р°С‚ СѓСЃС‚РѕР№С‡РёРІ Рё РєР°РєР°СЏ РЅР°СЃС‚СЂРѕР№РєР° РІС‹РіР»СЏРґРёС‚ Р»СѓС‡С€РµР№.",
        "metric_cards": [],
        "methodology_items": [],
        "comparison_rows": [],
        "dissertation_points": ["РџРѕРєР° РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С… РґР»СЏ СЂР°СЃС‡РµС‚Р° РјРµС‚СЂРёРє РєР°С‡РµСЃС‚РІР° РєР»Р°СЃС‚РµСЂРёР·Р°С†РёРё."],
    }


def _build_configuration_recommendation_note(
    working_configuration: ClusterMethod | None,
    recommended_configuration: ClusterMethod | None,
    *,
    cluster_count_is_explicit: bool,
) -> str:
    working_label = _format_configuration_label(working_configuration)
    recommended_label = _format_configuration_label(recommended_configuration)
    if not recommended_configuration or working_label == recommended_label:
        if cluster_count_is_explicit:
            return f"РќР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРѕРј k С‚РµРєСѓС‰РёР№ РІС‹РІРѕРґ СѓР¶Рµ РёСЃРїРѕР»СЊР·СѓРµС‚ Р»СѓС‡С€СѓСЋ СЃРѕРїРѕСЃС‚Р°РІРёРјСѓСЋ РєРѕРЅС„РёРіСѓСЂР°С†РёСЋ: {working_label}."
        return f"РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ СЃС‚СЂР°РЅРёС†Р° СЃСЂР°Р·Сѓ РїРѕРєР°Р·С‹РІР°РµС‚ СЂРµРєРѕРјРµРЅРґСѓРµРјСѓСЋ РєРѕРЅС„РёРіСѓСЂР°С†РёСЋ: {working_label}."
    if cluster_count_is_explicit:
        return (
            f"РќР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРѕРј k С‚РµРєСѓС‰РёР№ РІС‹РІРѕРґ РёСЃРїРѕР»СЊР·СѓРµС‚ Р»СѓС‡С€СѓСЋ СЃРѕРїРѕСЃС‚Р°РІРёРјСѓСЋ РєРѕРЅС„РёРіСѓСЂР°С†РёСЋ {working_label}, "
            f"РЅРѕ РїРѕ РІСЃРµРјСѓ РґРѕСЃС‚СѓРїРЅРѕРјСѓ РґРёР°РїР°Р·РѕРЅСѓ СѓР±РµРґРёС‚РµР»СЊРЅРµРµ РІС‹РіР»СЏРґРёС‚ {recommended_label}."
        )
    return (
        f"РЎРµР№С‡Р°СЃ СЃС‚СЂР°РЅРёС†Р° РїРѕСЃС‚СЂРѕРµРЅР° РїРѕ РєРѕРЅС„РёРіСѓСЂР°С†РёРё {working_label}, "
        f"РЅРѕ РїРѕ РІСЃРµРјСѓ РґРѕСЃС‚СѓРїРЅРѕРјСѓ РґРёР°РїР°Р·РѕРЅСѓ Р»СѓС‡С€Рµ РІС‹РіР»СЏРґРёС‚ {recommended_label}."
    )


def _resolve_quality_configuration_context(
    *,
    method_comparison: Sequence[ClusterMethod],
    diagnostics: QualityDiagnostics | None,
    cluster_count: int,
) -> QualityConfigurationContext:
    diagnostics = diagnostics or {}
    recommended_configuration = dict(diagnostics.get("best_configuration") or {})
    recommended_k = int(recommended_configuration.get("cluster_count") or diagnostics.get("best_quality_k") or cluster_count)
    selected_method = next(
        (row for row in method_comparison if row.get("is_selected")),
        method_comparison[0] if method_comparison else None,
    )
    recommended_row = next((row for row in method_comparison if row.get("is_recommended")), selected_method)
    working_configuration = {**dict(selected_method or {}), "cluster_count": cluster_count}
    effective_recommended_configuration = (
        recommended_configuration
        or {**dict(recommended_row or {}), "cluster_count": recommended_k}
    )
    return {
        "recommended_k": recommended_k,
        "best_silhouette_k": diagnostics.get("best_silhouette_k"),
        "selected_method": selected_method,
        "working_configuration": working_configuration,
        "effective_recommended_configuration": effective_recommended_configuration,
        "recommended_method": effective_recommended_configuration or recommended_row or selected_method,
        "working_config_label": _format_configuration_label(working_configuration),
        "recommended_config_label": _format_configuration_label(effective_recommended_configuration),
    }


def _build_feature_selection_quality_label_context(
    feature_selection_report: FeatureSelectionReport | None,
) -> QualityLabelContext:
    report = feature_selection_report or {}
    return {
        "mode_label": str(report.get("volume_role_label") or "РџСЂРѕС„РёР»СЊ С‚РµСЂСЂРёС‚РѕСЂРёРё"),
        "mode_note": str(report.get("volume_note") or ""),
        "weighting_label": str(report.get("weighting_label") or "Р Р°РІРЅС‹Р№ РІРµСЃ С‚РµСЂСЂРёС‚РѕСЂРёР№"),
        "weighting_note": str(report.get("weighting_note") or ""),
        "weighting_meta": str(report.get("weighting_meta") or ""),
        "ablation_rows": list(report.get("ablation_rows") or []),
    }


def _build_ablation_warning_note(ablation_rows: Sequence[FeatureAblationRow]) -> str:
    negative_adds = [
        row for row in ablation_rows if row.get("direction") == "add" and float(row.get("delta_score") or 0.0) < 0.0
    ]
    if not negative_adds:
        return ""

    worst_feature = min(negative_adds, key=lambda item: float(item.get("delta_score") or 0.0))
    return (
        f"Р’ РїСЂРѕР±РЅРѕРј СЃСЂР°РІРЅРµРЅРёРё РїСЂРёР·РЅР°РєРѕРІ РєРѕР»РѕРЅРєР° '{worst_feature['feature']}' РЅРµ РІРѕС€Р»Р° РІ РёС‚РѕРіРѕРІС‹Р№ РЅР°Р±РѕСЂ, "
        "РїРѕС‚РѕРјСѓ С‡С‚Рѕ СЃ РЅРµР№ РєР»Р°СЃС‚РµСЂС‹ СЂР°Р·РґРµР»СЏР»РёСЃСЊ С…СѓР¶Рµ."
    )


def _format_quality_method_selection_label(row: ClusterMethod) -> str:
    if row.get("is_selected") and row.get("is_recommended"):
        return "Р Р°Р±РѕС‡РёР№ Рё Р»СѓС‡С€РёР№ РЅР° С‚РµРєСѓС‰РµРј k"
    if row.get("is_selected"):
        return "Р Р°Р±РѕС‡РёР№ РІС‹РІРѕРґ"
    if row.get("is_recommended"):
        return "Р›СѓС‡С€Рµ РЅР° С‚РµРєСѓС‰РµРј k"
    return "РЎСЂР°РІРЅРµРЅРёРµ"


def _build_quality_method_comparison_rows(
    method_comparison: Sequence[ClusterMethod],
) -> list[MethodComparisonRow]:
    return [
        {
            "method_label": row.get("method_label", "РњРµС‚РѕРґ"),
            "selection_label": _format_quality_method_selection_label(row),
            "silhouette_display": _format_number(row.get("silhouette"), 3),
            "davies_display": _format_number(row.get("davies_bouldin"), 3),
            "calinski_display": _format_number(row.get("calinski_harabasz"), 1),
            "balance_display": _format_percent(row.get("cluster_balance_ratio") or 0.0),
        }
        for row in method_comparison
    ]


def _build_quality_dissertation_points(
    *,
    segmentation_note: str,
    method_note: str,
    cluster_count_guidance: ClusterCountGuidance,
    recommended_config_label: str,
    working_config_label: str,
    recommended_k: int | None,
    best_silhouette_k: Any,
    stability_note: str,
    low_support_display: str,
    selected_features: Sequence[str],
    comparison_scope_note: str,
    cluster_shape_note: str,
    weighting_note: str,
    mode_note: str,
    ablation_note: str,
) -> list[str]:
    dissertation_points = [
        segmentation_note,
        method_note,
        str(cluster_count_guidance.get("quality_note") or ""),
        (
            f"Р•СЃР»Рё СЃРјРѕС‚СЂРµС‚СЊ РЅР° РІРµСЃСЊ РґРѕСЃС‚СѓРїРЅС‹Р№ РґРёР°РїР°Р·РѕРЅ РЅР°СЃС‚СЂРѕРµРє, Р»СѓС‡С€РµР№ РІС‹РіР»СЏРґРёС‚ РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ {recommended_config_label}."
            if recommended_config_label != working_config_label
            else f"РўРµРєСѓС‰Р°СЏ РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ {working_config_label} СѓР¶Рµ СЃРѕРІРїР°РґР°РµС‚ СЃ Р»СѓС‡С€РµР№ РЅР°Р№РґРµРЅРЅРѕР№."
        ),
        (
            f"РџРѕ С‡С‘С‚РєРѕСЃС‚Рё РіСЂР°РЅРёС† Р»СѓС‡С€РёР№ СЂРµР·СѓР»СЊС‚Р°С‚ РѕС‚РґРµР»СЊРЅРѕ РґР°С‘С‚ k={_format_integer(best_silhouette_k)}, "
            "РЅРѕ РёС‚РѕРіРѕРІРѕРµ С‡РёСЃР»Рѕ РіСЂСѓРїРї РІСЃС‘ СЂР°РІРЅРѕ РІС‹Р±РёСЂР°РµС‚СЃСЏ РІРјРµСЃС‚Рµ СЃ РїСЂРѕРІРµСЂРєРѕР№ Р±Р°Р»Р°РЅСЃР° СЂР°Р·РјРµСЂРѕРІ."
            if recommended_k and best_silhouette_k and recommended_k != best_silhouette_k
            else "РћСЃРЅРѕРІРЅС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё РєР°С‡РµСЃС‚РІР° РЅРµ СЃРїРѕСЂСЏС‚ РјРµР¶РґСѓ СЃРѕР±РѕР№ РїРѕ РІС‹Р±РѕСЂСѓ С‡РёСЃР»Р° РіСЂСѓРїРї."
        ),
        stability_note,
        (
            f"РЈ {low_support_display} С‚РµСЂСЂРёС‚РѕСЂРёР№ РїРѕР¶Р°СЂРѕРІ РЅРµРјРЅРѕРіРѕ, РїРѕСЌС‚РѕРјСѓ РёС… РґРѕР»РµРІС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё СЃР»РµРіРєР° "
            "РїРѕРґС‚СЏРЅСѓС‚С‹ Рє РѕР±С‰РµРјСѓ СѓСЂРѕРІРЅСЋ, С‡С‚РѕР±С‹ РµРґРёРЅРёС‡РЅС‹Рµ СЃР»СѓС‡Р°Рё РЅРµ РёСЃРєР°Р¶Р°Р»Рё СЂР°Р·Р±РёРµРЅРёРµ."
        ),
        f"РЎСЂР°РІРЅРµРЅРёРµ РјРµС‚РѕРґРѕРІ РІС‹РїРѕР»РЅРµРЅРѕ РЅР° С‚РѕРј Р¶Рµ РЅР°Р±РѕСЂРµ РїСЂРёР·РЅР°РєРѕРІ: {', '.join(selected_features)}.",
    ]
    if comparison_scope_note:
        dissertation_points.append(comparison_scope_note)
    if cluster_shape_note:
        dissertation_points.append(cluster_shape_note)
    if weighting_note:
        dissertation_points.append(weighting_note)
    if mode_note:
        dissertation_points.append(mode_note)
    if ablation_note:
        dissertation_points.append(ablation_note)
    return [item for item in dissertation_points if str(item).strip()]


def _build_quality_note_context(
    *,
    clustering: ClusterMetrics,
    selected_method: ClusterMethod | None,
    working_configuration: ClusterMethod,
    effective_recommended_configuration: ClusterMethod,
    recommended_method: ClusterMethod,
    cluster_count: int,
    recommended_k: int | None,
    method_comparison: Sequence[ClusterMethod],
    feature_selection_report: FeatureSelectionReport | None,
    resample_share_label: str,
    cluster_count_is_explicit: bool,
) -> QualityNoteContext:
    segmentation_summary = _summarize_segmentation_strength(
        clustering,
        selected_method=selected_method,
        recommended_method=recommended_method,
        cluster_count=cluster_count,
        recommended_k=recommended_k,
    )
    label_context = _build_feature_selection_quality_label_context(feature_selection_report)
    return {
        "segmentation_summary": segmentation_summary,
        "stability_note": _build_stability_note(clustering, resample_share_label),
        "method_note": _build_configuration_recommendation_note(
            working_configuration,
            effective_recommended_configuration,
            cluster_count_is_explicit=cluster_count_is_explicit,
        ),
        "comparison_scope_note": _build_method_comparison_scope_note(method_comparison),
        "cluster_shape_note": _build_cluster_shape_note(clustering),
        "label_context": label_context,
        "ablation_note": _build_ablation_warning_note(label_context["ablation_rows"]),
    }


def _build_quality_metric_cards(clustering: ClusterMetrics, resample_share_label: str) -> list[QualityScore]:
    return [
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ РєР»Р°СЃС‚РµСЂС‹ РѕС‚РґРµР»РµРЅС‹",
            "value": _format_number(clustering.get("silhouette"), 3),
            "meta": "Р§РµРј РІС‹С€Рµ Р·РЅР°С‡РµРЅРёРµ, С‚РµРј Р·Р°РјРµС‚РЅРµРµ РіСЂР°РЅРёС†С‹ РјРµР¶РґСѓ РіСЂСѓРїРїР°РјРё",
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ РєР»Р°СЃС‚РµСЂС‹ СЃРјРµС€РёРІР°СЋС‚СЃСЏ",
            "value": _format_number(clustering.get("davies_bouldin"), 3),
            "meta": "Р§РµРј РЅРёР¶Рµ Р·РЅР°С‡РµРЅРёРµ, С‚РµРј РјРµРЅСЊС€Рµ СЃРѕСЃРµРґРЅРёРµ РіСЂСѓРїРїС‹ Р·Р°С…РѕРґСЏС‚ РґСЂСѓРі РІ РґСЂСѓРіР°",
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ РіСЂСѓРїРїС‹ СЃРѕР±СЂР°РЅС‹ РїР»РѕС‚РЅРѕ",
            "value": _format_number(clustering.get("calinski_harabasz"), 1),
            "meta": "Р§РµРј РІС‹С€Рµ Р·РЅР°С‡РµРЅРёРµ, С‚РµРј СЃРѕР±СЂР°РЅРЅРµРµ С‚РµСЂСЂРёС‚РѕСЂРёРё РІРЅСѓС‚СЂРё СЃРІРѕРёС… РіСЂСѓРїРї",
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ РіСЂСѓРїРїС‹ СЂР°РІРЅРѕРјРµСЂРЅС‹",
            "value": _format_percent(clustering.get("cluster_balance_ratio") or 0.0),
            "meta": (
                f"Р Р°Р·РјРµСЂ СЃР°РјРѕР№ РјР°Р»РµРЅСЊРєРѕР№ Рё СЃР°РјРѕР№ Р±РѕР»СЊС€РѕР№ РіСЂСѓРїРїС‹: "
                f"{_format_integer(clustering.get('smallest_cluster_size'))} / "
                f"{_format_integer(clustering.get('largest_cluster_size'))}"
            ),
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ СЂРµР·СѓР»СЊС‚Р°С‚ РїРѕРІС‚РѕСЂСЏРµС‚СЃСЏ",
            "value": _format_number(clustering.get("stability_ari"), 3),
            "meta": f"РџСЂРѕРІРµСЂРµРЅРѕ РЅР° РїРѕРІС‚РѕСЂРЅС‹С… {resample_share_label}-РїРѕРґРІС‹Р±РѕСЂРєР°С…",
        },
    ]


def _build_quality_methodology_items(
    *,
    selected_features: Sequence[str],
    selected_method: ClusterMethod | None,
    working_config_label: str,
    recommended_config_label: str,
    segmentation_label: str,
    mode_label: str,
    weighting_label: str,
    weighting_meta: str,
    low_support_display: str,
    explained_variance: Any,
) -> list[QualityScore]:
    return [
        {
            "label": "РўРµРєСѓС‰Р°СЏ РЅР°СЃС‚СЂРѕР№РєР°",
            "value": working_config_label,
            "meta": "Р ВР СР ВµР Р…Р Р…Р С• РїРѕ СЌС‚РѕР№ РЅР°СЃС‚СЂРѕР№РєРµ РїРѕСЃС‚СЂРѕРµРЅС‹ РєР»Р°СЃС‚РµСЂС‹ РЅР° СЃС‚СЂР°РЅРёС†Рµ",
        },
        {
            "label": "Р›СѓС‡С€Р°СЏ РЅР°Р№РґРµРЅРЅР°СЏ РЅР°СЃС‚СЂРѕР№РєР°",
            "value": recommended_config_label,
            "meta": "Р›СѓС‡С€Р°СЏ РєРѕРјР±РёРЅР°С†РёСЏ СЂРµР¶РёРјР°, РІРµСЃРѕРІ, РјРµС‚РѕРґР° Рё С‡РёСЃР»Р° РєР»Р°СЃС‚РµСЂРѕРІ РІ РґРѕСЃС‚СѓРїРЅРѕРј РґРёР°РїР°Р·РѕРЅРµ",
        },
        {
            "label": "РњРµС‚РѕРґ СЃРµР№С‡Р°СЃ",
            "value": str((selected_method or {}).get("method_label") or "KMeans"),
            "meta": "Р›СѓС‡С€РёР№ СЃСЂРµРґРё СЃРѕРїРѕСЃС‚Р°РІРёРјС‹С… РІР°СЂРёР°РЅС‚РѕРІ РїСЂРё С‚РµРєСѓС‰РµРј С‡РёСЃР»Рµ РіСЂСѓРїРї",
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ РєР»Р°СЃС‚РµСЂС‹ СЂР°Р·Р»РёС‡РёРјС‹",
            "value": segmentation_label,
            "meta": "Р ВРЎвЂљР С•Р С–Р С•Р Р†Р В°РЎРЏ РѕС†РµРЅРєР° РїРѕ СЂР°Р·РґРµР»РµРЅРёСЋ РіСЂСѓРїРї, СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё Рё РёС… СЂР°Р·РјРµСЂР°Рј",
        },
        {
            "label": "Р§С‚Рѕ РёРјРµРЅРЅРѕ РєР»Р°СЃС‚РµСЂРёР·СѓРµРј",
            "value": mode_label,
            "meta": "РљР°РєРѕР№ РїСЂРѕС„РёР»СЊ С‚РµСЂСЂРёС‚РѕСЂРёРё СЃСЂР°РІРЅРёРІР°РµС‚СЃСЏ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ",
        },
        {
            "label": "Р’РµСЃС‹ С‚РµСЂСЂРёС‚РѕСЂРёР№",
            "value": weighting_label,
            "meta": weighting_meta or "РџРѕРєР°Р·С‹РІР°РµС‚, РІР»РёСЏРµС‚ Р»Рё С‡РёСЃР»Рѕ РїРѕР¶Р°СЂРѕРІ РЅР° РїРѕР»РѕР¶РµРЅРёРµ С‚РµСЂСЂРёС‚РѕСЂРёРё РІ РєР»Р°СЃС‚РµСЂРµ",
        },
        {
            "label": "РЎРєРѕР»СЊРєРѕ РїСЂРёР·РЅР°РєРѕРІ РІРѕС€Р»Рѕ РІ СЂР°СЃС‡С‘С‚",
            "value": _format_integer(len(selected_features)),
            "meta": "РћС‚РѕР±СЂР°РЅС‹ РїРѕС‚РѕРјСѓ, С‡С‚Рѕ РЅР° С‚РµРєСѓС‰РµРј СЃСЂРµР·Рµ Р»СѓС‡С€Рµ СЂР°Р·РґРµР»СЏСЋС‚ С‚РµСЂСЂРёС‚РѕСЂРёРё",
        },
        {
            "label": "РўРµСЂСЂРёС‚РѕСЂРёРё СЃ РєРѕСЂРѕС‚РєРѕР№ РёСЃС‚РѕСЂРёРµР№",
            "value": low_support_display,
            "meta": f"Р”Р»СЏ С‚РµСЂСЂРёС‚РѕСЂРёР№ СЃ РІвЂ°В¤{LOW_SUPPORT_TERRITORY_THRESHOLD} РїРѕР¶Р°СЂР°РјРё Р·РЅР°С‡РµРЅРёСЏ СЃРіР»Р°Р¶РµРЅС‹, С‡С‚РѕР±С‹ СѓР±СЂР°С‚СЊ С€СѓРј",
        },
        {
            "label": "РќР°СЃРєРѕР»СЊРєРѕ 2D-РєР°СЂС‚Р° РѕС‚СЂР°Р¶Р°РµС‚ РєР°СЂС‚РёРЅСѓ",
            "value": _format_percent(explained_variance or 0.0),
            "meta": "РЎРєРѕР»СЊРєРѕ РѕР±С‰РµР№ РєР°СЂС‚РёРЅС‹ СЃРѕС…СЂР°РЅСЏРµС‚СЃСЏ, РєРѕРіРґР° РґР°РЅРЅС‹Рµ СЃРІРѕРґРёРј Рє РїР»РѕСЃРєРѕР№ РєР°СЂС‚Рµ",
        },
    ]


def _build_clustering_quality_assessment(
    clustering: ClusterMetrics,
    method_comparison: Sequence[ClusterMethod],
    cluster_count: int,
    selected_features: Sequence[str],
    diagnostics: QualityDiagnostics | None = None,
    support_summary: SupportSummary | None = None,
    feature_selection_report: FeatureSelectionReport | None = None,
    requested_cluster_count: int | None = None,
    resolved_requested_cluster_count: int | None = None,
    cluster_count_is_explicit: bool = False,
    cluster_count_guidance: ClusterCountGuidance | None = None,
) -> ClusteringQualityAssessment:
    if clustering.get("silhouette") is None:
        payload = _empty_clustering_quality_assessment()
        payload["dissertation_points"] = ["Р’ С‚РµРєСѓС‰РµРј СЃСЂРµР·Рµ РєР»Р°СЃС‚РµСЂРёР·Р°С†РёСЏ РїРѕСЃС‚СЂРѕРµРЅР°, РЅРѕ РІРЅСѓС‚СЂРµРЅРЅРёС… РјРµС‚СЂРёРє РїРѕРєР° РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР»СЏ СѓСЃС‚РѕР№С‡РёРІРѕР№ РёРЅС‚РµСЂРїСЂРµС‚Р°С†РёРё РєР°С‡РµСЃС‚РІР°."]
        return payload

    low_support_share = float((support_summary or {}).get("low_support_share") or 0.0)
    low_support_display = _format_percent(low_support_share)
    resample_share_label = f"{int(round(STABILITY_RESAMPLE_RATIO * 100.0))}%"
    quality_context = _resolve_quality_configuration_context(
        method_comparison=method_comparison,
        diagnostics=diagnostics,
        cluster_count=cluster_count,
    )
    recommended_k = quality_context["recommended_k"]
    best_silhouette_k = quality_context["best_silhouette_k"]
    cluster_count_guidance = cluster_count_guidance or _build_cluster_count_guidance(
        requested_cluster_count=requested_cluster_count or cluster_count,
        current_cluster_count=cluster_count,
        diagnostics=diagnostics,
        adjusted_requested_cluster_count=resolved_requested_cluster_count,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    selected_method = quality_context["selected_method"]
    working_configuration = quality_context["working_configuration"]
    effective_recommended_configuration = quality_context["effective_recommended_configuration"]
    recommended_method = quality_context["recommended_method"]
    working_config_label = quality_context["working_config_label"]
    recommended_config_label = quality_context["recommended_config_label"]

    note_context = _build_quality_note_context(
        clustering=clustering,
        selected_method=selected_method,
        working_configuration=working_configuration,
        effective_recommended_configuration=effective_recommended_configuration,
        recommended_method=recommended_method,
        cluster_count=cluster_count,
        recommended_k=recommended_k,
        method_comparison=method_comparison,
        feature_selection_report=feature_selection_report,
        resample_share_label=resample_share_label,
        cluster_count_is_explicit=cluster_count_is_explicit,
    )
    segmentation_summary = note_context["segmentation_summary"]
    label_context = note_context["label_context"]
    mode_label = label_context["mode_label"]
    mode_note = label_context["mode_note"]
    weighting_label = label_context["weighting_label"]
    weighting_note = label_context["weighting_note"]
    weighting_meta = label_context["weighting_meta"]
    comparison_rows = _build_quality_method_comparison_rows(method_comparison)
    dissertation_points = _build_quality_dissertation_points(
        segmentation_note=segmentation_summary["note"],
        method_note=note_context["method_note"],
        cluster_count_guidance=cluster_count_guidance,
        recommended_config_label=recommended_config_label,
        working_config_label=working_config_label,
        recommended_k=recommended_k,
        best_silhouette_k=best_silhouette_k,
        stability_note=note_context["stability_note"],
        low_support_display=low_support_display,
        selected_features=selected_features,
        comparison_scope_note=note_context["comparison_scope_note"],
        cluster_shape_note=note_context["cluster_shape_note"],
        weighting_note=weighting_note,
        mode_note=mode_note,
        ablation_note=note_context["ablation_note"],
    )

    return {
        "ready": True,
        "title": "РћС†РµРЅРєР° РєР°С‡РµСЃС‚РІР° РєР»Р°СЃС‚РµСЂРёР·Р°С†РёРё",
        "subtitle": "РќРёР¶Рµ РїРѕРєР°Р·Р°РЅРѕ, РЅР°СЃРєРѕР»СЊРєРѕ РіСЂСѓРїРїС‹ РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ СЂР°Р·Р»РёС‡Р°СЋС‚СЃСЏ, РЅР°СЃРєРѕР»СЊРєРѕ СЂРµР·СѓР»СЊС‚Р°С‚ СѓСЃС‚РѕР№С‡РёРІ РїСЂРё РїРѕРІС‚РѕСЂРЅРѕРј СЂР°СЃС‡РµС‚Рµ Рё РєР°РєР°СЏ РЅР°СЃС‚СЂРѕР№РєР° РєР»Р°СЃС‚РµСЂРёР·Р°С†РёРё РІС‹РіР»СЏРґРёС‚ Р»СѓС‡С€РµР№.",
        "metric_cards": _build_quality_metric_cards(clustering, resample_share_label),
        "methodology_items": _build_quality_methodology_items(
            selected_features=selected_features,
            selected_method=selected_method,
            working_config_label=working_config_label,
            recommended_config_label=recommended_config_label,
            segmentation_label=segmentation_summary["label"],
            mode_label=mode_label,
            weighting_label=weighting_label,
            weighting_meta=weighting_meta,
            low_support_display=low_support_display,
            explained_variance=clustering.get("explained_variance"),
        ),
        "comparison_rows": comparison_rows,
        "dissertation_points": dissertation_points,
    }

__all__ = [
    '_format_configuration_label',
    '_empty_clustering_quality_assessment',
    '_build_configuration_recommendation_note',
    '_resolve_quality_configuration_context',
    '_build_feature_selection_quality_label_context',
    '_build_ablation_warning_note',
    '_format_quality_method_selection_label',
    '_build_quality_method_comparison_rows',
    '_build_quality_dissertation_points',
    '_build_quality_note_context',
    '_build_quality_metric_cards',
    '_build_quality_methodology_items',
    '_build_clustering_quality_assessment',
]

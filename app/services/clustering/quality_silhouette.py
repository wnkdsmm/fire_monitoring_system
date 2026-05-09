from __future__ import annotations

from typing import Any, Sequence

from config.constants import LOW_SUPPORT_TERRITORY_THRESHOLD, STABILITY_RESAMPLE_RATIO
from .count_guidance import _build_cluster_count_guidance
from .quality_cohesion import (
    _build_cluster_shape_note,


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

def _build_kmeans_description(weighting_strategy: str) -> str:
    from config.constants import WEIGHTING_STRATEGY_INCIDENT_LOG

    if weighting_strategy == WEIGHTING_STRATEGY_INCIDENT_LOG:
        return (
            "KMeans разделяет территории на k непересекающихся групп, "
            "итеративно перемещая центры до минимизации внутрикластерного разброса. "
            "Территории с длинной историей пожаров влияют на положение центров сильнее — "
            "это сглаживает эффект редких случаев в малонаселённых точках."
        )
    return (
        "KMeans разделяет территории на k непересекающихся групп, "
        "итеративно перемещая центры до минимизации внутрикластерного разброса. "
        "Все территории влияют на центры кластеров одинаково, "
        "независимо от числа пожаров в истории."
    )

def _format_configuration_label(configuration: ClusterMethod | None) -> str:
    if not configuration:
        return "—"
    method_label = str(configuration.get("method_label") or "Метод")
    cluster_count = configuration.get("cluster_count")
    if cluster_count:
        return f"{method_label}, k={_format_integer(cluster_count)}"
    return method_label


def _empty_clustering_quality_assessment() -> ClusteringQualityAssessment:
    return {
        "ready": False,
        "title": "Оценка качества кластеризации",
        "subtitle": "После расчета здесь появится понятная сводка: насколько группы различаются, насколько результат устойчив и какая настройка выглядит лучшей.",
        "metric_cards": [],
        "methodology_items": [],
        "comparison_rows": [],
        "quality_notes": ["Пока недостаточно данных для расчета метрик качества кластеризации."],
    }


def _resolve_quality_configuration_context(
    *,
    diagnostics: QualityDiagnostics | None,
    cluster_count: int,
) -> QualityConfigurationContext:
    diagnostics = diagnostics or {}
    recommended_configuration = dict(diagnostics.get("best_configuration") or {})
    recommended_k = int(recommended_configuration.get("cluster_count") or diagnostics.get("best_quality_k") or cluster_count)
    return {
        "recommended_k": recommended_k,
        "best_silhouette_k": diagnostics.get("best_silhouette_k"),
    }


def _build_feature_selection_quality_label_context(
    feature_selection_report: FeatureSelectionReport | None,
) -> QualityLabelContext:
    report = feature_selection_report or {}
    return {
        "mode_label": str(report.get("volume_role_label") or "Профиль территории"),
        "mode_note": str(report.get("volume_note") or ""),
        "weighting_label": str(report.get("weighting_label") or "Равный вес территорий"),
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
        f"В пробном сравнении признаков колонка '{worst_feature['feature']}' не вошла в итоговый набор, "
        "потому что с ней кластеры разделялись хуже."
    )


def _format_quality_method_selection_label(row: ClusterMethod) -> str:
    if row.get("is_selected") and row.get("is_recommended"):
        return "Рабочий и лучший на текущем k"
    if row.get("is_selected"):
        return "Рабочий вывод"
    if row.get("is_recommended"):
        return "Лучше на текущем k"
    return "Сравнение"


def _build_quality_method_comparison_rows(
    method_comparison: Sequence[ClusterMethod],
) -> list[MethodComparisonRow]:
    return [
        {
            "method_label": row.get("method_label", "Метод"),
            "selection_label": _format_quality_method_selection_label(row),
            "silhouette_display": _format_number(row.get("silhouette"), 3),
            "davies_display": _format_number(row.get("davies_bouldin"), 3),
            "calinski_display": _format_number(row.get("calinski_harabasz"), 1),
            "balance_display": _format_percent(row.get("cluster_balance_ratio") or 0.0),
        }
        for row in method_comparison
    ]


def _build_quality_notes(
    *,
    segmentation_note: str,
    cluster_count_guidance: ClusterCountGuidance,
    recommended_k: int | None,
    best_silhouette_k: Any,
    stability_note: str,
    low_support_display: str,
    cluster_shape_note: str,
    weighting_note: str,
    mode_note: str,
    ablation_note: str,
    kmeans_description: str,
) -> list[str]:
    quality_notes = [
        segmentation_note,
        str(cluster_count_guidance.get("quality_note") or ""),
        (
            f"По чёткости границ лучший результат отдельно даёт k={_format_integer(best_silhouette_k)}, "
            "но итоговое число групп всё равно выбирается вместе с проверкой баланса размеров."
            if recommended_k and best_silhouette_k and recommended_k != best_silhouette_k
            else "Основные показатели качества не спорят между собой по выбору числа групп."
        ),
        stability_note,
        (
            f"У {low_support_display} территорий пожаров немного, поэтому их долевые показатели слегка "
            "подтянуты к общему уровню, чтобы единичные случаи не искажали разбиение."
        ),
    ]
    if cluster_shape_note:
        quality_notes.append(cluster_shape_note)
    if weighting_note:
        quality_notes.append(weighting_note)
    if mode_note:
        quality_notes.append(mode_note)
    if ablation_note:
        quality_notes.append(ablation_note)
    if kmeans_description:
        quality_notes.append(kmeans_description)
    return [item for item in quality_notes if str(item).strip()]

def _build_quality_note_context(
    *,
    clustering: ClusterMetrics,
    recommended_method: ClusterMethod,
    cluster_count: int,
    recommended_k: int | None,
    feature_selection_report: FeatureSelectionReport | None,
    resample_share_label: str,
) -> QualityNoteContext:
    segmentation_summary = _summarize_segmentation_strength(
        clustering,
        recommended_method=recommended_method,
        cluster_count=cluster_count,
        recommended_k=recommended_k,
    )
    label_context = _build_feature_selection_quality_label_context(feature_selection_report)
    return {
        "segmentation_summary": segmentation_summary,
        "stability_note": _build_stability_note(clustering, resample_share_label),
        "cluster_shape_note": _build_cluster_shape_note(clustering),
        "label_context": label_context,
        "ablation_note": _build_ablation_warning_note(label_context["ablation_rows"]),
    }

def _build_quality_metric_cards(clustering: ClusterMetrics, resample_share_label: str) -> list[QualityScore]:
    return [
        {
            "label": "Насколько кластеры отделены",
            "value": _format_number(clustering.get("silhouette"), 3),
            "meta": "Чем выше значение, тем заметнее границы между группами",
        },
        {
            "label": "Насколько кластеры смешиваются",
            "value": _format_number(clustering.get("davies_bouldin"), 3),
            "meta": "Чем ниже значение, тем меньше соседние группы заходят друг в друга",
        },
        {
            "label": "Насколько группы собраны плотно",
            "value": _format_number(clustering.get("calinski_harabasz"), 1),
            "meta": "Чем выше значение, тем собраннее территории внутри своих групп",
        },
        {
            "label": "Насколько группы равномерны",
            "value": _format_percent(clustering.get("cluster_balance_ratio") or 0.0),
            "meta": (
                f"Размер самой маленькой и самой большой группы: "
                f"{_format_integer(clustering.get('smallest_cluster_size'))} / "
                f"{_format_integer(clustering.get('largest_cluster_size'))}"
            ),
        },
        {
            "label": "Насколько результат повторяется",
            "value": _format_number(clustering.get("stability_ari"), 3),
            "meta": f"Проверено на повторных {resample_share_label}-подвыборках",
        },
    ]


def _build_quality_methodology_items(
    *,
    selected_features: Sequence[str],
    segmentation_label: str,
    mode_label: str,
    weighting_label: str,
    weighting_meta: str,
    low_support_display: str,
    explained_variance: Any,
) -> list[QualityScore]:
    return [
        {
            "label": "Метод кластеризации",
            "value": "KMeans",
            "meta": (
                "Разбивает территории на группы, минимизируя разброс внутри каждой. "
                + (weighting_meta or "Все территории влияют на центры кластеров одинаково.")
            ),
        },
        {
            "label": "Насколько кластеры различимы",
            "value": segmentation_label,
            "meta": "Итоговая оценка по разделению групп, устойчивости и их размерам",
        },
        {
            "label": "Что именно кластеризуем",
            "value": mode_label,
            "meta": "Какой профиль территории сравнивается по умолчанию",
        },
        {
            "label": "Весы территорий",
            "value": weighting_label,
            "meta": weighting_meta or "Показывает, влияет ли число пожаров на положение территории в кластере",
        },
        {
            "label": "Сколько признаков вошло в расчёт",
            "value": _format_integer(len(selected_features)),
            "meta": "Отобраны потому, что на текущем срезе лучше разделяют территории",
        },
        {
            "label": "Территории с короткой историей",
            "value": low_support_display,
            "meta": f"Для территорий с ≤{LOW_SUPPORT_TERRITORY_THRESHOLD} пожарами значения сглажены, чтобы убрать шум",
        },
        {
            "label": "Насколько 2D-карта отражает картину",
            "value": _format_percent(explained_variance or 0.0),
            "meta": "Сколько общей картины сохраняется, когда данные сводим к плоской карте",
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
        payload["quality_notes"] = ["В текущем срезе кластеризация построена, но внутренних метрик пока недостаточно для устойчивой интерпретации качества."]
        return payload

    low_support_share = float((support_summary or {}).get("low_support_share") or 0.0)
    low_support_display = _format_percent(low_support_share)
    resample_share_label = f"{int(round(STABILITY_RESAMPLE_RATIO * 100.0))}%"
    quality_context = _resolve_quality_configuration_context(
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


    recommended_method = method_comparison[0] if method_comparison else {
        "method_key": "kmeans",
        "method_label": "KMeans",
        "algorithm_key": "kmeans",
    }



    note_context = _build_quality_note_context(
        clustering=clustering,
        recommended_method=recommended_method,
        cluster_count=cluster_count,
        recommended_k=recommended_k,
        feature_selection_report=feature_selection_report,
        resample_share_label=resample_share_label,
    )
    segmentation_summary = note_context["segmentation_summary"]
    label_context = note_context["label_context"]
    mode_label = label_context["mode_label"]
    mode_note = label_context["mode_note"]
    weighting_label = label_context["weighting_label"]
    weighting_note = label_context["weighting_note"]
    weighting_meta = label_context["weighting_meta"]
    comparison_rows = _build_quality_method_comparison_rows(method_comparison)
    quality_notes = _build_quality_notes(
        segmentation_note=segmentation_summary["note"],
        cluster_count_guidance=cluster_count_guidance,
        recommended_k=recommended_k,
        best_silhouette_k=best_silhouette_k,
        stability_note=note_context["stability_note"],
        low_support_display=low_support_display,
        cluster_shape_note=note_context["cluster_shape_note"],
        weighting_note=weighting_note,
        mode_note=mode_note,
        ablation_note=note_context["ablation_note"],
        kmeans_description=_build_kmeans_description(
            weighting_strategy=str(
                (feature_selection_report or {}).get("weighting_strategy") or ""
            )
        ),
    )
    return {
        "ready": True,
        "title": "Оценка качества кластеризации",
        "subtitle": "Ниже показано, насколько группы действительно различаются, насколько результат устойчив при повторном расчете и какая настройка кластеризации выглядит лучшей.",
        "metric_cards": _build_quality_metric_cards(clustering, resample_share_label),
        "methodology_items": _build_quality_methodology_items(

            selected_features=selected_features,
            segmentation_label=segmentation_summary["label"],
            mode_label=mode_label,
            weighting_label=weighting_label,
            weighting_meta=weighting_meta,
            low_support_display=low_support_display,
            explained_variance=clustering.get("explained_variance"),
        ),
        "comparison_rows": comparison_rows,
        "quality_notes": quality_notes,
    }

__all__ = [
    '_format_configuration_label',
    '_empty_clustering_quality_assessment',
    '_resolve_quality_configuration_context',
    '_build_feature_selection_quality_label_context',
    '_build_ablation_warning_note',
    '_format_quality_method_selection_label',
    '_build_quality_method_comparison_rows',
    '_build_quality_notes',
    '_build_quality_note_context',
    '_build_quality_metric_cards',
    '_build_quality_methodology_items',
    '_build_clustering_quality_assessment',
]










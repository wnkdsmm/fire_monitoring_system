from __future__ import annotations

import math

from config.constants import (
    CLUSTER_BALANCE_RATIO_STRONG_THRESHOLD,
    CLUSTER_BALANCE_RATIO_MIN_THRESHOLD,
    CLUSTER_DAVIES_BOULDIN_GOOD_THRESHOLD,
    CLUSTER_DAVIES_BOULDIN_STRONG_THRESHOLD,
    CLUSTER_SHAPE_BALANCE_WARNING_THRESHOLD,
    CLUSTER_SILHOUETTE_GOOD_THRESHOLD,
    CLUSTER_SILHOUETTE_STRONG_THRESHOLD,
    CLUSTER_STABILITY_ARI_GOOD_THRESHOLD,
    CLUSTER_STABILITY_ARI_STRONG_THRESHOLD,
)

from .types import ClusterLabel, ClusterMethod, ClusterMetrics, ClusteringMethodRow


def compute_method_algorithm_key(method_row: ClusterMethod | None) -> str:
    if not method_row:
        return ""
    return str(method_row.get("algorithm_key") or method_row.get("method_key") or "")


def compute_segmentation_strength(
    clustering: ClusterMetrics,
    selected_method: ClusterMethod | None = None,
    recommended_method: ClusterMethod | None = None,
    cluster_count: int | None = None,
    recommended_k: int | None = None,
) -> ClusterLabel:
    silhouette = float(clustering.get("silhouette") or 0.0)
    davies_bouldin = float(clustering.get("davies_bouldin") or 0.0)
    balance_ratio = float(clustering.get("cluster_balance_ratio") or 0.0)
    stability_ari = float(clustering.get("stability_ari") or 0.0)
    initialization_ari = float(clustering.get("initialization_ari") or 0.0)
    has_microclusters = bool(clustering.get("has_microclusters"))
    selected_algorithm_key = compute_method_algorithm_key(selected_method)
    recommended_algorithm_key = compute_method_algorithm_key(recommended_method)
    algorithm_mismatch = bool(selected_method and recommended_method) and selected_algorithm_key != recommended_algorithm_key
    configuration_mismatch = bool(selected_method and recommended_method) and (
        (selected_method or {}).get("method_key") != (recommended_method or {}).get("method_key")
    )
    k_mismatch = bool(recommended_k and cluster_count) and int(recommended_k) != int(cluster_count)
    stability_gap = initialization_ari - stability_ari if initialization_ari else 0.0
    requires_caution = configuration_mismatch or k_mismatch or stability_gap >= CLUSTER_SHAPE_BALANCE_WARNING_THRESHOLD

    if (
        not has_microclusters
        and silhouette >= CLUSTER_SILHOUETTE_STRONG_THRESHOLD
        and davies_bouldin <= CLUSTER_DAVIES_BOULDIN_STRONG_THRESHOLD
        and stability_ari >= CLUSTER_STABILITY_ARI_STRONG_THRESHOLD
        and balance_ratio >= CLUSTER_BALANCE_RATIO_STRONG_THRESHOLD
        and not requires_caution
    ):
        return {
            "label": "Сильная",
            "note": "Сегментация выглядит сильной: метрики согласованы между собой, кластеры заметно отделяются и в целом воспроизводятся на повторных подвыборках.",
        }
    if (
        not has_microclusters
        and silhouette >= CLUSTER_SILHOUETTE_GOOD_THRESHOLD
        and davies_bouldin <= CLUSTER_DAVIES_BOULDIN_GOOD_THRESHOLD
        and stability_ari >= CLUSTER_STABILITY_ARI_GOOD_THRESHOLD
        and balance_ratio >= CLUSTER_BALANCE_RATIO_MIN_THRESHOLD
    ):
        caution_suffix = ""
        if algorithm_mismatch:
            caution_suffix = " При этом итог лучше трактовать осторожнее: для текущего среза уже виден более убедительный альтернативный метод."
        elif configuration_mismatch:
            caution_suffix = " При этом итог лучше трактовать осторожнее: на том же наборе признаков более убедительно выглядит другая конфигурация весов или параметров."
        elif k_mismatch:
            caution_suffix = " При этом итог лучше трактовать осторожнее: рабочее число кластеров не совпадает с рекомендацией по совокупности метрик."
        elif stability_gap >= CLUSTER_SHAPE_BALANCE_WARNING_THRESHOLD:
            caution_suffix = " При этом итог лучше трактовать осторожнее: устойчивость на одном и том же датасете заметно выше, чем на повторных подвыборках."
        return {
            "label": "Умеренная",
            "note": (
                "Сегментация выглядит умеренной: типология уже читается, но часть границ между кластерами остаётся чувствительной к составу данных или к балансу размеров групп."
                f"{caution_suffix}"
            ),
        }
    return {
        "label": "Слабая",
        "note": "Сегментация выглядит слабой: либо метрики между собой не согласованы, либо разбиение слишком чувствительно к составу выборки, либо его качество проседает из-за микрокластеров и дисбаланса.",
    }


def compute_diagnostics_row_sort_key(result: ClusteringMethodRow) -> tuple[float, float, float, float, float]:
    davies_bouldin = result.get("davies_bouldin")
    davies_value = float("inf") if davies_bouldin is None else float(davies_bouldin)
    return (
        float(result.get("quality_score", float("-inf"))),
        float(result.get("silhouette", float("-inf"))),
        -float(davies_value if math.isfinite(davies_value) else 1e9),
        float(result.get("cluster_balance_ratio", 0.0)),
        -float(result.get("shape_penalty", 0.0)),
    )

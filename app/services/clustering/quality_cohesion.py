from __future__ import annotations


from config.constants import (
    CLUSTER_BALANCE_RATIO_CRITICAL_THRESHOLD,
    CLUSTER_SHAPE_BALANCE_WARNING_THRESHOLD,
    CLUSTER_STABILITY_ARI_DIVERGENCE_THRESHOLD,
)
from .quality_assessment import (
    compute_method_algorithm_key,
    compute_segmentation_strength,
)
from .types import ClusterLabel, ClusterMethod, ClusterMetrics
from app.services.shared.formatting import (
    format_integer as _format_integer,
    format_number as _format_number,
    format_percent as _format_percent,
)


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
        return "Оценить устойчивость на повторных подвыборках не удалось: в текущем срезе слишком мало территорий для надёжного сравнения пересэмплов."
    if initialization_ari is None:
        return (
            f"Проверка на повторных {resample_share_label}-подвыборках дала "
            f"{_format_number(stability_ari, 3)}: так видно, насколько результат повторяется не только на тех же данных."
        )

    gap = float(initialization_ari) - float(stability_ari)
    if gap >= CLUSTER_STABILITY_ARI_DIVERGENCE_THRESHOLD:
        return (
            f"На одних и тех же данных разбиение почти не меняется ({_format_number(initialization_ari, 3)}), "
            f"но на повторных {resample_share_label}-подвыборках устойчивость заметно ниже "
            f"({_format_number(stability_ari, 3)}), поэтому результат чувствителен к составу выборки. "
            "Рекомендуется проверять выводы по центрам кластеров, а не по конкретным территориям на границах."
        )
    return (
        f"На повторных {resample_share_label}-подвыборках устойчивость составляет "
        f"{_format_number(stability_ari, 3)}; это близко к проверке на тех же данных "
        f"({_format_number(initialization_ari, 3)})."
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
            f"Есть микрокластеры: самый маленький кластер содержит {_format_integer(smallest_cluster_size)} территорий при пороге предупреждения {_format_integer(microcluster_threshold)}, "
            "поэтому часть сегментации может держаться на очень малой группе наблюдений. "
            "Рекомендуется уменьшить число кластеров или проверить, не образовался ли этот кластер из-за одного нетипичного населённого пункта."
        )
    if balance_ratio < CLUSTER_BALANCE_RATIO_CRITICAL_THRESHOLD:
        return (
            f"Кластеры заметно несбалансированы: min/max = {_format_integer(smallest_cluster_size)} / {_format_integer(largest_cluster_size)} "
            f"({_format_percent(balance_ratio)}), поэтому результат стоит трактовать осторожнее. "
            "При интерпретации ориентируйтесь на удельные показатели (доли), а не на абсолютный размер групп."
        )
    if balance_ratio < CLUSTER_SHAPE_BALANCE_WARNING_THRESHOLD:
        return (
            f"Кластеры умеренно несбалансированы: min/max = {_format_integer(smallest_cluster_size)} / {_format_integer(largest_cluster_size)} "
            f"({_format_percent(balance_ratio)})."
        )
    return ""


__all__ = [
    "_summarize_segmentation_strength",
    "_build_stability_note",
    "_resolve_method_algorithm_key",
    "_build_cluster_shape_note",
    "compute_method_algorithm_key",
    "compute_segmentation_strength",
]

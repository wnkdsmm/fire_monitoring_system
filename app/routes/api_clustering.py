from __future__ import annotations

from fastapi import APIRouter, Body, Request

from app.services.clustering.core import get_clustering_data

from .api_common import (
    coerce_string_list,
    job_status_response,
    run_analytics_request,
    run_session_analytics_request,
)

router = APIRouter()

_INVALID_CLUSTERING_MESSAGE = "Некорректные параметры кластеризации."
_FAILED_CLUSTERING_MESSAGE = (
    "Не удалось собрать "
    "clustering-данные. Попробуйте "
    "повторить запрос."
)
_INVALID_CLUSTERING_JOB_MESSAGE = (
    "Некорректные параметры "
    "для фоновой clustering-задачи."
)
_FAILED_CLUSTERING_JOB_MESSAGE = (
    "Не удалось запустить "
    "фоновую clustering-задачу. "
    "Попробуйте повторить запрос."
)


def _build_clustering_api_payload(**kwargs):
    payload = get_clustering_data(**kwargs)
    payload.setdefault("pca_projection", {"points": [], "explained_variance": [0.0, 0.0]})  # New key retained in API JSON for downstream thesis export.
    return payload


def start_clustering_job(**kwargs):
    from app.services.clustering.jobs import start_clustering_job as _start_clustering_job

    return _start_clustering_job(**kwargs)


def get_clustering_job_status(**kwargs):
    from app.services.clustering.jobs import get_clustering_job_status as _get_clustering_job_status

    return _get_clustering_job_status(**kwargs)

@router.get("/api/clustering-data")
def clustering_data_endpoint(
    request: Request,
    table_name: str = "",
    table_names: list[str] | None = None,
    cluster_count: str = "4",
    sampling_strategy: str = "stratified",
    feature_columns: list[str] | None = None,
):
    return run_analytics_request(
        lambda: _build_clustering_api_payload(
            table_name=table_name,
            table_names=table_names or [],
            cluster_count=cluster_count,
            sampling_strategy=sampling_strategy,
            feature_columns=feature_columns or [],
            cluster_count_is_explicit="cluster_count" in request.query_params,
        ),
        invalid_code="clustering_invalid_request",
        invalid_message=_INVALID_CLUSTERING_MESSAGE,
        failed_code="clustering_failed",
        failed_message=_FAILED_CLUSTERING_MESSAGE,
    )

@router.post("/api/clustering-jobs")
def start_clustering_job_endpoint(request: Request, payload: dict = Body(...)):
    return run_session_analytics_request(
        request,
        lambda session_id: start_clustering_job(
            session_id=session_id,
            table_name=str(payload.get("table_name") or ""),
            table_names=coerce_string_list(payload.get("table_names")),
            cluster_count=str(payload.get("cluster_count") or "4"),
            sampling_strategy=str(payload.get("sampling_strategy") or "stratified"),
            feature_columns=coerce_string_list(payload.get("feature_columns")),
            cluster_count_is_explicit="cluster_count" in payload,
        ),
        invalid_code="clustering_job_invalid_request",
        invalid_message=_INVALID_CLUSTERING_JOB_MESSAGE,
        failed_code="clustering_job_failed",
        failed_message=_FAILED_CLUSTERING_JOB_MESSAGE,
    )

@router.get("/api/clustering-jobs/{job_id}")
def clustering_job_status_endpoint(request: Request, job_id: str):
    return job_status_response(request, job_id, get_clustering_job_status)

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.routes.api_common import run_session_json_action
from app.routes.page_common import asset_versions, render_template_page

from .service import (
    decode_and_import_uploaded_stat_file,
    decode_uploaded_stat_file,
    run_rename_headers_script,
    run_split_xlsx_by_year_script,
)

page_router = APIRouter()
api_router = APIRouter()


@page_router.get("/statistics-1992-2020", response_class=HTMLResponse)
def statistics19922020_page(request: Request):
    return render_template_page(
        request,
        "statistics19922020/index.html",
        **asset_versions(
            statistics19922020_css_version="css/statistics19922020/statistics19922020.css",
            statistics19922020_js_version="js/statistics19922020/statistics19922020.js",
        ),
    )


@api_router.post("/statistics19922020/decode")
def statistics19922020_decode_endpoint(
    request: Request,
    job_id: str | None = Form(None),
    base_dir: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: decode_uploaded_stat_file(
            session_id=session_id,
            job_id=job_id,
            base_dir=base_dir,
        ),
    )


@api_router.post("/statistics19922020/decode_import")
def statistics19922020_decode_import_endpoint(
    request: Request,
    job_id: str | None = Form(None),
    base_dir: str | None = Form(None),
    output_folder: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: decode_and_import_uploaded_stat_file(
            session_id=session_id,
            job_id=job_id,
            base_dir=base_dir,
            output_folder=output_folder,
        ),
    )


@api_router.post("/statistics19922020/run_rename_headers")
def statistics19922020_run_rename_headers_endpoint(
    request: Request,
    job_id: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: run_rename_headers_script(
            session_id=session_id,
            job_id=job_id,
        ),
    )


@api_router.post("/statistics19922020/run_split_xlsx_by_year")
def statistics19922020_run_split_xlsx_by_year_endpoint(
    request: Request,
    job_id: str | None = Form(None),
    output_dir: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: run_split_xlsx_by_year_script(
            session_id=session_id,
            job_id=job_id,
            output_dir=output_dir,
        ),
    )

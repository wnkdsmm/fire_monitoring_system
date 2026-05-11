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


def _normalize_decode_response(payload: dict, *, include_import: bool) -> dict:
    decoded_payload = payload if payload.get("decode") is None else payload.get("decode") or {}
    import_payload = payload.get("import")

    decode_status = str(decoded_payload.get("status") or "")
    root_status = str(payload.get("status") or "")
    is_error = root_status == "error" or decode_status == "error"

    files = {
        "input_file": str(decoded_payload.get("input_file") or ""),
        "decoded_file": str(decoded_payload.get("decoded_file") or ""),
        "report_file": str(decoded_payload.get("report_file") or ""),
    }
    if import_payload and isinstance(import_payload, dict):
        files["import_output_folder"] = str(import_payload.get("output_folder") or "")

    message = str(payload.get("message") or "")
    if not message:
        if is_error:
            message = str(decoded_payload.get("message") or "Ошибка обработки.")
        elif include_import:
            message = "Расшифровка и импорт завершены."
        else:
            message = "Расшифровка завершена."

    response = {
        "status": "error" if is_error else ("decoded_imported" if include_import else "decoded"),
        "job_id": str(payload.get("job_id") or decoded_payload.get("job_id") or ""),
        "message": message,
        "decode": decoded_payload if decoded_payload else payload,
        "files": files,
    }
    if include_import:
        response["import"] = import_payload if isinstance(import_payload, dict) else None
    return response


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
        lambda session_id: _normalize_decode_response(
            decode_uploaded_stat_file(
                session_id=session_id,
                job_id=job_id,
                base_dir=base_dir,
            ),
            include_import=False,
        ),
    )


def _decode_and_import_action(session_id: str, job_id: str | None, base_dir: str | None, output_folder: str | None) -> dict:
    return _normalize_decode_response(
        decode_and_import_uploaded_stat_file(
            session_id=session_id,
            job_id=job_id,
            base_dir=base_dir,
            output_folder=output_folder,
        ),
        include_import=True,
    )


@api_router.post("/statistics19922020/decode-and-import")
def statistics19922020_decode_and_import_endpoint(
    request: Request,
    job_id: str | None = Form(None),
    base_dir: str | None = Form(None),
    output_folder: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: _decode_and_import_action(session_id, job_id, base_dir, output_folder),
    )


@api_router.post("/statistics19922020/decode_import")
def statistics19922020_decode_import_alias_endpoint(
    request: Request,
    job_id: str | None = Form(None),
    base_dir: str | None = Form(None),
    output_folder: str | None = Form(None),
):
    return run_session_json_action(
        request,
        lambda session_id: _decode_and_import_action(session_id, job_id, base_dir, output_folder),
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

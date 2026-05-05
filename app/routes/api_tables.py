from __future__ import annotations

from fastapi import APIRouter, Body

from .api_common import json_action_response

router = APIRouter()

_FAILED_TABLE_PAGE_MESSAGE = "Не удалось загрузить страницу таблицы: {exc}"
_DELETED_TABLE_MESSAGE = "Таблица {table_name} удалена из базы данных."
_FAILED_DELETE_TABLE_MESSAGE = "Не удалось удалить таблицу: {exc}"
_TABLE_WORD_SINGLE = "таблица"
_TABLE_WORD_FEW = "таблицы"
_TABLE_WORD_MANY = "таблиц"
_DELETED_TABLES_MESSAGE = "Удалено {count} {table_word} из базы данных."
_FAILED_DELETE_TABLES_MESSAGE = "Не удалось удалить таблицы: {exc}"


def build_table_page_api_payload(**kwargs):
    from app.services.table_workflows import build_table_page_api_payload as _build_table_page_api_payload

    return _build_table_page_api_payload(**kwargs)


def delete_table(table_name: str):
    from app.table_operations import delete_table as _delete_table

    return _delete_table(table_name)


def delete_tables(table_names: list[str]):
    from app.table_operations import delete_tables as _delete_tables

    return _delete_tables(table_names)

@router.get("/api/tables/{table_name}/page")


def table_page_endpoint(table_name: str, page: int = 1, page_size: int = 100):
    return json_action_response(
        lambda: build_table_page_api_payload(table_name=table_name, page=page, page_size=page_size),
        on_value_error=lambda exc: (
            {
                "ok": False,
                "table_name": table_name,
                "message": str(exc),
            },
            400,
        ),
        on_exception=lambda exc: (
            {
                "ok": False,
                "table_name": table_name,
                "message": _FAILED_TABLE_PAGE_MESSAGE.format(exc=exc),
            },
            404,
        ),
    )

@router.delete("/api/tables/{table_name}")


def delete_table_endpoint(table_name: str):
    def delete_action():
        result = delete_table(table_name)
        return {
            "ok": True,
            "table_name": result["table_name"],
            "remaining_tables": result["remaining_tables"],
            "remaining_count": result["remaining_count"],
            "message": _DELETED_TABLE_MESSAGE.format(table_name=result["table_name"]),
        }

    return json_action_response(
        delete_action,
        on_value_error=lambda exc: (
            {
                "ok": False,
                "table_name": table_name,
                "message": str(exc),
            },
            404,
        ),
        on_exception=lambda exc: (
            {
                "ok": False,
                "table_name": table_name,
                "message": _FAILED_DELETE_TABLE_MESSAGE.format(exc=exc),
            },
            500,
        ),
    )

@router.post("/api/tables/delete")


def delete_tables_endpoint(payload: dict = Body(...)):
    table_names = [str(item).strip() for item in (payload.get("table_names") or []) if str(item).strip()]

    def delete_action():
        result = delete_tables(table_names)
        deleted_tables = result["deleted_tables"]
        deleted_count = len(deleted_tables)
        table_word = _TABLE_WORD_SINGLE if deleted_count == 1 else _TABLE_WORD_FEW if 2 <= deleted_count <= 4 else _TABLE_WORD_MANY
        return {
            "ok": True,
            "deleted_tables": deleted_tables,
            "remaining_tables": result["remaining_tables"],
            "remaining_count": result["remaining_count"],
            "message": _DELETED_TABLES_MESSAGE.format(count=deleted_count, table_word=table_word),
        }

    return json_action_response(
        delete_action,
        on_value_error=lambda exc: (
            {
                "ok": False,
                "table_names": table_names,
                "message": str(exc),
            },
            400,
        ),
        on_exception=lambda exc: (
            {
                "ok": False,
                "table_names": table_names,
                "message": _FAILED_DELETE_TABLES_MESSAGE.format(exc=exc),
            },
            500,
        ),
    )

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from config.db import engine

_CACHE_SCHEMA_VERSION = "v1_profiling_result"
_CACHE_DIR_NAME = ".pipeline_cache"
_CACHE_FILENAME = "profiling_results.json"


def _cache_file_path(output_folder: str) -> Path:
    cache_dir = Path(output_folder) / _CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / _CACHE_FILENAME


def _cache_key(table_name: str, thresholds: dict[str, float]) -> str:
    payload = {
        "table_name": str(table_name or ""),
        "thresholds": {
            "null_threshold": float(thresholds.get("null_threshold", 0.0)),
            "dominant_value_threshold": float(thresholds.get("dominant_value_threshold", 0.0)),
            "low_variance_threshold": float(thresholds.get("low_variance_threshold", 0.0)),
        },
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cache_document(output_folder: str) -> dict[str, Any]:
    cache_path = _cache_file_path(output_folder)
    if not cache_path.exists():
        return {"schema_version": _CACHE_SCHEMA_VERSION, "entries": {}}
    try:
        parsed = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": _CACHE_SCHEMA_VERSION, "entries": {}}
    if not isinstance(parsed, dict):
        return {"schema_version": _CACHE_SCHEMA_VERSION, "entries": {}}
    entries = parsed.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    if parsed.get("schema_version") != _CACHE_SCHEMA_VERSION:
        return {"schema_version": _CACHE_SCHEMA_VERSION, "entries": {}}
    return {"schema_version": _CACHE_SCHEMA_VERSION, "entries": entries}


def _save_cache_document(output_folder: str, document: dict[str, Any]) -> None:
    cache_path = _cache_file_path(output_folder)
    cache_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _table_signature(table_name: str) -> dict[str, Any] | None:
    query = text(
        """
        SELECT
            c.oid::text AS oid,
            c.relfilenode::text AS relfilenode,
            pg_relation_size(c.oid)::bigint AS relation_size,
            COALESCE(s.n_tup_ins, 0)::bigint AS stat_inserts,
            COALESCE(s.n_tup_upd, 0)::bigint AS stat_updates,
            COALESCE(s.n_tup_del, 0)::bigint AS stat_deletes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE c.relkind = 'r'
          AND n.nspname = current_schema()
          AND c.relname = :table_name
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"table_name": str(table_name)}).mappings().first()
    if row is None:
        return None
    return {
        "oid": str(row.get("oid") or ""),
        "relfilenode": str(row.get("relfilenode") or ""),
        "relation_size": int(row.get("relation_size") or 0),
        "stat_inserts": int(row.get("stat_inserts") or 0),
        "stat_updates": int(row.get("stat_updates") or 0),
        "stat_deletes": int(row.get("stat_deletes") or 0),
    }


def _table_exists(table_name: str) -> bool:
    query = text("SELECT to_regclass(current_schema() || '.' || :table_name) IS NOT NULL")
    with engine.connect() as conn:
        value = conn.execute(query, {"table_name": str(table_name)}).scalar()
    return bool(value)


def _files_exist(result_payload: dict[str, Any]) -> bool:
    files = result_payload.get("files")
    if not isinstance(files, dict):
        return False
    required_keys = ("profile_csv", "profile_xlsx", "clean_xlsx")
    for key in required_keys:
        file_path = str(files.get(key) or "").strip()
        if not file_path or not Path(file_path).exists():
            return False
    return True


def load_cached_profiling_result(
    *,
    table_name: str,
    output_folder: str,
    thresholds: dict[str, float],
) -> dict[str, Any] | None:
    document = _load_cache_document(output_folder)
    cache_entry = document["entries"].get(_cache_key(table_name, thresholds))
    if not isinstance(cache_entry, dict):
        return None

    cached_signature = cache_entry.get("table_signature")
    current_signature = _table_signature(table_name)
    if current_signature is None or cached_signature != current_signature:
        return None

    result_payload = cache_entry.get("result")
    if not isinstance(result_payload, dict):
        return None

    clean_table = str(result_payload.get("clean_table") or "").strip()
    if clean_table and not _table_exists(clean_table):
        return None
    if not _files_exist(result_payload):
        return None
    return result_payload


def save_profiling_result_cache(
    *,
    table_name: str,
    output_folder: str,
    thresholds: dict[str, float],
    result_payload: dict[str, Any],
) -> None:
    signature = _table_signature(table_name)
    if signature is None:
        return

    document = _load_cache_document(output_folder)
    document["entries"][_cache_key(table_name, thresholds)] = {
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "table_signature": signature,
        "result": result_payload,
    }
    _save_cache_document(output_folder, document)


def invalidate_profiling_result_cache(*, output_folder: str, table_name: str) -> None:
    document = _load_cache_document(output_folder)
    entries = document.get("entries")
    if not isinstance(entries, dict) or not entries:
        return
    table_name_str = str(table_name or "")
    keys_to_remove: list[str] = []
    for key, value in entries.items():
        if not isinstance(value, dict):
            continue
        cache_result = value.get("result")
        if isinstance(cache_result, dict) and str(cache_result.get("table_name") or "") == table_name_str:
            keys_to_remove.append(str(key))
    if not keys_to_remove:
        return
    for key in keys_to_remove:
        entries.pop(key, None)
    _save_cache_document(output_folder, document)


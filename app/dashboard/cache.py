from __future__ import annotations

"""Dashboard cache orchestration.

This module keeps dashboard-specific cache keys and invalidation logic on top of
generic primitives from ``app.cache``.
"""

import copy
import json
from typing import Any

from app.db_metadata import invalidate_db_metadata_cache
from app.cache import CopyingTtlCache
from app.table_catalog import get_clean_table_names

from .metadata import _collect_dashboard_metadata

_DASHBOARD_METADATA_CACHE = CopyingTtlCache[tuple[str, ...], dict[str, Any]](
    ttl_seconds=None,
    skip_freeze=True,
)
_DASHBOARD_CACHE = CopyingTtlCache[tuple[Any, ...], dict[str, Any]](
    ttl_seconds=None,
    skip_freeze=True,
)


def _current_dashboard_table_names() -> tuple[str, ...]:
    return tuple(sorted(get_clean_table_names(fallback_to_user=True)))


def _metadata_table_names(metadata: dict[str, Any] | None) -> tuple[str, ...]:
    if not metadata:
        return ()
    cached_signature = metadata.get("table_signature")
    if cached_signature:
        return tuple(str(table_name) for table_name in cached_signature)
    return tuple(sorted(table["name"] for table in metadata.get("tables", [])))


def _invalidate_dashboard_caches() -> None:
    invalidate_db_metadata_cache()
    _DASHBOARD_METADATA_CACHE.clear()
    _DASHBOARD_CACHE.clear()


def _collect_dashboard_metadata_cached() -> dict[str, Any]:
    current_table_names = _current_dashboard_table_names()
    cached_value = _DASHBOARD_METADATA_CACHE.get(current_table_names)
    if cached_value is not None:
        try:
            cached_metadata = json.loads(json.dumps(cached_value))
        except (TypeError, ValueError):
            cached_metadata = copy.deepcopy(cached_value)
        if _metadata_table_names(cached_metadata) == current_table_names:
            return cached_metadata

    metadata = _collect_dashboard_metadata(current_table_names)
    _DASHBOARD_METADATA_CACHE.clear()
    _DASHBOARD_CACHE.clear()
    try:
        _DASHBOARD_METADATA_CACHE.set(current_table_names, json.loads(json.dumps(metadata)))
    except (TypeError, ValueError):
        _DASHBOARD_METADATA_CACHE.set(current_table_names, copy.deepcopy(metadata))
    return metadata


def _get_dashboard_cache(cache_key: tuple[Any, ...]) -> dict[str, Any] | None:
    cached_value = _DASHBOARD_CACHE.get(cache_key)
    if cached_value is None:
        return None
    try:
        return json.loads(json.dumps(cached_value))
    except (TypeError, ValueError):
        return copy.deepcopy(cached_value)


def _set_dashboard_cache(cache_key: tuple[Any, ...], value: dict[str, Any]) -> None:
    try:
        _DASHBOARD_CACHE.set(cache_key, json.loads(json.dumps(value)))
    except (TypeError, ValueError):
        _DASHBOARD_CACHE.set(cache_key, copy.deepcopy(value))

__all__ = [
    "_collect_dashboard_metadata_cached",
    "_current_dashboard_table_names",
    "_get_dashboard_cache",
    "_invalidate_dashboard_caches",
    "_metadata_table_names",
    "_set_dashboard_cache",
]

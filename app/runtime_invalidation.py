from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from typing import Callable

_INVALIDATORS: tuple[tuple[str, str, str, str], ...] = (
    (
        "db_metadata",
        "app.db_metadata",
        "invalidate_db_metadata_cache",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° РјРµС‚Р°РґР°РЅРЅС‹С… Р‘Р”: {exc}",
    ),
    (
        "dashboard",
        "app.dashboard.cache",
        "_invalidate_dashboard_caches",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° РїР°РЅРµР»Рё: {exc}",
    ),
    (
        "ml_model",
        "app.services.ml_model.core",
        "clear_ml_model_cache",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° ML-Р±Р»РѕРєР°: {exc}",
    ),
    (
        "clustering",
        "app.services.clustering.core",
        "clear_clustering_cache",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° РєР»Р°СЃС‚РµСЂРёР·Р°С†РёРё: {exc}",
    ),
    (
        "access_points",
        "app.services.access_points.core",
        "clear_access_points_cache",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° РїСЂРѕР±Р»РµРјРЅС‹С… С‚РѕС‡РµРє: {exc}",
    ),
    (
        "fire_map",
        "app.services.fire_map_service",
        "clear_fire_map_cache",
        "РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РєСЌС€Р° РєР°СЂС‚С‹ РїРѕР¶Р°СЂРѕРІ: {exc}",
    ),
)


def _resolve_invalidator(module_name: str, attr_name: str) -> Callable[[], None]:
    module = import_module(module_name)
    return getattr(module, attr_name)


def invalidate_runtime_caches(
    on_warning: Callable[[str], None] | None = None,
    *,
    include_metadata: bool = True,
) -> None:
    def warn(message: str) -> None:
        if on_warning is not None:
            on_warning(message)

    for name, module_name, attr_name, error_template in _INVALIDATORS:
        if not include_metadata and name == "db_metadata":
            continue
        try:
            invalidator = _resolve_invalidator(module_name, attr_name)
            invalidator()
        except Exception as exc:
            warn(error_template.format(exc=exc))


def invalidate_service_caches(on_warning: Callable[[str], None] | None = None) -> None:
    invalidate_runtime_caches(on_warning=on_warning, include_metadata=False)


def invalidate_table_related_caches(
    table_name: str | None = None,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> None:
    db_metadata = import_module("app.db_metadata")
    db_metadata.invalidate_db_metadata_cache(table_name=table_name)
    invalidate_service_caches(on_warning=on_warning)


def warmup_runtime_caches(on_warning: Callable[[str], None] | None = None) -> None:
    def warn(message: str) -> None:
        if on_warning is not None:
            on_warning(message)

    try:
        db_metadata = import_module("app.db_metadata")
        table_names: list[str] = db_metadata.get_table_names_cached()
        if table_names:
            with ThreadPoolExecutor(max_workers=min(8, len(table_names))) as executor:
                futures = {
                    executor.submit(db_metadata.get_table_columns_cached, table_name): table_name
                    for table_name in table_names
                }
                for future in as_completed(futures):
                    table_name = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        warn(f"РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РїСЂРѕРіСЂРµРІРµ РєРѕР»РѕРЅРѕРє С‚Р°Р±Р»РёС†С‹ '{table_name}': {exc}")
    except Exception as exc:
        warn(f"РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РїСЂРѕРіСЂРµРІРµ РєСЌС€Р° РјРµС‚Р°РґР°РЅРЅС‹С… Р‘Р”: {exc}")

    try:
        dashboard_cache = import_module("app.dashboard.cache")
        dashboard_cache._collect_dashboard_metadata_cached()
    except Exception as exc:
        warn(f"РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РїСЂРѕРіСЂРµРІРµ РєСЌС€Р° РґР°С€Р±РѕСЂРґР°: {exc}")


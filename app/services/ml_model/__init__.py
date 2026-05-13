"""ML compare-series facade."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE_EXPORTS = {
    "core": ".core",
}

_ATTRIBUTE_EXPORTS = {
    "clear_ml_model_cache": (".core", "clear_ml_model_cache"),
    "get_ml_compare_series_data": (".core", "get_ml_compare_series_data"),
    "get_ml_model_shell_context": (".core", "get_ml_model_shell_context"),
}

__all__ = sorted([*_MODULE_EXPORTS.keys(), *_ATTRIBUTE_EXPORTS.keys()])


def _load(module_path: str) -> Any:
    return import_module(module_path, __name__)


def __getattr__(name: str) -> Any:
    module_path = _MODULE_EXPORTS.get(name)
    if module_path is not None:
        module = _load(module_path)
        globals()[name] = module
        return module

    attribute_target = _ATTRIBUTE_EXPORTS.get(name)
    if attribute_target is not None:
        target_module_path, attribute_name = attribute_target
        value = getattr(_load(target_module_path), attribute_name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(__all__))

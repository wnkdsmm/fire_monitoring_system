from __future__ import annotations

from typing import Any

from app.cache import CopyingLruCache, build_immutable_payload_lru_cache

from .ml_model_config_types import ML_TRAINING_ARTIFACT_CACHE_LIMIT, _CACHE_LIMIT


class MLModelCaches:
    def __init__(self, ml_cache: Any, artifact_cache: CopyingLruCache[Any, Any]) -> None:
        self.ml_cache = ml_cache
        self.artifact_cache = artifact_cache


def create_default_caches() -> MLModelCaches:
    return MLModelCaches(
        ml_cache=build_immutable_payload_lru_cache(max_size=_CACHE_LIMIT),
        artifact_cache=CopyingLruCache(max_size=ML_TRAINING_ARTIFACT_CACHE_LIMIT, skip_freeze=True),
    )

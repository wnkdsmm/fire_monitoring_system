from __future__ import annotations

import math
from typing import Any

import pandas as pd
from config.constants import (
    BASELINE_RECENT_WINDOW_DAYS,
    BASELINE_WEEKDAY_MIN_SAMPLES,
    BASELINE_WEEKDAY_TAIL,
)

from ..ml_model_config_types import BASELINE_RECENT_WEIGHT, BASELINE_WEEKDAY_WEIGHT
from ..training.forecast_bounds import _bound_probability


def _baseline_expected_count(train: pd.DataFrame, target_date: pd.Timestamp) -> float:
    recent_mean = float(train['count'].tail(BASELINE_RECENT_WINDOW_DAYS).mean()) if not train.empty else 0.0
    same_weekday = train.loc[train['weekday'] == int(target_date.weekday()), 'count'].tail(BASELINE_WEEKDAY_TAIL)
    if len(same_weekday) >= BASELINE_WEEKDAY_MIN_SAMPLES:
        return max(0.0, float(BASELINE_WEEKDAY_WEIGHT * same_weekday.mean() + BASELINE_RECENT_WEIGHT * recent_mean))
    return max(0.0, recent_mean)


def _baseline_event_probability(train: pd.DataFrame, target_date: pd.Timestamp) -> float | None:
    if train.empty:
        return None
    recent_rate = float(train['event'].tail(BASELINE_RECENT_WINDOW_DAYS).mean())
    same_weekday = train.loc[train['weekday'] == int(target_date.weekday()), 'event'].tail(BASELINE_WEEKDAY_TAIL)
    if len(same_weekday) >= BASELINE_WEEKDAY_MIN_SAMPLES:
        probability = BASELINE_WEEKDAY_WEIGHT * float(same_weekday.mean()) + BASELINE_RECENT_WEIGHT * recent_rate
    else:
        probability = recent_rate
    return _bound_probability(probability)


def _scenario_reference_forecast(
    train: pd.DataFrame,
    test: pd.DataFrame,
    temperature_stats: dict[str, Any] | None = None,
) -> tuple[float, float | None]:
    if train.empty:
        return 0.0, None
    target_date = pd.Timestamp(test['date'].iloc[0])
    fallback_count = _baseline_expected_count(train, target_date)
    return fallback_count, _bound_probability(1.0 - math.exp(-max(0.0, fallback_count)))

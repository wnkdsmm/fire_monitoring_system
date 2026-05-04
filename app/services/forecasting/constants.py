from __future__ import annotations

"""Shared constants for the forecasting data layer (column names, option lists, palette).

Scenario-forecast-specific constants have been removed. This module is kept
because it is imported by shared utilities used by the ML-model service.
"""

from app.domain.fire_columns import (
    CAUSE_COLUMN_CANDIDATES,
    DATE_COLUMN,
    DISTRICT_COLUMN_CANDIDATES,
    LATITUDE_COLUMN_CANDIDATES,
    LONGITUDE_COLUMN_CANDIDATES,
    OBJECT_CATEGORY_COLUMN,
    TEMPERATURE_COLUMN_CANDIDATES,
)
from app.domain.analytics_metadata import PLOTLY_PALETTE
from app.labels import FORECASTING_HISTORY_WINDOW_LABELS
from config.constants import FORECASTING_FORECAST_DAY_OPTIONS, FORECASTING_HISTORY_WINDOWS

FORECAST_DAY_OPTIONS: list[int] = list(FORECASTING_FORECAST_DAY_OPTIONS)

HISTORY_WINDOW_OPTIONS: list[dict[str, str]] = [
    {"value": value, "label": FORECASTING_HISTORY_WINDOW_LABELS.get(value, value)}
    for value in FORECASTING_HISTORY_WINDOWS
]

__all__ = [
    "CAUSE_COLUMN_CANDIDATES",
    "DATE_COLUMN",
    "DISTRICT_COLUMN_CANDIDATES",
    "FORECAST_DAY_OPTIONS",
    "HISTORY_WINDOW_OPTIONS",
    "LATITUDE_COLUMN_CANDIDATES",
    "LONGITUDE_COLUMN_CANDIDATES",
    "OBJECT_CATEGORY_COLUMN",
    "PLOTLY_PALETTE",
    "TEMPERATURE_COLUMN_CANDIDATES",
]

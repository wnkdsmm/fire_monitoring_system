from __future__ import annotations

__all__ = [
    "AREA_COLUMN",
    "CAUSE_COLUMNS",
    "DATE_COLUMN",
    "EXCLUDED_TABLE_PREFIXES",
    "IMPACT_METRIC_CONFIG",
    "MONTH_LABELS",
    "PLOTLY_PALETTE",
]

from app.domain.analytics_metadata import (
    EXCLUDED_TABLE_PREFIXES,
    IMPACT_METRIC_CONFIG,
    PLOTLY_PALETTE,
)
from app.domain.fire_columns import (
    AREA_COLUMN,
    CAUSE_COLUMNS,
    DATE_COLUMN,
)

DASHBOARD_MONTH_LABELS = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек",
}
FORECAST_MONTH_LABELS = dict(DASHBOARD_MONTH_LABELS)
FORECAST_WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

MONTH_LABELS = DASHBOARD_MONTH_LABELS

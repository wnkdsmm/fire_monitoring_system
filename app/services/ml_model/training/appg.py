from __future__ import annotations

from datetime import date, datetime
from typing import Any, TypedDict


class AppgRow(TypedDict, total=False):
    current_date: str
    current_value: float | None
    appg_date: str
    appg_value: float | None
    appg_delta_abs: float | None
    appg_delta_pct: float | None
    appg_available: bool


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 10:
            text = text[:10]
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_day_previous_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        # Leap-day fallback: 29-Feb -> 28-Feb in non-leap year.
        return value.replace(year=value.year - 1, month=2, day=28)


def compute_appg_series(
    target_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    *,
    current_date_key: str = "date",
    current_value_key: str = "forecast_value",
    history_date_key: str = "date",
    history_value_key: str = "count",
) -> list[AppgRow]:
    history_index: dict[str, float] = {}
    for item in history_rows:
        history_date = _coerce_date(item.get(history_date_key))
        history_value = _coerce_float(item.get(history_value_key))
        if history_date is None or history_value is None:
            continue
        history_index[history_date.isoformat()] = history_value

    result: list[AppgRow] = []
    for item in target_rows:
        current_date = _coerce_date(item.get(current_date_key))
        current_value = _coerce_float(item.get(current_value_key))
        if current_date is None:
            continue

        appg_date = _same_day_previous_year(current_date)
        appg_value = history_index.get(appg_date.isoformat())
        appg_available = appg_value is not None
        appg_delta_abs = None
        appg_delta_pct = None
        if appg_available and current_value is not None:
            appg_delta_abs = current_value - float(appg_value)
            if float(appg_value) != 0.0:
                appg_delta_pct = (current_value / float(appg_value) - 1.0) * 100.0

        result.append(
            {
                "current_date": current_date.isoformat(),
                "current_value": current_value,
                "appg_date": appg_date.isoformat(),
                "appg_value": appg_value if appg_available else None,
                "appg_delta_abs": appg_delta_abs,
                "appg_delta_pct": appg_delta_pct,
                "appg_available": appg_available,
            }
        )

    return result


__all__ = ["AppgRow", "compute_appg_series"]

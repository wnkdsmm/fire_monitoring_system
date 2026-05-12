from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, TypedDict


class CompareSeriesRow(TypedDict):
    day: int
    a_value: float | None
    b_value: float | None
    a_source: str
    b_source: str


class CompareSeriesSummary(TypedDict):
    fact_days: int
    ml_days: int


class CompareSeriesPayload(TypedDict):
    month: int
    year_a: int
    year_b: int
    rows: list[CompareSeriesRow]
    a_summary: CompareSeriesSummary
    b_summary: CompareSeriesSummary


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()[:10]
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


def build_compare_series(
    *,
    month: int,
    year_a: int,
    year_b: int,
    daily_history: list[dict[str, Any]],
    ml_month_provider: Callable[[int, int], dict[int, float | None]],
    history_date_key: str = "date",
    history_value_key: str = "count",
) -> CompareSeriesPayload:
    facts_by_key: dict[tuple[int, int, int], float] = {}
    for row in daily_history:
        row_date = _coerce_date(row.get(history_date_key))
        row_value = _coerce_float(row.get(history_value_key))
        if row_date is None or row_value is None:
            continue
        facts_by_key[(row_date.year, row_date.month, row_date.day)] = row_value

    max_days = 31
    ml_a = ml_month_provider(int(year_a), int(month))
    ml_b = ml_month_provider(int(year_b), int(month))

    rows: list[CompareSeriesRow] = []
    a_fact_days = 0
    a_ml_days = 0
    b_fact_days = 0
    b_ml_days = 0

    for day in range(1, max_days + 1):
        a_fact = facts_by_key.get((int(year_a), int(month), day))
        b_fact = facts_by_key.get((int(year_b), int(month), day))
        a_ml = _coerce_float(ml_a.get(day))
        b_ml = _coerce_float(ml_b.get(day))

        a_value = a_fact if a_fact is not None else a_ml
        b_value = b_fact if b_fact is not None else b_ml
        a_source = "fact" if a_fact is not None else "ml"
        b_source = "fact" if b_fact is not None else "ml"

        if a_value is not None:
            if a_source == "fact":
                a_fact_days += 1
            else:
                a_ml_days += 1
        if b_value is not None:
            if b_source == "fact":
                b_fact_days += 1
            else:
                b_ml_days += 1

        rows.append(
            {
                "day": day,
                "a_value": a_value,
                "b_value": b_value,
                "a_source": a_source,
                "b_source": b_source,
            }
        )

    return {
        "month": int(month),
        "year_a": int(year_a),
        "year_b": int(year_b),
        "rows": rows,
        "a_summary": {"fact_days": a_fact_days, "ml_days": a_ml_days},
        "b_summary": {"fact_days": b_fact_days, "ml_days": b_ml_days},
    }


__all__ = ["CompareSeriesPayload", "CompareSeriesRow", "build_compare_series"]

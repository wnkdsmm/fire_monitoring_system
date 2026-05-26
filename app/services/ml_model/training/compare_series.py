from __future__ import annotations

from calendar import monthrange
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
    treat_missing_as_zero: bool = True,
) -> CompareSeriesPayload:
    """Build day-by-day comparison series for two years of a target month.

    The SQL source (``GROUP BY fire_date``) only returns rows for days with at
    least one incident, so a true zero-fire day is indistinguishable from a
    truly absent day at the raw-data level. To recover the distinction we use
    ``daily_history`` itself as a coverage signal:

    * A month ``(year, month)`` is considered *covered* if it has at least one
      day in ``daily_history``.
    * The data window is bounded by ``[min_date, max_date]`` computed over the
      whole ``daily_history``. A day strictly before ``min_date`` or strictly
      after ``max_date`` is treated as "outside the observed window" — we do
      not know whether it had fires or not, so we still fall back to OLS.
    * Only when the month is covered AND the day falls inside
      ``[min_date, max_date]`` is an absent day interpreted as a true zero.

    This handles the case where data is exported mid-month (e.g. only the
    first 10 days of October were dumped): days 1..10 inside October are real
    zeros for absent rows, but days 11..31 stay as OLS imputations.

    Set ``treat_missing_as_zero=False`` to keep the legacy behaviour where any
    day missing from ``daily_history`` is filled by the OLS baseline.
    """
    facts_by_key: dict[tuple[int, int, int], float] = {}
    covered_months: set[tuple[int, int]] = set()
    min_observed_date: date | None = None
    max_observed_date: date | None = None
    for row in daily_history:
        row_date = _coerce_date(row.get(history_date_key))
        row_value = _coerce_float(row.get(history_value_key))
        if row_date is None or row_value is None:
            continue
        facts_by_key[(row_date.year, row_date.month, row_date.day)] = row_value
        covered_months.add((row_date.year, row_date.month))
        if min_observed_date is None or row_date < min_observed_date:
            min_observed_date = row_date
        if max_observed_date is None or row_date > max_observed_date:
            max_observed_date = row_date

    month_days_a = int(monthrange(int(year_a), int(month))[1])
    month_days_b = int(monthrange(int(year_b), int(month))[1])
    max_days = max(month_days_a, month_days_b)
    ml_a = ml_month_provider(int(year_a), int(month))
    ml_b = ml_month_provider(int(year_b), int(month))

    a_month_covered = treat_missing_as_zero and ((int(year_a), int(month)) in covered_months)
    b_month_covered = treat_missing_as_zero and ((int(year_b), int(month)) in covered_months)

    def _within_observed_window(target: date) -> bool:
        if min_observed_date is None or max_observed_date is None:
            return False
        return min_observed_date <= target <= max_observed_date

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

        a_in_window = day <= month_days_a and _within_observed_window(
            date(int(year_a), int(month), day)
        )
        b_in_window = day <= month_days_b and _within_observed_window(
            date(int(year_b), int(month), day)
        )

        if a_fact is not None:
            a_value: float | None = a_fact
            a_source = "fact"
        elif a_month_covered and a_in_window:
            a_value = 0.0
            a_source = "fact"
        elif a_ml is not None:
            a_value = a_ml
            a_source = "ml"
        else:
            a_value = None
            a_source = "empty"

        if b_fact is not None:
            b_value: float | None = b_fact
            b_source = "fact"
        elif b_month_covered and b_in_window:
            b_value = 0.0
            b_source = "fact"
        elif b_ml is not None:
            b_value = b_ml
            b_source = "ml"
        else:
            b_value = None
            b_source = "empty"

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

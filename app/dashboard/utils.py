from __future__ import annotations

import re
from typing import Any

from app.services.shared.formatting import (
    format_datetime as _format_datetime,
    format_number_two_decimals as _format_number,
    format_percentage as _format_percentage,
)
from app.shared.sql_utils import quote_identifier
from app.table_catalog import select_clean_table_names
from config.constants import FORECASTING_FORECAST_DAY_OPTIONS

DASHBOARD_HORIZON_OPTIONS: tuple[int, ...] = tuple(int(day) for day in FORECASTING_FORECAST_DAY_OPTIONS)


def build_horizon_day_options() -> list[dict[str, str]]:
    return [{"value": str(day), "label": f"{day} дней"} for day in DASHBOARD_HORIZON_OPTIONS]


def _select_tables(table_names: list[str]) -> list[str]:
    return select_clean_table_names(table_names)


def _extract_year_from_name(table_name: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", table_name)
    return int(match.group(0)) if match else None


def _parse_year(year_value: str) -> int | None:
    if not year_value or year_value == "all":
        return None
    try:
        return int(year_value)
    except ValueError:
        return None


def _find_option_label(options: list[dict[str, str]], value: str, fallback: str) -> str:
    for item in options:
        if item["value"] == value:
            return item["label"]
    return fallback


def _date_expression(column_name: str) -> str:
    column_sql = quote_identifier(column_name)
    text_value = f"TRIM(CAST({column_sql} AS TEXT))"
    numeric_text = f"REPLACE({text_value}, ',', '.')"
    return (
        "CASE "
        f"WHEN {text_value} ~ '^[0-9]{{2}}\\.[0-9]{{2}}\\.[0-9]{{4}}$' THEN TO_DATE({text_value}, 'DD.MM.YYYY') "
        f"WHEN {text_value} ~ '^[0-9]{{2}}\\.[0-9]{{2}}\\.[0-9]{{2}}$' THEN TO_DATE({text_value}, 'DD.MM.YY') "
        f"WHEN {text_value} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' THEN TO_DATE(SUBSTRING({text_value} FROM 1 FOR 10), 'YYYY-MM-DD') "
        f"WHEN {text_value} ~ '^[0-9]{{4}}/[0-9]{{2}}/[0-9]{{2}}' THEN TO_DATE(SUBSTRING({text_value} FROM 1 FOR 10), 'YYYY/MM/DD') "
        f"WHEN {text_value} ~ '^[0-9]{{5}}(?:[.,][0-9]+)?$' "
        f"AND ({numeric_text})::double precision BETWEEN 20000 AND 100000 "
        f"THEN DATE '1899-12-30' + FLOOR(({numeric_text})::double precision)::int "
        "ELSE NULL END"
    )


def _format_chart_date(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _format_signed_number(value: float, integer: bool = False) -> str:
    if value > 0:
        return f"+{_format_number(value, integer=integer)}"
    return _format_number(value, integer=integer)


def _format_period_label(years: list[int]) -> str:
    if not years:
        return "Нет данных"
    normalized = sorted(set(years))
    if len(normalized) == 1:
        return str(normalized[0])
    return f"{normalized[0]}-{normalized[-1]}"

__all__ = [
    "DASHBOARD_HORIZON_OPTIONS",
    "build_horizon_day_options",
]

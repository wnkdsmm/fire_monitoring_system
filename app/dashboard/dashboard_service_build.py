from __future__ import annotations

from datetime import datetime

from app.plotly_bundle import PLOTLY_AVAILABLE
from config.constants import PRIORITY_HORIZON_DAYS

from .charts import _finalize_chart
from .distribution import _damage_count_columns
from .distribution_logic import (
    _build_dashboard_widgets,
    _build_damage_dashboard_charts,
    _build_standard_dashboard_charts,
)
from .impact import (
    _build_cause_chart,
    _collect_dashboard_grouped_counts,
)
from .metadata import _is_damage_group_selection
from .management import _build_management_snapshot, _empty_management_snapshot
from .summary_logic import (
    _build_dashboard_scope,
    _build_dashboard_summary_metrics,
    _build_dashboard_summary_series,
)
from .types import (
    DashboardAggregation,
    DashboardContext,
    DashboardMetadata,
    DashboardOption,
    DashboardPayload,
    DashboardTableRef,
)
from .utils import _format_datetime, build_horizon_day_options


def _build_dashboard_error_context(error_message: str, *, plotly_js: str = "") -> DashboardContext:
    return {
        "generated_at": _format_datetime(datetime.now()),
        "filters": {
            "tables": [{"value": "all", "label": "Все таблицы"}],
            "years": [],
            "group_columns": [],
        },
        "initial_data": _empty_dashboard_data(),
        "errors": [error_message],
        "has_data": False,
        "plotly_js": plotly_js,
    }


def _build_dashboard_aggregation(
    *,
    metadata: DashboardMetadata,
    selected_tables: list[DashboardTableRef],
    selected_year: int | None,
    selected_group_column: str,
    selected_table_name: str,
    available_years: list[DashboardOption],
    available_group_columns: list[DashboardOption],
    horizon_days: int = PRIORITY_HORIZON_DAYS,
    selected_table_label: str = "",
) -> DashboardAggregation:
    summary_series = _build_dashboard_summary_series(selected_tables, selected_year)
    summary = summary_series["summary"]
    yearly_fires_series = summary_series["yearly_fires_series"]
    table_breakdown_series = summary_series["table_breakdown_series"]
    is_damage_group = _is_damage_group_selection(selected_group_column)
    if is_damage_group:
        grouped_counts_bundle = _collect_dashboard_grouped_counts(
            selected_tables,
            selected_year,
            selected_group_column,
            include_area_buckets=False,
            include_impact_timeline=False,
            positive_count_columns=_damage_count_columns(),
        )
    else:
        grouped_counts_bundle = _collect_dashboard_grouped_counts(
            selected_tables,
            selected_year,
            selected_group_column,
            include_area_buckets=False,
            include_impact_timeline=True,
        )
    cause_counts = grouped_counts_bundle["cause_counts"]
    cause_overview = _build_cause_chart(selected_tables, selected_year, cause_counts=cause_counts)
    damage_counts = grouped_counts_bundle.get("positive_column_counts") or {}
    has_damage_data = any(int(value or 0) > 0 for value in damage_counts.values())
    use_damage_group = is_damage_group and has_damage_data

    dashboard_charts = (
        _build_damage_dashboard_charts(
            selected_tables,
            selected_year,
            damage_counts=damage_counts,
        )
        if use_damage_group
        else _build_standard_dashboard_charts(
            selected_tables,
            selected_year,
            selected_group_column if not is_damage_group else "",
            grouped_counts_bundle,
        )
    )
    distribution = dashboard_charts["distribution"]
    yearly_area_chart = dashboard_charts["yearly_area_chart"]
    monthly_profile = dashboard_charts["monthly_profile"]
    monthly_heatmap = dashboard_charts["monthly_heatmap"]
    summary_metrics = _build_dashboard_summary_metrics(
        summary=summary,
        yearly_fires_series=yearly_fires_series,
        table_breakdown_series=table_breakdown_series,
        distribution=distribution,
        cause_overview=cause_overview,
    )
    trend = summary_metrics["trend"]
    rankings = summary_metrics["rankings"]
    highlights = summary_metrics["highlights"]
    widgets = _build_dashboard_widgets(selected_tables, selected_year, grouped_counts_bundle)
    management = _build_management_snapshot(
        selected_tables=selected_tables,
        selected_year=selected_year,
        summary=summary,
        precomputed_summary=summary,
        trend=trend,
        cause_overview=cause_overview,
        district_widget=widgets["districts"],
        planning_horizon_days=horizon_days,
    )
    scope = _build_dashboard_scope(
        summary=summary,
        metadata=metadata,
        selected_table_name=selected_table_name,
        selected_group_column=selected_group_column if use_damage_group or not is_damage_group else "",
        available_group_columns=available_group_columns,
        available_years=available_years,
    )
    if selected_table_label:
        scope["table_label"] = selected_table_label
    if is_damage_group and not has_damage_data:
        scope["group_label"] = "Нет данных по ущербу (показан общий режим)"

    return {
        "summary": summary,
        "yearly_fires_series": yearly_fires_series,
        "cause_overview": cause_overview,
        "distribution": distribution,
        "yearly_area_chart": yearly_area_chart,
        "monthly_profile": monthly_profile,
        "monthly_heatmap": monthly_heatmap,
        "trend": trend,
        "rankings": rankings,
        "highlights": highlights,
        "widgets": widgets,
        "management": management,
        "scope": scope,
    }


def _build_dashboard_payload(
    *,
    metadata: DashboardMetadata,
    aggregation: DashboardAggregation,
    selected_tables: list[DashboardTableRef],
    selected_table_name: str,
    selected_year: int | None,
    selected_group_column: str,
    available_years: list[DashboardOption],
    available_group_columns: list[DashboardOption],
    horizon_days: int = PRIORITY_HORIZON_DAYS,
    selected_table_names: list[str] | None = None,
) -> DashboardPayload:
    summary = aggregation["summary"]
    scope = aggregation["scope"]
    trend = aggregation["trend"]
    management = aggregation["management"]
    cause_overview = aggregation["cause_overview"]
    distribution = aggregation["distribution"]
    yearly_area_chart = aggregation["yearly_area_chart"]
    yearly_trend_chart = aggregation["yearly_fires_series"]
    monthly_profile = aggregation["monthly_profile"]
    monthly_heatmap = aggregation["monthly_heatmap"]
    management["export_text"] = ""
    if isinstance(management.get("brief"), dict):
        management["brief"]["export_text"] = ""

    notes = list(metadata["errors"][:5])
    if not PLOTLY_AVAILABLE:
        notes.append("Библиотека Plotly не найдена в окружении. Интерактивные графики не будут показаны.")
    data_overlap_disclaimer = (
        "Показатели суммированы по выбранным таблицам без проверки пересечений."
        if int(summary.get("tables_used") or 0) > 1
        else None
    )

    payload = {
        "generated_at": _format_datetime(datetime.now()),
        "has_data": bool(selected_tables),
        "summary": summary,
        "scope": scope,
        "trend": trend,
        "management": management,
        "highlights": aggregation["highlights"],
        "rankings": aggregation["rankings"],
        "widgets": aggregation["widgets"],
        "charts": {
            "yearly_fires": cause_overview,
            "yearly_area": yearly_area_chart,
            "yearly_trend": yearly_trend_chart,
            "monthly_heatmap": monthly_heatmap,
            "monthly_profile": monthly_profile,
        },
        "filters": {
            "table_name": selected_table_name,
            "table_names": selected_table_names or [],
            "year": str(selected_year) if selected_year is not None else "all",
            "group_column": selected_group_column,
            "horizon_days": str(horizon_days),
            "available_tables": metadata["table_options"],
            "available_years": available_years,
            "available_group_columns": available_group_columns,
            "available_horizon_days": build_horizon_day_options(),
        },
        "notes": notes,
    }
    if data_overlap_disclaimer:
        payload["data_overlap_disclaimer"] = data_overlap_disclaimer
    return payload


def _empty_dashboard_data(
    error_message: str = "",
    *,
    horizon_days: int = PRIORITY_HORIZON_DAYS,
) -> DashboardPayload:
    return {
        "generated_at": _format_datetime(datetime.now()),
        "has_data": False,
        "summary": {
            "fires_count": 0,
            "fires_count_display": "0",
            "total_area": 0,
            "total_area_display": "0",
            "average_area": 0,
            "average_area_display": "0",
            "tables_used": 0,
            "tables_used_display": "0",
            "area_records": 0,
            "area_records_display": "0",
            "area_fill_rate": 0,
            "area_fill_rate_display": "0%",
            "years_covered": 0,
            "years_covered_display": "0",
            "period_label": "Нет данных",
            "year_label": "Все годы",
            "deaths": 0,
            "deaths_display": "0",
            "injuries": 0,
            "injuries_display": "0",
            "evacuated": 0,
            "evacuated_display": "0",
            "evacuated_adults": 0,
            "evacuated_adults_display": "0",
            "evacuated_children": 0,
            "evacuated_children_display": "0",
            "rescued_total": 0,
            "rescued_total_display": "0",
            "rescued_adults": 0,
            "rescued_adults_display": "0",
            "rescued_children": 0,
            "rescued_children_display": "0",
            "children_total": 0,
            "children_total_display": "0",
        },
        "scope": {
            "table_label": "Все таблицы",
            "year_label": "Все годы",
            "group_label": "Нет данных",
            "table_count": 0,
            "table_count_display": "0",
            "database_tables_count": 0,
            "database_tables_count_display": "0",
            "available_years_count": 0,
            "available_years_count_display": "0",
            "period_label": "Нет данных",
        },
        "trend": {
            "title": "Динамика последнего года",
            "current_year": "-",
            "current_value_display": "0",
            "previous_year": "",
            "delta_display": "Нет базы сравнения",
            "direction": "flat",
            "description": "Недостаточно данных для сравнения по годам.",
        },
        "management": _empty_management_snapshot(priority_horizon_days=horizon_days),
        "highlights": [],
        "rankings": {
            "top_distribution": [],
            "top_tables": [],
            "recent_years": [],
        },
        "widgets": {
            "causes": _finalize_chart("SQL-виджет: причины", [], "Нет данных по причинам возгорания."),
            "districts": _finalize_chart("SQL-виджет: районы", [], "В выбранных таблицах не найдено колонок района."),
            "seasons": _finalize_chart("SQL-виджет: сезоны", [], "Нет данных для сезонного SQL-виджета."),
        },
        "charts": {
            "yearly_fires": _finalize_chart("Причины возгораний", [], "Нет данных по причинам возгорания."),
            "yearly_area": _finalize_chart("Последствия, эвакуация и дети", [], "Нет данных по погибшим, травмам и эвакуации."),
            "yearly_trend": _finalize_chart("Динамика количества пожаров по годам", [], "Недостаточно данных для динамики по годам."),
            "monthly_heatmap": _finalize_chart("Сезонность по месяцам и годам", [], "Недостаточно данных для тепловой карты сезонности."),
            "monthly_profile": _finalize_chart("Сезонность по месяцам", [], "Нет данных для сезонного профиля."),
        },
        "filters": {
            "table_name": "all",
            "table_names": [],
            "year": "",
            "group_column": "",
            "horizon_days": str(horizon_days),
            "available_tables": [{"value": "all", "label": "Все таблицы"}],
            "available_years": [],
            "available_group_columns": [],
            "available_horizon_days": build_horizon_day_options(),
        },
        "notes": [error_message] if error_message else [],
    }

__all__ = [
    '_build_dashboard_error_context',
    '_build_dashboard_aggregation',
    '_build_dashboard_payload',
    '_empty_dashboard_data',
]


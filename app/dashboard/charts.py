from __future__ import annotations

import plotly.graph_objects as go
from app.plotly_bundle import serialize_plotly_figure
from app.statistics_constants import MONTH_LABELS

from app.services.shared.dashboard_charts import (
    _build_area_bucket_plotly,
    _build_cause_plotly,
    _build_combined_impact_timeline_plotly,
    _build_damage_overview_plotly,
    _build_damage_pairs_plotly,
    _build_empty_plotly_chart,
    _build_damage_share_plotly,
    _build_damage_standalone_plotly,
    _build_distribution_pie_plotly,
    _build_distribution_plotly,
    _build_monthly_profile_plotly,
    _build_sql_widget_bar_plotly,
    _build_sql_widget_season_plotly,
    _build_table_breakdown_plotly,
    _build_yearly_plotly,
    _finalize_chart,
    _plotly_layout,
    _wrap_plotly_label,
)


def empty_figure(message: str) -> dict:
    return _build_empty_plotly_chart("", message)


def _build_cumulative_area_plotly(
    title: str,
    current_year_data: list[dict],
    previous_year_data: list[dict],
    current_year: int,
    previous_year: int,
    empty_message: str,
) -> dict:
    if len(current_year_data) < 7 and len(previous_year_data) < 7:
        return empty_figure(empty_message)

    current_days = [int(item.get("day_of_year") or 0) for item in current_year_data]
    current_values = [float(item.get("area") or 0.0) for item in current_year_data]
    previous_days = [int(item.get("day_of_year") or 0) for item in previous_year_data]
    previous_values = [float(item.get("area") or 0.0) for item in previous_year_data]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=current_days,
            y=current_values,
            mode="lines",
            name=str(current_year),
            line={"color": "#cf2323", "width": 3},
            hovertemplate=f"Р“РѕРґ: {current_year}<br>Р”РµРЅСЊ: %{{x}}<br>РџР»РѕС‰Р°РґСЊ: %{{y:.2f}} РіР°<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=previous_days,
            y=previous_values,
            mode="lines",
            name=str(previous_year),
            line={"color": "#8a8a8a", "width": 2, "dash": "dash"},
            hovertemplate=f"Р“РѕРґ: {previous_year}<br>Р”РµРЅСЊ: %{{x}}<br>РџР»РѕС‰Р°РґСЊ: %{{y:.2f}} РіР°<extra></extra>",
        )
    )
    figure.update_layout(
        _plotly_layout("РќР°РєРѕРїР»РµРЅРЅР°СЏ РїР»РѕС‰Р°РґСЊ, РіР°", showlegend=True),
        xaxis={"title": "Р”РµРЅСЊ РіРѕРґР°", "range": [1, 365]},
    )
    return serialize_plotly_figure(figure)


def _build_monthly_heatmap_plotly(
    title: str,
    data: dict[int, dict[int, int]],
    empty_message: str,
) -> dict:
    if not data:
        return empty_figure(empty_message)

    years = sorted(int(year_value) for year_value in data.keys())
    x_values = list(range(1, 13))
    z_values = []
    text_values = []

    for year_value in years:
        row = []
        text_row = []
        month_counts = data.get(year_value) or {}
        for month_value in x_values:
            count_value = int(month_counts.get(month_value, 0) or 0)
            row.append(count_value)
            text_row.append(
                f"Р“РѕРґ: {year_value}<br>РњРµСЃСЏС†: {MONTH_LABELS[month_value]}<br>РџРѕР¶Р°СЂРѕРІ: {count_value}"
            )
        z_values.append(row)
        text_values.append(text_row)

    figure = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_values,
            y=years,
            text=text_values,
            hoverinfo="text",
            colorscale="YlOrRd",
        )
    )
    figure.update_layout(
        _plotly_layout("РљРѕР»РёС‡РµСЃС‚РІРѕ РїРѕР¶Р°СЂРѕРІ", showlegend=False),
        xaxis={"title": "РњРµСЃСЏС†", "tickmode": "array", "tickvals": x_values, "ticktext": [MONTH_LABELS[month] for month in x_values]},
        yaxis={"title": "Р“РѕРґ"},
    )
    return serialize_plotly_figure(figure)

__all__ = [
    "_finalize_chart",
    "_build_yearly_plotly",
    "_wrap_plotly_label",
    "_build_cause_plotly",
    "_build_distribution_pie_plotly",
    "_build_distribution_plotly",
    "_build_combined_impact_timeline_plotly",
    "_build_damage_overview_plotly",
    "_build_damage_pairs_plotly",
    "_build_empty_plotly_chart",
    "_build_damage_standalone_plotly",
    "_build_damage_share_plotly",
    "_build_table_breakdown_plotly",
    "_build_monthly_profile_plotly",
    "_build_area_bucket_plotly",
    "_build_sql_widget_bar_plotly",
    "_build_sql_widget_season_plotly",
    "_plotly_layout",
    "_build_cumulative_area_plotly",
    "_build_monthly_heatmap_plotly",
    "empty_figure",
]

from __future__ import annotations

from statistics import mean
from typing import Any

from app.labels import (
    FORECASTING_FEATURE_CARD_CONFIG,
    FORECASTING_FEATURE_COVERAGE_DISPLAY_TEMPLATE,
    FORECASTING_FEATURE_QUALITY_LABEL_GOOD,
    FORECASTING_FEATURE_QUALITY_LABEL_MISSING,
    FORECASTING_FEATURE_QUALITY_LABEL_SPARSE,
    FORECASTING_FEATURE_SOURCES_COVERAGE_TEMPLATE,
    FORECASTING_FEATURE_SOURCE_COVERAGE_SUFFIX_TEMPLATE,
    FORECASTING_FEATURE_STATUS_LABEL_MISSING,
    FORECASTING_FEATURE_STATUS_LABEL_PARTIAL_TEMPLATE,
    FORECASTING_FEATURE_STATUS_LABEL_USED,
    FORECASTING_FEATURE_TEMPERATURE_LOW_COVERAGE_DESCRIPTION,
    FORECASTING_INSIGHT_LABEL_ACTIVE_WEEKDAY,
    FORECASTING_INSIGHT_LABEL_AVERAGE_PROBABILITY,
    FORECASTING_INSIGHT_LABEL_COMPARE_RECENT,
    FORECASTING_INSIGHT_LABEL_RISKIEST_DAY,
    FORECASTING_INSIGHT_LABEL_STABILITY,
    FORECASTING_INSIGHT_META_ACTIVE_WEEKDAY_TEMPLATE,
    FORECASTING_INSIGHT_META_COMPARE_RECENT_TEMPLATE,
    FORECASTING_INSIGHT_META_HORIZON_TEMPLATE,
    FORECASTING_INSIGHT_META_PROBABILITY_TEMPLATE,
    FORECASTING_NOTE_INTERPRETATION,
    FORECASTING_NOTE_MISSING_DATE,
    FORECASTING_NOTE_MISSING_TEMPERATURE,
    FORECASTING_NOTE_MULTI_TABLE_TEMPLATE,
    FORECASTING_NOTE_NO_HISTORY,
    FORECASTING_NOTE_PARTIAL_CAUSE,
    FORECASTING_NOTE_PARTIAL_OBJECT_CATEGORY,
    FORECASTING_NOTE_SHORT_HISTORY,
    FORECASTING_SUMMARY_HERO_EMPTY,
    FORECASTING_SUMMARY_HERO_TEMPLATE,
    FORECASTING_TEMPERATURE_SCENARIO_SEASONAL,
)
from app.services.shared.formatting import (
    format_percent as _format_percent,
    normalize_probability as _normalize_probability,
)

from .bootstrap import _build_slice_label
from .selection import _table_selection_label
from .types import (
    ForecastingDailyHistoryRow,
    ForecastingFeatureCard,
    ForecastingForecastRow,
    ForecastingTableMetadata,
    ForecastingTemperatureQuality,
    ForecastingWeekdayProfileRow,
)
from .utils import (
    _forecast_level_label,
    _forecast_stability_hint,
    _format_integer,
    _format_number,
    _format_period,
    _format_probability,
    _format_signed_percent,
    _history_window_label,
)

# intentionally separate from access_points/presentation.py::_build_summary and
# ml_model/training/presentation_training.py::_build_summary:
# forecasting summary is scenario-level (time-series probability) and lightweight.


def _build_summary(
    selected_table: str,
    selected_district: str,
    selected_cause: str,
    selected_object_category: str,
    temperature_value: float | None,
    daily_history: list[ForecastingDailyHistoryRow],
    filtered_records_count: int,
    forecast_rows: list[ForecastingForecastRow],
    history_window: str,
) -> dict[str, str]:
    history_dates = [item["date"] for item in daily_history]
    history_counts = [float(item["count"]) for item in daily_history]
    active_days = sum(1 for item in daily_history if item["count"] > 0)
    predicted_total = sum(item["forecast_value"] for item in forecast_rows)
    predicted_average = predicted_total / len(forecast_rows) if forecast_rows else 0.0
    average_probability = (
        mean(_normalize_probability(item.get("fire_probability", 0.0)) for item in forecast_rows)
        if forecast_rows
        else 0.0
    )
    historical_average = mean(history_counts) if history_counts else 0.0
    recent_counts = history_counts[-28:] if len(history_counts) >= 28 else history_counts
    recent_average = mean(recent_counts) if recent_counts else historical_average
    active_days_share = active_days / len(daily_history) if daily_history else 0.0
    delta_ratio = (predicted_average - recent_average) / recent_average if recent_average > 0 else 0.0
    scenario_label, _scenario_tone = _forecast_level_label(
        predicted_average,
        recent_average if recent_average > 0 else historical_average,
    )
    peak_row = max(forecast_rows, key=lambda item: float(item["forecast_value"])) if forecast_rows else None
    hero_summary = (
        FORECASTING_SUMMARY_HERO_TEMPLATE.format(
            peak_date=peak_row.get("date_display", "-"),
            peak_probability=peak_row.get("fire_probability_display", "0%"),
            average_probability=_format_probability(average_probability),
        )
        if peak_row
        else FORECASTING_SUMMARY_HERO_EMPTY
    )
    return {
        "selected_table_label": _table_selection_label(selected_table),
        "slice_label": _build_slice_label(selected_district, selected_cause, selected_object_category),
        "hero_summary": hero_summary,
        "history_period_label": _format_period(history_dates),
        "history_window_label": _history_window_label(history_window),
        "fires_count_display": _format_integer(filtered_records_count),
        "history_days_display": _format_integer(len(daily_history)),
        "active_days_display": _format_integer(active_days),
        "active_days_share_display": _format_percent(active_days_share),
        "last_observed_date": history_dates[-1].strftime("%d.%m.%Y") if history_dates else "-",
        "forecast_days_display": _format_integer(len(forecast_rows)),
        "predicted_total_display": _format_number(predicted_total),
        "predicted_average_display": _format_number(predicted_average),
        "average_probability_display": _format_probability(average_probability),
        "historical_average_display": _format_number(historical_average),
        "recent_average_display": _format_number(recent_average),
        "forecast_vs_recent_display": _format_signed_percent(delta_ratio),
        "forecast_vs_recent_label": scenario_label,
        "peak_forecast_day_display": peak_row["date_display"] if peak_row else "-",
        "peak_forecast_value_display": peak_row["forecast_value_display"] if peak_row else "0",
        "peak_forecast_probability_display": peak_row["fire_probability_display"] if peak_row else "0%",
        "temperature_scenario_display": (
            f"{_format_number(temperature_value)} °C" if temperature_value is not None else FORECASTING_TEMPERATURE_SCENARIO_SEASONAL
        ),
    }


def _build_feature_cards(metadata: Any) -> list[dict[str, str]]:
    metadata_items = metadata if isinstance(metadata, list) else [metadata]
    metadata_items = [item for item in metadata_items if item]
    if not metadata_items:
        return []
    total_tables = len(metadata_items)
    feature_config = FORECASTING_FEATURE_CARD_CONFIG
    cards = []
    for key, label, description in feature_config:
        sources = []
        found = 0
        for item in metadata_items:
            source_column = item["resolved_columns"].get(key)
            if source_column:
                found += 1
                sources.append(f"{item['table_name']}: {source_column}")
        if found == total_tables:
            status = "used"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_USED
        elif found > 0:
            status = "partial"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_PARTIAL_TEMPLATE.format(found=found, total_tables=total_tables)
        else:
            status = "missing"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_MISSING
        cards.append(
            {
                "label": label,
                "status": status,
                "status_label": status_label,
                "source": "; ".join(sources[:3]) if sources else FORECASTING_FEATURE_STATUS_LABEL_MISSING,
                "description": description,
            }
        )
    return cards


def _build_feature_cards_with_quality(
    metadata: Any,
    temperature_quality: ForecastingTemperatureQuality | None = None,
) -> list[ForecastingFeatureCard]:
    metadata_items = metadata if isinstance(metadata, list) else [metadata]
    metadata_items = [item for item in metadata_items if item]
    if not metadata_items:
        return []
    total_tables = len(metadata_items)
    feature_config = FORECASTING_FEATURE_CARD_CONFIG
    cards: list[ForecastingFeatureCard] = []
    for key, label, base_description in feature_config:
        description = base_description
        sources: list[str] = []
        found = 0
        quality_items: list[ForecastingTemperatureQuality] = []
        for item in metadata_items:
            source_column = (item.get("resolved_columns") or {}).get(key)
            if not source_column:
                continue
            found += 1
            quality = (item.get("column_quality") or {}).get(key) or {} if key == "temperature" else {}
            coverage_suffix = ""
            if key == "temperature" and temperature_quality is None:
                non_null_days = int(quality.get("non_null_days", 0) or 0)
                total_days = int(quality.get("total_days", 0) or 0)
                coverage_value = _normalize_probability(quality.get("coverage", 0.0) or 0.0)
                coverage_suffix = FORECASTING_FEATURE_SOURCE_COVERAGE_SUFFIX_TEMPLATE.format(
                    non_null_days=non_null_days,
                    total_days=total_days,
                    coverage=_format_percent(coverage_value),
                )
            if key == "temperature":
                quality_items.append(quality)
            sources.append(f"{item['table_name']}: {source_column}{coverage_suffix}")
        coverage_display = None
        quality_status = None
        quality_label = None
        usable = found == total_tables and found > 0
        if key == "temperature" and found > 0:
            non_null_days = sum(int(item.get("non_null_days", 0) or 0) for item in quality_items)
            total_days = sum(int(item.get("total_days", 0) or 0) for item in quality_items)
            coverage_value = float(non_null_days) / float(total_days) if total_days > 0 else 0.0
            coverage_display = FORECASTING_FEATURE_COVERAGE_DISPLAY_TEMPLATE.format(
                non_null_days=non_null_days,
                total_days=total_days,
                coverage=_format_percent(coverage_value),
            )
            usable = all(bool(item.get("usable")) for item in quality_items) and len(quality_items) == found
            quality_status = "good" if usable else "missing" if non_null_days <= 0 else "sparse"
            quality_label = (
                FORECASTING_FEATURE_QUALITY_LABEL_GOOD
                if usable
                else FORECASTING_FEATURE_QUALITY_LABEL_MISSING
                if non_null_days <= 0
                else FORECASTING_FEATURE_QUALITY_LABEL_SPARSE
            )
            if not usable:
                description = FORECASTING_FEATURE_TEMPERATURE_LOW_COVERAGE_DESCRIPTION
        if key == "temperature" and found > 0 and temperature_quality is not None:
            non_null_days = int(temperature_quality.get("non_null_days", 0) or 0)
            total_days = int(temperature_quality.get("total_days", 0) or 0)
            coverage_value = _normalize_probability(temperature_quality.get("coverage", 0.0) or 0.0)
            coverage_display = FORECASTING_FEATURE_COVERAGE_DISPLAY_TEMPLATE.format(
                non_null_days=non_null_days,
                total_days=total_days,
                coverage=_format_percent(coverage_value),
            )
            usable = bool(temperature_quality.get("usable")) and found == total_tables
            quality_status = str(temperature_quality.get("quality_key") or ("missing" if non_null_days <= 0 else "sparse"))
            quality_label = str(
                temperature_quality.get("quality_label")
                or (
                    FORECASTING_FEATURE_QUALITY_LABEL_MISSING
                    if non_null_days <= 0
                    else FORECASTING_FEATURE_QUALITY_LABEL_SPARSE
                )
            )
            if not usable:
                description = FORECASTING_FEATURE_TEMPERATURE_LOW_COVERAGE_DESCRIPTION
            if sources:
                base_sources = [source.split(" | ", 1)[0] for source in sources[:3]]
                sources = [
                    FORECASTING_FEATURE_SOURCES_COVERAGE_TEMPLATE.format(
                        sources="; ".join(base_sources),
                        coverage_display=coverage_display,
                    )
                ]
        if key == "temperature" and found > 0 and found < total_tables:
            usable = False
            quality_status = "partial"
            quality_label = FORECASTING_FEATURE_STATUS_LABEL_PARTIAL_TEMPLATE.format(found=found, total_tables=total_tables)
            description = base_description
        if found == 0:
            status = "missing"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_MISSING
            usable = False
        elif key == "temperature" and quality_label is not None:
            status = "used" if usable and found == total_tables else "partial"
            status_label = f"{quality_label} ({coverage_display})"
        elif found == total_tables:
            status = "used"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_USED
        else:
            status = "partial"
            status_label = FORECASTING_FEATURE_STATUS_LABEL_PARTIAL_TEMPLATE.format(found=found, total_tables=total_tables)
        cards.append(
            {
                "label": label,
                "status": status,
                "status_label": status_label,
                "source": "; ".join(sources[:3]) if sources else FORECASTING_FEATURE_STATUS_LABEL_MISSING,
                "description": description,
                "quality_status": quality_status,
                "quality_label": quality_label,
                "coverage_display": coverage_display,
                "usable": usable,
            }
        )
    return cards


def _build_insights(
    daily_history: list[ForecastingDailyHistoryRow],
    forecast_rows: list[ForecastingForecastRow],
    weekday_profile: list[ForecastingWeekdayProfileRow],
) -> list[dict[str, str]]:
    insights = []
    if forecast_rows:
        peak_row = max(forecast_rows, key=lambda item: _normalize_probability(item.get("fire_probability", 0.0)))
        insights.append(
            {
                "label": FORECASTING_INSIGHT_LABEL_RISKIEST_DAY,
                "value": peak_row["date_display"],
                "meta": FORECASTING_INSIGHT_META_PROBABILITY_TEMPLATE.format(
                    probability=peak_row["fire_probability_display"],
                ),
                "tone": "fire",
            }
        )
        average_probability = mean(_normalize_probability(item.get("fire_probability", 0.0)) for item in forecast_rows)
        insights.append(
            {
                "label": FORECASTING_INSIGHT_LABEL_AVERAGE_PROBABILITY,
                "value": _format_probability(average_probability),
                "meta": FORECASTING_INSIGHT_META_HORIZON_TEMPLATE.format(days=len(forecast_rows)),
                "tone": "forest",
            }
        )
    if daily_history and forecast_rows:
        recent_values = [float(item["count"]) for item in (daily_history[-28:] if len(daily_history) >= 28 else daily_history)]
        recent_average = mean(recent_values) if recent_values else 0.0
        forecast_average = mean(float(item["forecast_value"]) for item in forecast_rows)
        insights.append(
            {
                "label": FORECASTING_INSIGHT_LABEL_COMPARE_RECENT,
                "value": _format_signed_percent((forecast_average - recent_average) / recent_average if recent_average > 0 else 0.0),
                "meta": FORECASTING_INSIGHT_META_COMPARE_RECENT_TEMPLATE.format(
                    level_label=_forecast_level_label(forecast_average, recent_average)[0],
                ),
                "tone": "sky",
            }
        )
    if weekday_profile:
        peak_weekday = max(weekday_profile, key=lambda item: float(item["avg_value"]))
        insights.append(
            {
                "label": FORECASTING_INSIGHT_LABEL_ACTIVE_WEEKDAY,
                "value": peak_weekday["label"],
                "meta": FORECASTING_INSIGHT_META_ACTIVE_WEEKDAY_TEMPLATE.format(
                    avg_display=peak_weekday["avg_display"],
                ),
                "tone": "sand",
            }
        )
    stability_label, stability_meta = _forecast_stability_hint(daily_history)
    insights.append(
        {
            "label": FORECASTING_INSIGHT_LABEL_STABILITY,
            "value": stability_label,
            "meta": stability_meta,
            "tone": "sky",
        }
    )
    return insights[:4]


def _build_notes(
    metadata: ForecastingTableMetadata | list[ForecastingTableMetadata],  # one-off
    filtered_records_count: int,
    daily_history: list[ForecastingDailyHistoryRow],
    temperature_value: float | None,
) -> list[str]:
    metadata_items = metadata if isinstance(metadata, list) else [metadata]
    metadata_items = [item for item in metadata_items if item]
    notes: list[str] = []
    if len(metadata_items) > 1:
        notes.append(FORECASTING_NOTE_MULTI_TABLE_TEMPLATE.format(tables_count=len(metadata_items)))
    if not any(item["resolved_columns"].get("date") for item in metadata_items):
        notes.append(FORECASTING_NOTE_MISSING_DATE)
    if filtered_records_count <= 0:
        notes.append(FORECASTING_NOTE_NO_HISTORY)
    elif len(daily_history) < 14:
        notes.append(FORECASTING_NOTE_SHORT_HISTORY)
    if temperature_value is not None and not any(item["resolved_columns"].get("temperature") for item in metadata_items):
        notes.append(FORECASTING_NOTE_MISSING_TEMPERATURE)
    if any(not item["resolved_columns"].get("cause") for item in metadata_items):
        notes.append(FORECASTING_NOTE_PARTIAL_CAUSE)
    if any(not item["resolved_columns"].get("object_category") for item in metadata_items):
        notes.append(FORECASTING_NOTE_PARTIAL_OBJECT_CATEGORY)
    notes.append(FORECASTING_NOTE_INTERPRETATION)
    return notes

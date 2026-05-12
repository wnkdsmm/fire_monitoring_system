from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from app.services.forecasting.presentation import _build_feature_cards_with_quality
from app.services.forecasting.utils import _format_datetime, _history_window_label

from .ml_model_config_types import ML_PREDICTIVE_BLOCK_DESCRIPTION, MODEL_NAME
from .training.presentation_backtesting import _build_quality_assessment
from .training.presentation_meta import _build_notes
from .training.presentation_training import (
    _build_importance_chart,
    _build_summary,
)
from .training.appg import compute_appg_series
from .training.training_result import _empty_ml_result

_YEAR_TOKEN_RE = re.compile(r"(19\d{2}|20\d{2}|2100)")


def _compact_ui_notes(items: list[Any], limit: int = 2) -> list[str]:
    notes: list[str] = []
    for item in items:
        text = str(item).strip() if item is not None else ''
        if not text or text in notes:
            continue
        notes.append(text)
        if len(notes) >= limit:
            break
    return notes


def _extract_available_years_from_table_options(table_options: list[dict[str, str]]) -> list[dict[str, str]]:
    years: set[int] = set()
    for option in table_options:
        value = str((option or {}).get('value') or '').strip()
        if not value or value == 'all':
            continue
        for token in _YEAR_TOKEN_RE.findall(value):
            year = int(token)
            if 1900 <= year <= 2100:
                years.add(year)
    return [
        {'value': str(year), 'label': str(year)}
        for year in sorted(years, reverse=True)
    ]


def _extract_available_years_from_daily_history(daily_history: list[dict[str, Any]]) -> list[dict[str, str]]:
    years: set[int] = set()
    for row in daily_history:
        raw_date = row.get('date') if isinstance(row, dict) else None
        if isinstance(raw_date, datetime):
            years.add(int(raw_date.year))
            continue
        if isinstance(raw_date, date):
            years.add(int(raw_date.year))
            continue
        text = str(raw_date or '').strip()
        if len(text) >= 4 and text[:4].isdigit():
            years.add(int(text[:4]))
    return [
        {'value': str(year), 'label': str(year)}
        for year in sorted(years, reverse=True)
    ]


def _extract_available_years(
    table_options: list[dict[str, str]],
    daily_history: list[dict[str, Any]],
) -> list[dict[str, str]]:
    from_tables = _extract_available_years_from_table_options(table_options)
    if from_tables:
        return from_tables
    return _extract_available_years_from_daily_history(daily_history)


def _build_ml_payload(
    *,
    table_options: list[dict[str, str]],
    selected_table: str,
    selected_tables: list[str],
    selected_table_label: str,
    selected_cause: str,
    selected_object_category: str,
    temperature: str,
    days_ahead: int,
    selected_history_window: str,
    option_catalog: dict[str, list[dict[str, str]]],
    filtered_records_count: int,
    metadata_items: list[dict[str, Any]],
    preload_notes: list[str],
    source_table_notes: list[str],
    source_tables: list[str],
    daily_history: list[dict[str, Any]],
    ml_result: dict[str, Any],
    scenario_temperature: Any,
    temperature_quality: dict[str, Any],
) -> dict[str, Any]:
    appg_series = compute_appg_series(
        ml_result.get('forecast_rows', []),
        daily_history,
        current_date_key='date',
        current_value_key='forecast_value',
        history_date_key='date',
        history_value_key='count',
    )
    summary = _build_summary(
        selected_table=selected_table,
        selected_table_label=selected_table_label,
        selected_cause=selected_cause,
        selected_object_category=selected_object_category,
        daily_history=daily_history,
        filtered_records_count=filtered_records_count,
        ml_result=ml_result,
        history_window=selected_history_window,
        scenario_temperature=scenario_temperature,
    )
    return {
        'generated_at': _format_datetime(datetime.now()),
        'has_data': filtered_records_count > 0,
        'model_description': ML_PREDICTIVE_BLOCK_DESCRIPTION,
        'summary': summary,
        'quality_assessment': _build_quality_assessment(ml_result),
        'features': _build_feature_cards_with_quality(metadata_items, temperature_quality=temperature_quality),
        'charts': {
            'importance': _build_importance_chart(
                ml_result.get('feature_importance', []),
                note=str(ml_result.get('feature_importance_note') or '').strip(),
            ),
        },
        'appg_series': appg_series,
        'appg_period_series': [],
        'compare_series': {},
        'forecast_rows': ml_result.get('forecast_rows', []),
        'feature_importance': ml_result.get('feature_importance', []),
        'notes': _compact_ui_notes(
            source_table_notes
            + _build_notes(
                preload_notes,
                metadata_items,
                filtered_records_count,
                daily_history,
                ml_result,
                scenario_temperature,
                source_tables,
            )
        ),
        'filters': {
            'table_name': selected_table,
            'table_names': selected_tables,
            'cause': selected_cause,
            'object_category': selected_object_category,
            'forecast_days': str(days_ahead),
            'available_tables': table_options,
            'available_years': _extract_available_years(table_options, daily_history),
            'available_causes': option_catalog['causes'],
            'available_object_categories': option_catalog['object_categories'],
        },
    }


def _empty_ml_model_data(
    table_options: list[dict[str, str]],
    selected_table: str,
    selected_tables: list[str],
    selected_table_label: str,
    forecast_days: int,
    temperature: str,
    history_window: str,
) -> dict[str, Any]:
    empty_result = _empty_ml_result('Недостаточно данных для обучения модели.')
    return {
        'generated_at': _format_datetime(datetime.now()),
        'has_data': False,
        'model_description': '',
        'summary': {
            'selected_table_label': selected_table_label or ('Все таблицы' if selected_table == 'all' else (selected_table or 'Нет таблицы')),
            'slice_label': 'Все пожары',
            'hero_summary': 'После расчета здесь появится краткий вывод по ожидаемому числу пожаров на ближайшие даты.',
            'history_period_label': 'Нет данных',
            'history_window_label': _history_window_label(history_window),
            'model_label': MODEL_NAME,
            'count_model_label': 'Регрессия Пуассона',
            'event_model_label': 'Не обучен',
            'event_backtest_model_label': 'Не показан',
            'backtest_method_label': 'Проверка на истории не выполнена',
            'fires_count_display': '0',
            'history_days_display': '0',
            'forecast_days_display': str(forecast_days),
            'last_observed_date': '-',
            'count_mae_display': '-',
            'count_rmse_display': '-',
            'count_smape_display': 'вЂ”',
            'count_poisson_deviance_display': '-',
            'baseline_count_mae_display': '-',
            'baseline_count_rmse_display': '-',
            'baseline_count_smape_display': 'вЂ”',
            'heuristic_count_mae_display': '-',
            'heuristic_count_rmse_display': '-',
            'heuristic_count_smape_display': 'вЂ”',
            'heuristic_count_poisson_deviance_display': '-',
            'mae_vs_baseline_display': '-',
            'brier_display': 'вЂ”',
            'baseline_brier_display': 'вЂ”',
            'heuristic_brier_display': 'вЂ”',
            'roc_auc_display': 'вЂ”',
            'baseline_roc_auc_display': 'вЂ”',
            'heuristic_roc_auc_display': 'вЂ”',
            'f1_display': 'вЂ”',
            'baseline_f1_display': 'вЂ”',
            'heuristic_f1_display': 'вЂ”',
            'log_loss_display': 'вЂ”',
            'top_feature_label': '-',
            'temperature_scenario_display': temperature.strip() or 'историческая температура',
            'predicted_total_display': '0',
            'average_expected_count_display': '0',
            'peak_expected_count_display': '0',
            'peak_expected_count_day_display': '-',
            'elevated_risk_days_display': '0',
            'average_event_probability_display': 'вЂ”',
            'peak_event_probability_display': 'вЂ”',
            'peak_event_probability_day_display': '-',
            'event_probability_enabled': False,
            'event_backtest_available': False,
        },
        'quality_assessment': _build_quality_assessment(empty_result),
        'features': [],
        'charts': {
            'importance': _build_importance_chart([], note=''),
        },
        'appg_series': [],
        'appg_period_series': [],
        'compare_series': {},
        'forecast_rows': [],
        'feature_importance': [],
        'notes': [],
        'filters': {
            'table_name': selected_table,
            'table_names': selected_tables,
            'cause': 'all',
            'object_category': 'all',
            'forecast_days': str(forecast_days),
            'available_tables': table_options,
            'available_years': _extract_available_years_from_table_options(table_options),
            'available_causes': [{'value': 'all', 'label': 'Все причины'}],
            'available_object_categories': [{'value': 'all', 'label': 'Все категории'}],
        },
    }



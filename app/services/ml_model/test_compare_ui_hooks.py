from __future__ import annotations

from pathlib import Path


def test_compare_filters_sent_to_api() -> None:
    source = Path("app/static/js/ml_model_api.js").read_text(encoding="utf-8")
    assert "var defaultMonth = String(new Date().getMonth() + 1);" in source
    assert "month: params.get('month') || defaultMonth" in source
    assert "/api/ml-compare-series" in source
    assert "fetchMlCompareSeriesViaJob" in source
    assert "Number(error.status) === 404" in source


def test_compare_chart_render_hook_present() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")
    assert "charts.renderCompareChart(compare, 'mlCompareChart'" in source
    assert "refreshCompareSeriesOnly" in source
    assert "var yearA = byId('mlYearAFilter')" in source
    assert "var yearB = byId('mlYearBFilter')" in source
    assert "filters.available_years" in source
    assert "filters.available_tables" in source
    assert "value.match(/(19\\d{2}|20\\d{2}|2100)/g)" in source
    assert "yearFromCompareA = parseYear(compare.year_a)" in source
    assert "yearFromCompareB = parseYear(compare.year_b)" in source
    assert "resolveYearPair(years" in source
    assert "['mlMonthFilter', 'mlYearAFilter', 'mlYearBFilter'" in source
    assert "refreshCompareSeriesOnly();" in source


def test_compare_request_uses_current_filters_not_hardcoded_all() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")
    assert "var filters = (currentData && currentData.filters) || {};" in source
    assert "table_name: tableName" in source
    assert "table_names: tableNames" in source
    assert "cause: cause" in source
    assert "object_category: objectCategory" in source
    assert "year_a: resolved.yearA" in source
    assert "year_b: resolved.yearB" in source


def test_year_options_do_not_use_synthetic_range() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")
    assert "for (var year = 2026; year >= 1990; year -= 1)" not in source


def test_compare_chart_function_exists() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "function renderCompareChart(compareSeries, chartId, fallbackId, summaryId)" in source
    assert "var historyHasData = data.history_has_data === true;" in source
    assert "if (!rows.length || (!aPoints && !bPoints))" in source
    assert "renderFallback(chartNode, fallbackNode, 'Нет данных для сравнения выбранных лет за выбранный месяц.');" in source


def test_compare_chart_hides_fallback_when_history_available() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "setChartEmptyState(chartNode, false);" in source
    assert "fallbackNode.classList.add('is-hidden');" in source
    assert "fallbackNode.style.display = 'none';" in source


def test_compare_chart_can_render_without_history_flag_if_rows_have_points() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "var rows = Array.isArray(data.rows) ? data.rows : [];" in source
    assert "var aPoints = rows.filter(function (row) { return row && row.a_value != null && !isNaN(Number(row.a_value)); }).length;" in source
    assert "var bPoints = rows.filter(function (row) { return row && row.b_value != null && !isNaN(Number(row.b_value)); }).length;" in source
    assert "if (!rows.length || (!aPoints && !bPoints))" in source


def test_compare_chart_marks_ml_in_legend_and_summary() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "modes.year_a === 'ml'" in source
    assert "modes.year_b === 'ml'" in source
    assert "обе линии построены ML" in source

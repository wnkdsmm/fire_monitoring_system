from __future__ import annotations

from pathlib import Path


def test_compare_filters_sent_to_api() -> None:
    source = Path("app/static/js/ml_model_api.js").read_text(encoding="utf-8")
    assert "var defaultMonth = String(new Date().getMonth() + 1);" in source
    assert "month: params.get('month') || defaultMonth" in source
    assert "year_a: params.get('year_a') || '2025'" in source
    assert "year_b: params.get('year_b') || '2024'" in source
    assert "/api/ml-compare-series" in source


def test_compare_chart_render_hook_present() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")
    assert "charts.renderCompareChart(compareSeries, 'mlCompareChart'" in source
    assert "refreshCompareSeriesOnly" in source
    assert "year_a: yearAValue" in source
    assert "year_b: yearBValue" in source
    assert "filters.available_years" in source
    assert "nowYear - 10" not in source
    assert "response year mismatch" in source
    assert "keepUserCompareSelection" in source
    assert "['mlMonthFilter', 'mlYearAFilter', 'mlYearBFilter']" in source
    assert "refreshCompareSeriesOnly();" in source
    assert "formCompareYearA || requestCompare.year_a || compareYearA" in source
    assert "formCompareYearB || requestCompare.year_b || compareYearB" in source


def test_compare_chart_function_exists() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "function renderCompareChart(compareSeries, chartId, fallbackId, summaryId)" in source
    assert "var historyHasData = data.history_has_data === true;" in source
    assert "if (!historyHasData)" in source
    assert "renderFallback(chartNode, fallbackNode, 'Нет данных для сравнения выбранных лет за выбранный месяц.');" in source


def test_compare_chart_hides_fallback_when_history_available() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "setChartEmptyState(chartNode, false);" in source
    assert "fallbackNode.classList.add('is-hidden');" in source
    assert "fallbackNode.style.display = 'none';" in source

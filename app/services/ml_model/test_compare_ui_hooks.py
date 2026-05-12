from __future__ import annotations

from pathlib import Path


def test_compare_filters_sent_to_api() -> None:
    source = Path("app/static/js/ml_model_api.js").read_text(encoding="utf-8")
    assert "year_a: params.get('year_a') || ''" in source
    assert "year_b: params.get('year_b') || ''" in source


def test_compare_chart_render_hook_present() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")
    assert "charts.renderCompareChart(compareSeries, 'mlCompareChart'" in source
    assert "year_a: yearAValue" in source
    assert "year_b: yearBValue" in source
    assert "filters.available_years" in source
    assert "nowYear - 10" not in source


def test_compare_chart_function_exists() -> None:
    source = Path("app/static/js/ml_model_charts.js").read_text(encoding="utf-8")
    assert "function renderCompareChart(compareSeries, chartId, fallbackId, summaryId)" in source

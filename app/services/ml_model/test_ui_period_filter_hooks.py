from __future__ import annotations

from pathlib import Path


def test_ml_ui_change_handler_triggers_compare_filters() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")

    assert "['mlMonthFilter', 'mlYearAFilter', 'mlYearBFilter']" in source
    assert "refreshCompareSeriesOnly" in source


def test_ml_ui_renders_compare_chart_only() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")

    assert "charts.renderCompareChart(compare, 'mlCompareChart'" in source
    assert "renderAppgChart" not in source

from __future__ import annotations

from pathlib import Path


def test_ml_ui_change_handler_triggers_period_and_slice_filters() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")

    assert "targetName === 'table_names'" in source
    assert "}, 400);" in source
    assert "targetName === 'year'" in source
    assert "targetName === 'month'" in source
    assert "targetName === 'cause'" in source
    assert "targetName === 'object_category'" in source


def test_ml_ui_appg_chart_uses_latest_payload_series() -> None:
    source = Path("app/static/js/ml_model_render.js").read_text(encoding="utf-8")

    assert "appgGraphSeries = (Array.isArray(data.appg_period_series) && data.appg_period_series.length)" in source
    assert "charts.renderAppgChart(appgGraphSeries || [], 'mlAppgChart'" in source

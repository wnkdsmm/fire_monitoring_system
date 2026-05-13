from __future__ import annotations

import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.routes.api_ml_model import ml_compare_series_endpoint
from app.routes import pages as pages_routes
from fastapi.responses import HTMLResponse


def _build_compare_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/ml-compare-series",
            "headers": [],
            "query_string": b"",
        }
    )


def _build_page_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/ml-model",
            "headers": [],
            "query_string": b"",
        }
    )


class MlPeriodApiIntegrationTests(unittest.TestCase):
    def test_compare_endpoint_accepts_valid_params(self) -> None:
        def _fake_compare(**_kwargs):
            return {"compare_series": {"month": 5, "year_a": 2025, "year_b": 2024, "rows": []}, "filters": {}}

        def _fake_run_session_json_action(_request, action):
            return action("session-compare")

        with (
            patch("app.routes.api_ml_model.get_ml_compare_series_data", side_effect=_fake_compare),
            patch("app.routes.api_ml_model.run_session_json_action", side_effect=_fake_run_session_json_action),
        ):
            result = ml_compare_series_endpoint(
                _build_compare_request(),
                payload={"table_name": "fires", "month": 5, "year_a": 2025, "year_b": 2024},
            )

        self.assertEqual(result["status"], "completed")
        self.assertIn("result", result)

    def test_compare_endpoint_requires_month_and_years(self) -> None:
        response = ml_compare_series_endpoint(
            _build_compare_request(),
            payload={"table_name": "fires", "month": "", "year_a": 2025, "year_b": ""},
        )
        self.assertEqual(response.status_code, 400)

    def test_compare_endpoint_returns_history_has_data_true_when_points_exist(self) -> None:
        def _fake_compare(**_kwargs):
            return {
                "compare_series": {
                    "month": 5,
                    "year_a": 2020,
                    "year_b": 2018,
                    "rows": [{"day": 1, "a_value": 2.0, "b_value": 1.0, "a_source": "fact", "b_source": "ml"}],
                    "history_has_data": True,
                },
                "filters": {},
            }

        def _fake_run_session_json_action(_request, action):
            return action("session-compare")

        with (
            patch("app.routes.api_ml_model.get_ml_compare_series_data", side_effect=_fake_compare),
            patch("app.routes.api_ml_model.run_session_json_action", side_effect=_fake_run_session_json_action),
        ):
            result = ml_compare_series_endpoint(
                _build_compare_request(),
                payload={"table_name": "fires", "month": 5, "year_a": 2020, "year_b": 2018},
            )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["result"]["compare_series"]["history_has_data"])

    def test_ml_model_page_route_renders_without_exception(self) -> None:
        captured: dict[str, object] = {}

        def _fake_render_context_page(request, template_name, **kwargs):
            captured["template_name"] = template_name
            captured["context_name"] = kwargs.get("context_name")
            return HTMLResponse("<html><body>ok</body></html>", status_code=200)

        with (
            patch.object(pages_routes, "get_ml_model_shell_context", return_value={"initial_data": {}, "generated_at": "", "plotly_js": "", "has_data": True}),
            patch.object(pages_routes, "render_context_page", side_effect=_fake_render_context_page),
        ):
            response = pages_routes.ml_model_page(_build_page_request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured.get("template_name"), "ml_model.html")
        self.assertEqual(captured.get("context_name"), "ml_model")


if __name__ == "__main__":
    unittest.main()

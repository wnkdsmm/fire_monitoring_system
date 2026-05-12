from __future__ import annotations

import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.routes.api_ml_model import ml_compare_series_endpoint, start_ml_model_job_endpoint
from app.services.ml_model import jobs as ml_jobs
from app.routes import pages as pages_routes
from fastapi.responses import HTMLResponse


def _build_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/ml-model-jobs",
            "headers": [],
            "query_string": b"",
        }
    )

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
    def tearDown(self) -> None:
        ml_jobs._ML_JOB_IDS_BY_CACHE_KEY.clear()

    def test_endpoint_accepts_valid_year_month(self) -> None:
        captured: dict[str, object] = {}

        def _fake_start_ml_model_job(**kwargs):
            captured.update(kwargs)
            return {"status": "pending", "job_id": "job-1"}

        def _fake_run_session_json_action(_request, action):
            return action("session-1")

        with (
            patch("app.routes.api_ml_model.start_ml_model_job", side_effect=_fake_start_ml_model_job),
            patch("app.routes.api_ml_model.run_session_json_action", side_effect=_fake_run_session_json_action),
        ):
            result = start_ml_model_job_endpoint(
                _build_request(),
                payload={"table_name": "fires", "year": 2025, "month": 5},
            )

        self.assertEqual(result["status"], "pending")
        self.assertEqual(captured["year"], 2025)
        self.assertEqual(captured["month"], 5)

    def test_endpoint_accepts_compare_years(self) -> None:
        captured: dict[str, object] = {}

        def _fake_start_ml_model_job(**kwargs):
            captured.update(kwargs)
            return {"status": "pending", "job_id": "job-2"}

        def _fake_run_session_json_action(_request, action):
            return action("session-2")

        with (
            patch("app.routes.api_ml_model.start_ml_model_job", side_effect=_fake_start_ml_model_job),
            patch("app.routes.api_ml_model.run_session_json_action", side_effect=_fake_run_session_json_action),
        ):
            result = start_ml_model_job_endpoint(
                _build_request(),
                payload={"table_name": "fires", "month": 5, "year_a": 2025, "year_b": 2024},
            )

        self.assertEqual(result["status"], "pending")
        self.assertEqual(captured["year_a"], 2025)
        self.assertEqual(captured["year_b"], 2024)

    def test_endpoint_rejects_invalid_year_month(self) -> None:
        response = start_ml_model_job_endpoint(
            _build_request(),
            payload={"table_name": "fires", "year": "abc", "month": 13},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error_message", response.body.decode("utf-8"))

    def test_new_year_triggers_background_calculation(self) -> None:
        session_id = "ml-period-new-year"
        request_state = {"cache_key": ("ml", "fires", "2027-01-01")}

        with (
            patch.object(ml_jobs, "_build_ml_request_state", return_value=request_state),
            patch.object(ml_jobs, "_cache_get", return_value=None),
            patch.object(ml_jobs._ML_JOB_EXECUTOR, "submit", return_value=None) as submit_mock,
        ):
            payload = ml_jobs.start_ml_model_job(
                session_id=session_id,
                table_name="fires",
                year=2027,
                month=1,
            )

        self.assertEqual(payload["status"], "pending")
        submit_mock.assert_called_once()

    def test_old_year_uses_cached_payload_without_recalculation(self) -> None:
        session_id = "ml-period-old-year"
        request_state = {"cache_key": ("ml", "fires", "2025-05-01")}
        cached_payload = {
            "summary": {"selected_table_label": "fires"},
            "quality_assessment": {},
            "filters": {"table_name": "fires"},
            "notes": [],
            "charts": {},
            "forecast_rows": [],
            "feature_importance": [],
            "features": [],
            "appg_series": [],
        }

        with (
            patch.object(ml_jobs, "_build_ml_request_state", return_value=request_state),
            patch.object(ml_jobs, "_cache_get", return_value=cached_payload),
            patch.object(ml_jobs._ML_JOB_EXECUTOR, "submit", return_value=None) as submit_mock,
        ):
            payload = ml_jobs.start_ml_model_job(
                session_id=session_id,
                table_name="fires",
                year=2025,
                month=5,
            )

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["result"]["summary"]["selected_table_label"], "fires")
        submit_mock.assert_not_called()

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

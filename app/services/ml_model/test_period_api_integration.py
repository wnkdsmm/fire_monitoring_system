from __future__ import annotations

import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.routes.api_ml_model import start_ml_model_job_endpoint
from app.services.ml_model import jobs as ml_jobs


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


if __name__ == "__main__":
    unittest.main()

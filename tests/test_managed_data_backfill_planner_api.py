from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedDataBackfillPlannerApiTest(unittest.TestCase):
    def test_docs_list_backfill_planner_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/backfill-plan", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-backfill-plan", paths)

    def test_get_backfill_plan_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_backfill_planner_report",
            return_value={
                "status": "blocked",
                "production_cache_write_allowed": False,
                "feature_store_v12_allowed": False,
                "rows_fetched": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/backfill-plan", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["production_cache_write_allowed"])
        self.assertFalse(payload["feature_store_v12_allowed"])

    def test_post_refresh_rejects_execution_paths_or_secrets_and_never_runs_downstream(self) -> None:
        report = {
            "status": "ready",
            "production_cache_write_allowed": False,
            "feature_store_v12_allowed": False,
            "rows_fetched": False,
        }
        with patch("sn_futures.api.terminal_api.write_backfill_planner_report", return_value=report, create=True) as planner, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12, patch("sn_futures.api.terminal_api.build_training_dataset_v12") as build_td, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate:
            secret_status, secret_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-backfill-plan",
                method="POST",
                body=json.dumps({"token": "managed-secret-token", "Authorization": "Bearer managed-secret-token"}),
            )
            execute_status, execute_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-backfill-plan",
                method="POST",
                body=json.dumps({"execute": True, "fetch": True, "production_cache": True, "build_v12": True}),
            )
            output_status, output_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-backfill-plan",
                method="POST",
                body=json.dumps({"output_path": "outputs/fundamentals/managed_fundamentals.json"}),
            )

        self.assertEqual(secret_status, 400)
        self.assertIn("raw_secret_input_forbidden", json.dumps(secret_payload, ensure_ascii=False))
        self.assertEqual(execute_status, 400)
        self.assertIn("backfill_execution_forbidden", json.dumps(execute_payload, ensure_ascii=False))
        self.assertEqual(output_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(output_payload, ensure_ascii=False))
        planner.assert_not_called()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        candidate.assert_not_called()

    def test_post_refresh_generates_report_without_fetch_or_v12(self) -> None:
        report = {
            "status": "blocked",
            "production_cache_write_allowed": False,
            "feature_store_v12_allowed": False,
            "rows_fetched": False,
            "historical_backfill_executed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.write_backfill_planner_report", return_value=report, create=True) as planner, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12:
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/refresh-backfill-plan", method="POST", body=json.dumps({}))

        self.assertEqual(status, 200)
        self.assertFalse(payload["production_cache_write_allowed"])
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["rows_fetched"])
        planner.assert_called_once()
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()

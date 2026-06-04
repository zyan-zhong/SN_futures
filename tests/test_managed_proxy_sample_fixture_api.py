from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxySampleFixtureApiTest(unittest.TestCase):
    def test_docs_list_sample_fixture_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/sample-fixture", paths)
        self.assertIn("/api/terminal/managed-proxy/import-sample-fixture", paths)
        self.assertIn("/api/terminal/managed-proxy/run-sample-fixture-contract-tests", paths)

    def test_get_sample_fixture_report_is_sanitized(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_sample_fixture_report",
            return_value={
                "status": "ready",
                "row_count": 2,
                "sample_data_used": True,
                "production_eligible": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/sample-fixture", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["feature_store_v12_allowed"])

    def test_post_sample_fixture_ignores_raw_token_body_and_does_not_run_downstream_tasks(self) -> None:
        report = {
            "status": "ready",
            "row_count": 2,
            "schema_contract_status": "ready",
            "pit_replay_status": "ready",
            "data_quality_status": "pass",
            "sample_data_used": True,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch(
            "sn_futures.api.terminal_api.run_fixture_contract_tests",
            return_value=report,
            create=True,
        ) as run_fixture, patch("sn_futures.api.terminal_api.build_feature_store_v12") as build_v12, patch(
            "sn_futures.api.terminal_api.build_training_dataset_v12"
        ) as build_td, patch("sn_futures.api.terminal_api.run_candidate_v12_research") as run_candidate:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/run-sample-fixture-contract-tests",
                method="POST",
                body=json.dumps({"token": "managed-secret-token", "Authorization": "Bearer managed-secret-token"}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertNotIn("managed-secret-token", json.dumps(payload, ensure_ascii=False))
        run_fixture.assert_called_once_with()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        run_candidate.assert_not_called()


if __name__ == "__main__":
    unittest.main()

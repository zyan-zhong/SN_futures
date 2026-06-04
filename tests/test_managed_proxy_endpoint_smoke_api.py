from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxyEndpointSmokeApiTest(unittest.TestCase):
    def test_docs_list_endpoint_smoke_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/endpoint-smoke", paths)
        self.assertIn("/api/terminal/managed-proxy/run-endpoint-smoke", paths)

    def test_get_endpoint_smoke_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_endpoint_smoke_report",
            return_value={
                "status": "blocked",
                "auth_status": "not_run",
                "endpoint_reachable": False,
                "raw_rows_persisted": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/endpoint-smoke", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["raw_rows_persisted"])

    def test_post_endpoint_smoke_ignores_raw_token_body_and_does_not_run_downstream_tasks(self) -> None:
        report = {
            "status": "pass",
            "auth_status": "pass",
            "endpoint_reachable": True,
            "raw_rows_persisted": False,
            "managed_data_cache_updated": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.run_endpoint_smoke_test", return_value=report, create=True) as smoke, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12, patch("sn_futures.api.terminal_api.build_training_dataset_v12") as build_td, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/run-endpoint-smoke",
                method="POST",
                body=json.dumps({"token": "managed-secret-token", "Authorization": "Bearer managed-secret-token"}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pass")
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertNotIn("managed-secret-token", json.dumps(payload, ensure_ascii=False))
        smoke.assert_called_once_with()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        candidate.assert_not_called()


if __name__ == "__main__":
    unittest.main()

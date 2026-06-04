from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedDataProductionCacheGateApiTest(unittest.TestCase):
    def test_docs_list_production_cache_gate_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/production-cache-gate", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-production-cache-gate", paths)
        self.assertIn("/api/terminal/managed-proxy/build-production-cache-dry-run", paths)

    def test_get_production_cache_gate_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_production_cache_gate_report",
            return_value={
                "status": "blocked",
                "production_cache_write_allowed": False,
                "production_cache_written": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/production-cache-gate", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["production_cache_write_allowed"])
        self.assertFalse(payload["production_cache_written"])
        self.assertFalse(payload["feature_store_v12_allowed"])

    def test_refresh_rejects_secrets_paths_or_execution_requests(self) -> None:
        with patch("sn_futures.api.terminal_api.build_production_cache_gate_report", create=True) as gate, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12, patch("sn_futures.api.terminal_api.build_training_dataset_v12") as build_td, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate:
            secret_status, secret_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-production-cache-gate",
                method="POST",
                body=json.dumps({"token": "raw-token", "Authorization": "Bearer raw-token"}),
            )
            output_status, output_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-production-cache-gate",
                method="POST",
                body=json.dumps({"production_cache_path": "outputs/fundamentals/managed_fundamentals.json"}),
            )
            execute_status, execute_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-production-cache-gate",
                method="POST",
                body=json.dumps({"write": True, "execute": True, "build_v12": True, "train": True, "active": True, "prediction": True}),
            )

        self.assertEqual(secret_status, 400)
        self.assertIn("raw_secret_input_forbidden", json.dumps(secret_payload, ensure_ascii=False))
        self.assertEqual(output_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(output_payload, ensure_ascii=False))
        self.assertEqual(execute_status, 400)
        self.assertIn("production_cache_write_forbidden", json.dumps(execute_payload, ensure_ascii=False))
        gate.assert_not_called()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        candidate.assert_not_called()

    def test_dry_run_endpoint_generates_report_without_cache_write_or_v12(self) -> None:
        report = {
            "status": "blocked",
            "production_cache_write_allowed": False,
            "production_cache_written": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.build_production_cache_gate_report", return_value=report, create=True) as gate, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/build-production-cache-dry-run",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["production_cache_write_allowed"])
        self.assertFalse(payload["production_cache_written"])
        self.assertFalse(payload["feature_store_v12_allowed"])
        gate.assert_called_once()
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()

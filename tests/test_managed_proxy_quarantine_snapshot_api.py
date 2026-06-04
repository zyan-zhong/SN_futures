from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxyQuarantineSnapshotApiTest(unittest.TestCase):
    def test_docs_list_quarantine_snapshot_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/quarantine-snapshot", paths)
        self.assertIn("/api/terminal/managed-proxy/pull-quarantine-snapshot", paths)

    def test_get_quarantine_snapshot_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_quarantine_snapshot_report",
            return_value={
                "status": "blocked",
                "snapshot_pulled": False,
                "raw_rows_persisted": False,
                "managed_cache_updated": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/quarantine-snapshot", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["snapshot_pulled"])

    def test_post_quarantine_snapshot_rejects_raw_token_or_custom_output_path_and_never_runs_downstream(self) -> None:
        with patch("sn_futures.api.terminal_api.pull_managed_proxy_quarantine_snapshot", return_value={"status": "ready"}, create=True) as pull, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12, patch("sn_futures.api.terminal_api.build_training_dataset_v12") as build_td, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate:
            token_status, token_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/pull-quarantine-snapshot",
                method="POST",
                body=json.dumps({"token": "managed-secret-token", "Authorization": "Bearer managed-secret-token"}),
            )
            path_status, path_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/pull-quarantine-snapshot",
                method="POST",
                body=json.dumps({"output_path": "outputs/fundamentals/managed_fundamentals.json"}),
            )

        self.assertEqual(token_status, 400)
        self.assertIn("raw_secret_input_forbidden", json.dumps(token_payload, ensure_ascii=False))
        self.assertEqual(path_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(path_payload, ensure_ascii=False))
        pull.assert_not_called()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        candidate.assert_not_called()

    def test_post_quarantine_snapshot_allows_small_row_request_only(self) -> None:
        report = {
            "status": "ready",
            "snapshot_pulled": True,
            "snapshot_row_count": 1,
            "raw_rows_persisted": False,
            "managed_cache_updated": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.pull_managed_proxy_quarantine_snapshot", return_value=report, create=True) as pull:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/pull-quarantine-snapshot",
                method="POST",
                body=json.dumps({"requested_rows": 1}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["feature_store_v12_allowed"])
        pull.assert_called_once_with(requested_rows=1)


if __name__ == "__main__":
    unittest.main()

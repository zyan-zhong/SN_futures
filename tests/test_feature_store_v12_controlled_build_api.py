from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class FeatureStoreV12ControlledBuildApiTest(unittest.TestCase):
    def test_docs_list_controlled_build_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/feature-store/v12-controlled-build", paths)
        self.assertIn("/api/terminal/feature-store/run-v12-controlled-build", paths)

    def test_get_returns_latest_controlled_build_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_v12_controlled_build_report",
            return_value={"status": "blocked", "build_executed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/feature-store/v12-controlled-build", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["build_executed"])

    def test_run_forbids_secrets_paths_force_and_upstream_build_requests(self) -> None:
        with patch("sn_futures.api.terminal_api.execute_feature_store_v12_controlled_build", create=True) as executor:
            cases = [
                ({"token": "raw", "Authorization": "Bearer raw"}, "raw_secret_input_forbidden"),
                ({"output_path": "C:/tmp/feature_store.csv"}, "custom_output_path_forbidden"),
                ({"force": True}, "force_controlled_build_forbidden"),
                ({"build_missing": True}, "upstream_auto_build_forbidden"),
                ({"training_dataset": True, "candidate": True, "promotion": True, "active": True, "prediction": True}, "downstream_action_forbidden"),
            ]
            for body, expected_error in cases:
                status, payload = handle_terminal_api(
                    "/api/terminal/feature-store/run-v12-controlled-build",
                    method="POST",
                    body=json.dumps(body),
                )
                self.assertEqual(status, 400)
                self.assertIn(expected_error, json.dumps(payload, ensure_ascii=False))

        executor.assert_not_called()


if __name__ == "__main__":
    unittest.main()

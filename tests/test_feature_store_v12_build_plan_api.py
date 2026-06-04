from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class FeatureStoreV12BuildPlanApiTest(unittest.TestCase):
    def test_docs_list_v12_build_plan_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/feature-store/v12-build-plan", paths)
        self.assertIn("/api/terminal/feature-store/refresh-v12-build-plan", paths)

    def test_get_returns_latest_build_plan(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_v12_build_plan_report",
            return_value={"status": "blocked", "feature_store_v12_build_executed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/feature-store/v12-build-plan", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["feature_store_v12_build_executed"])

    def test_refresh_forbids_secrets_paths_and_real_build_requests(self) -> None:
        with patch("sn_futures.api.terminal_api.write_v12_build_plan_report", create=True) as plan, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12:
            secret_status, secret_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-build-plan",
                method="POST",
                body=json.dumps({"token": "raw", "Authorization": "Bearer raw"}),
            )
            path_status, path_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-build-plan",
                method="POST",
                body=json.dumps({"output_path": "outputs/feature_store/v12/feature_store.csv"}),
            )
            build_status, build_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-build-plan",
                method="POST",
                body=json.dumps({"build_v12": True, "training": True, "active": True, "prediction": True}),
            )

        self.assertEqual(secret_status, 400)
        self.assertIn("raw_secret_input_forbidden", json.dumps(secret_payload, ensure_ascii=False))
        self.assertEqual(path_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(path_payload, ensure_ascii=False))
        self.assertEqual(build_status, 400)
        self.assertIn("v12_build_forbidden", json.dumps(build_payload, ensure_ascii=False))
        plan.assert_not_called()
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()

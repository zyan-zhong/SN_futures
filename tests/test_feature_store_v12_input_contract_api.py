from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class FeatureStoreV12InputContractApiTest(unittest.TestCase):
    def test_docs_list_v12_input_contract_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/feature-store/v12-input-contract", paths)
        self.assertIn("/api/terminal/feature-store/refresh-v12-input-contract", paths)

    def test_get_returns_latest_contract(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_v12_input_contract_report",
            return_value={"status": "blocked", "input_contract_ready": False, "feature_store_v12_build_allowed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/feature-store/v12-input-contract", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["input_contract_ready"])
        self.assertFalse(payload["feature_store_v12_build_allowed"])

    def test_refresh_forbids_secrets_paths_or_build_requests(self) -> None:
        with patch("sn_futures.api.terminal_api.build_v12_input_contract_report", create=True) as contract, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12:
            secret_status, secret_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-input-contract",
                method="POST",
                body=json.dumps({"token": "raw", "Authorization": "Bearer raw"}),
            )
            path_status, path_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-input-contract",
                method="POST",
                body=json.dumps({"output_path": "outputs/feature_store/v12/feature_store.csv"}),
            )
            build_status, build_payload = handle_terminal_api(
                "/api/terminal/feature-store/refresh-v12-input-contract",
                method="POST",
                body=json.dumps({"build_v12": True, "training": True, "active": True, "prediction": True}),
            )

        self.assertEqual(secret_status, 400)
        self.assertIn("raw_secret_input_forbidden", json.dumps(secret_payload, ensure_ascii=False))
        self.assertEqual(path_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(path_payload, ensure_ascii=False))
        self.assertEqual(build_status, 400)
        self.assertIn("v12_build_forbidden", json.dumps(build_payload, ensure_ascii=False))
        contract.assert_not_called()
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()

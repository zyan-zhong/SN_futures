from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class ShadowOutputContractApiTest(unittest.TestCase):
    def test_docs_expose_shadow_output_contract_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/shadow-output-contract", paths)
        self.assertIn("/api/terminal/governance/refresh-shadow-output-contract", paths)
        self.assertIn("/api/terminal/governance/build-shadow-output-dry-run", paths)

    def test_get_shadow_output_contract_is_report_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_shadow_output_contract_report",
            return_value={
                "status": "blocked",
                "shadow_output_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/governance/shadow-output-contract", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["shadow_output_allowed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_build_shadow_output_dry_run_forces_contract_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_shadow_output_dry_run_artifact",
            return_value={
                "status": "pass",
                "dry_run_artifact_created": True,
                "synthetic_contract_only": True,
                "customer_prediction_generated": False,
                "active_updated": False,
                "training_invoked": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/build-shadow-output-dry-run",
                method="POST",
                body=json.dumps({"customer_output_path": "outputs/customer_predictions"}),
            )

        self.assertEqual(status, 200)
        self.assertTrue(payload["synthetic_contract_only"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["training_invoked"])


if __name__ == "__main__":
    unittest.main()

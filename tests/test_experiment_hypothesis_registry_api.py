from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ExperimentHypothesisRegistryApiTest(unittest.TestCase):
    def test_docs_expose_hypothesis_registry_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/hypothesis-registry", paths)
        self.assertIn("/api/terminal/research/create-hypothesis-template", paths)
        self.assertIn("/api/terminal/research/refresh-anti-p-hacking-ledger", paths)

    def test_get_registry_reads_ledger_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_hypothesis_registry",
            return_value={"status": "empty", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/hypothesis-registry", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])

    def test_create_template_does_not_execute_experiment(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.create_hypothesis_template",
            return_value={"status": "open", "training_allowed": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/create-hypothesis-template",
                method="POST",
                body=json.dumps({"remediation_id": "cost_aware_thresholding"}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_allowed"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_ledger_does_not_train_or_publish(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_anti_p_hacking_ledger",
            return_value={"status": "empty", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-anti-p-hacking-ledger",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])


if __name__ == "__main__":
    unittest.main()

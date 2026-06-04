from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class EvidenceBundleApiTest(unittest.TestCase):
    def test_docs_expose_evidence_bundle_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/evidence-bundle", paths)
        self.assertIn("/api/terminal/research/refresh-evidence-bundle", paths)

    def test_get_evidence_bundle_reads_index_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_evidence_bundle",
            return_value={"status": "blocked", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/evidence-bundle", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])

    def test_refresh_evidence_bundle_writes_index_not_task_queue(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.write_evidence_bundle",
            return_value={"status": "blocked", "training_invoked": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-evidence-bundle",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

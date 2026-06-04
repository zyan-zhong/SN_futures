from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class EvidenceFreshnessApiTest(unittest.TestCase):
    def test_docs_expose_evidence_freshness_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/evidence-freshness", paths)
        self.assertIn("/api/terminal/research/refresh-evidence-freshness", paths)

    def test_get_evidence_freshness_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_evidence_freshness_report",
            return_value={"status": "blocked", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/evidence-freshness", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])

    def test_refresh_evidence_freshness_only_recomputes_audit(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_evidence_freshness_report",
            return_value={"status": "blocked", "training_invoked": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-evidence-freshness",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

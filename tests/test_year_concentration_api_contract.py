from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class YearConcentrationApiContractTest(unittest.TestCase):
    def test_docs_expose_year_concentration_and_candidate_v10_report_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/year-concentration", paths)
        self.assertIn("/api/terminal/research/refresh-year-concentration", paths)
        self.assertIn("/api/terminal/research/candidate-v10-report", paths)
        self.assertIn("/api/terminal/research/candidate-v12-report", paths)

    def test_get_year_concentration_reads_summary_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_year_concentration_report",
            return_value={"status": "success", "training_invoked": False, "candidate_v10": {}},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/year-concentration", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])

    def test_refresh_year_concentration_calls_refresh_service_not_training_task(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_year_concentration",
            return_value={"status": "success", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-year-concentration",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])

    def test_candidate_v10_report_includes_year_evidence(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_candidate_v10_report",
            return_value={
                "candidate_version": "v10",
                "year_concentration_evidence": {"status": "fail", "passed": False},
                "manual_approval_recommended": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/candidate-v10-report", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["candidate_version"], "v10")
        self.assertIn("year_concentration_evidence", payload)
        self.assertFalse(payload["manual_approval_recommended"])


if __name__ == "__main__":
    unittest.main()

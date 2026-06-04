from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class CandidateV12ApiContractTest(unittest.TestCase):
    def test_docs_expose_candidate_v12_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/candidate-v12-report", paths)
        self.assertIn("/api/terminal/research/run-candidate-v12", paths)

    def test_get_candidate_v12_report_uses_v12_service(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_candidate_v12_report",
            return_value={"status": "blocked", "candidate_version": "v12", "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/candidate-v12-report", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["candidate_version"], "v12")
        self.assertFalse(payload["active_updated"])

    def test_run_candidate_v12_queues_research_only_task(self) -> None:
        with patch("sn_futures.api.terminal_api.run_candidate_v12_research", return_value={"status": "blocked"}, create=True), patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "candidate-v12-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }
            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v12",
                method="POST",
                body=json.dumps({"horizons": ["5d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v12")
        self.assertEqual(payload["payload"]["dataset_version"], "v12")
        self.assertEqual(payload["payload"]["feature_store_version"], "v12")
        self.assertFalse(payload["payload"].get("active_publish", True))
        self.assertFalse(payload["payload"].get("customer_prediction_generated", True))


if __name__ == "__main__":
    unittest.main()

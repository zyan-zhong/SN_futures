from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ResearchDecisionBoardApiContractTest(unittest.TestCase):
    def test_docs_expose_decision_board_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/decision-board", paths)
        self.assertIn("/api/terminal/research/refresh-decision-board", paths)

    def test_get_decision_board_reads_board_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_research_decision_board",
            return_value={"status": "blocked", "training_invoked": False, "active_publish_allowed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/decision-board", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_publish_allowed"])

    def test_refresh_decision_board_is_not_a_training_task(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_research_decision_board",
            return_value={"status": "blocked", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-decision-board",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])


if __name__ == "__main__":
    unittest.main()

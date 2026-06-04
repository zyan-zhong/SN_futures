from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class FrontendCandidateV10ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v10_task_endpoint(self) -> None:
        with patch("sn_futures.api.terminal_api.run_candidate_v10_research") as run_v10, patch("sn_futures.api.terminal_api.start_task") as start_task:
            run_v10.return_value = {"status": "blocked", "candidate_version": "v10", "active_updated": False}
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "train_candidate-v10-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v10",
                method="POST",
                body=json.dumps({"horizons": ["5d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v10")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_shows_candidate_v10_cpcv_research(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
        backtest_page = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")

        self.assertIn("runCandidateV10Research", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v10", terminal)
        self.assertIn("CandidateV10ResearchPayload", types)
        self.assertIn("candidate_v10 CPCV", research_page)
        self.assertIn("v10 vs v9", research_page)
        self.assertIn("regime-balanced dataset v10", research_page)
        self.assertIn("manual_approval_recommended", research_page)
        self.assertIn('<option value="v10">candidate_v10</option>', backtest_page)


if __name__ == "__main__":
    unittest.main()

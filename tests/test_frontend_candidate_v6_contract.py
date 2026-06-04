from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class FrontendCandidateV6ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v6_gated_research_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), \
            patch("sn_futures.api.terminal_api.run_candidate_v6_gated_research") as run_v6, \
            patch("sn_futures.api.terminal_api.start_task") as start_task:
            run_v6.return_value = {
                "status": "blocked",
                "candidate_version": "v6",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "train_candidate-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v6",
                method="POST",
                body=json.dumps({"horizons": ["1d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v6")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_exposes_candidate_v6_research_and_backtest_controls(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
        backtest_page = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")

        self.assertIn("runCandidateV6Research", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v6", terminal)
        self.assertIn("CandidateV6ResearchPayload", types)
        self.assertIn("candidate_v6", research_page)
        self.assertIn("v5 vs v6", research_page)
        self.assertIn("institutional validation", research_page)
        self.assertIn("promotion dry-run", research_page)
        self.assertIn("waiting for human approval", research_page)
        self.assertIn('<option value="v6">candidate_v6</option>', backtest_page)


if __name__ == "__main__":
    unittest.main()

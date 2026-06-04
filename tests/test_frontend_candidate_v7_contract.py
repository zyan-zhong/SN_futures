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


class FrontendCandidateV7ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v7_research_endpoint(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False),
            patch("sn_futures.api.terminal_api.run_candidate_v7_research") as run_v7,
            patch("sn_futures.api.terminal_api.start_task") as start_task,
        ):
            run_v7.return_value = {
                "status": "blocked",
                "candidate_version": "v7",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "train_candidate-v7-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v7",
                method="POST",
                body=json.dumps({"horizons": ["1d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v7")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_exposes_candidate_v7_research_and_backtest_controls(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
        backtest_page = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")

        self.assertIn("runCandidateV7Research", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v7", terminal)
        self.assertIn("CandidateV7ResearchPayload", types)
        self.assertIn("candidate_v7", research_page)
        self.assertIn("v6 vs v7", research_page)
        self.assertIn("cost pressure", research_page)
        self.assertIn("PBO", research_page)
        self.assertIn("DSR", research_page)
        self.assertIn("promotion dry-run", research_page)
        self.assertIn("waiting for human approval", research_page)
        self.assertIn('<option value="v7">candidate_v7</option>', backtest_page)


if __name__ == "__main__":
    unittest.main()

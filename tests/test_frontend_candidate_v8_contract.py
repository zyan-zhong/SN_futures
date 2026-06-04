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


class FrontendCandidateV8ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v8_stability_endpoint(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False),
            patch("sn_futures.api.terminal_api.run_candidate_v8_research") as run_v8,
            patch("sn_futures.api.terminal_api.start_task") as start_task,
        ):
            run_v8.return_value = {
                "status": "blocked",
                "candidate_version": "v8",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "train_candidate-v8-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v8",
                method="POST",
                body=json.dumps({"horizons": ["5d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v8")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_exposes_candidate_v8_stability_comparison(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
        backtest_page = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")

        self.assertIn("runCandidateV8Research", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v8", terminal)
        self.assertIn("CandidateV8ResearchPayload", types)
        self.assertIn("candidate_v8 stability", research_page)
        self.assertIn("v7 vs v8", research_page)
        self.assertIn("disabled horizons", research_page)
        self.assertIn("no-trade reasons", research_page)
        self.assertIn("still blocked", research_page)
        self.assertIn('<option value="v8">candidate_v8</option>', backtest_page)


if __name__ == "__main__":
    unittest.main()

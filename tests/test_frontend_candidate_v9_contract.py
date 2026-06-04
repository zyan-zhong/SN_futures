from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class FrontendCandidateV9ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v9_task_endpoint(self) -> None:
        with patch("sn_futures.api.terminal_api.run_candidate_v9_research") as run_v9, patch("sn_futures.api.terminal_api.start_task") as start_task:
            run_v9.return_value = {"status": "blocked", "candidate_version": "v9", "active_updated": False}
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "train_candidate-v9-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/run-candidate-v9",
                method="POST",
                body=json.dumps({"horizons": ["5d"]}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "train_candidate")
        self.assertEqual(payload["payload"]["candidate_version"], "v9")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_shows_candidate_v9_regime_neutral_research(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
        backtest_page = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")

        self.assertIn("runCandidateV9Research", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v9", terminal)
        self.assertIn("getCpcvValidationReport", terminal)
        self.assertIn("/api/terminal/research/cpcv-report", terminal)
        self.assertIn("CPCVValidationPayload", types)
        self.assertIn("CPCV multi-path validation", research_page)
        self.assertIn("CandidateV9ResearchPayload", types)
        self.assertIn("candidate_v9 regime-neutral", research_page)
        self.assertIn("v8 vs v9", research_page)
        self.assertIn("regime concentration", research_page)
        self.assertIn("trade quota", research_page)
        self.assertIn("可进入人工审批", research_page)
        self.assertIn('<option value="v9">candidate_v9</option>', backtest_page)


if __name__ == "__main__":
    unittest.main()

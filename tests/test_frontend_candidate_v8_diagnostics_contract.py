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


class FrontendCandidateV8DiagnosticsContractTest(unittest.TestCase):
    def test_terminal_api_exposes_candidate_v8_diagnostics_endpoint(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False),
            patch("sn_futures.api.terminal_api.build_candidate_v8_validation_diagnostics") as build_diag,
        ):
            build_diag.return_value = {
                "status": "success",
                "candidate_version": "v8",
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            status, payload = handle_terminal_api("/api/terminal/research/candidate-v8-diagnostics", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["candidate_version"], "v8")
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_frontend_exposes_candidate_v8_diagnostics_copy(self) -> None:
        terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("getCandidateV8Diagnostics", terminal)
        self.assertIn("/api/terminal/research/candidate-v8-diagnostics", terminal)
        self.assertIn("CandidateV8DiagnosticsPayload", types)
        self.assertIn("v8 failure attribution", research_page)
        self.assertIn("PBO source", research_page)
        self.assertIn("Regime concentration", research_page)
        self.assertIn("Reality Check gap", research_page)
        self.assertIn("v9 actions", research_page)


if __name__ == "__main__":
    unittest.main()

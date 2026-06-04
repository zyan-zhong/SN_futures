from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_decision_board_service import build_research_decision_board


class ManagedProxyReliabilityDecisionBoardTest(unittest.TestCase):
    def test_reliability_fail_blocks_managed_data_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / "managed_proxy_config_wizard_report.json").write_text(
                json.dumps({"status": "ready", "next_allowed_action": "configure_managed_proxy_endpoint_or_token"}),
                encoding="utf-8",
            )
            (diagnostics / "managed_proxy_setup_report.json").write_text(
                json.dumps({"status": "ready", "managed_proxy_health_allowed": True, "blocking_reasons": []}),
                encoding="utf-8",
            )
            (diagnostics / "managed_proxy_health.json").write_text(
                json.dumps({"status": "ready", "ready": True, "v12_allowed": True, "blocking_reasons": []}),
                encoding="utf-8",
            )
            (diagnostics / "managed_proxy_reliability_report.json").write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "canary_status": "server_error",
                        "circuit_breaker_status": "closed",
                        "blocking_reasons": ["managed_proxy_canary_5xx"],
                        "next_allowed_action": "fix_managed_proxy_reliability",
                    }
                ),
                encoding="utf-8",
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_managed_proxy_reliability")
        self.assertFalse(board["candidate_training_allowed"])
        self.assertIn("managed_proxy_reliability:managed_proxy_canary_5xx", board["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

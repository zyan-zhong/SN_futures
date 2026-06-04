from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_decision_board_service import build_research_decision_board  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ResearchDecisionBoardLockdownTest(unittest.TestCase):
    def test_real_lockdown_overrides_training_manual_approval_and_active_publish(self) -> None:
        tmp = _workspace_tmp("board-lockdown")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(
                output / "model_research" / "incident_drill_report.json",
                {
                    "status": "lockdown",
                    "generated_at": "2026-06-03T12:00:00",
                    "real_lockdown_state": {
                        "lockdown_triggered": True,
                        "lockdown_reasons": ["unauthorized_active_model_detected"],
                    },
                    "decision_board_override": {
                        "candidate_training_allowed": False,
                        "manual_approval_recommended": False,
                        "active_publish_allowed": False,
                    },
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "governance_lockdown")
        self.assertEqual(board["next_allowed_action"], "resolve_governance_incident")
        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("governance_lockdown:unauthorized_active_model_detected", board["blocking_reasons"])
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

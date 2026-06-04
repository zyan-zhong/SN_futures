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


class ResearchDecisionBoardManualApprovalTest(unittest.TestCase):
    def test_manual_approval_blocked_enters_board_and_blocks_recommendation(self) -> None:
        tmp = _workspace_tmp("board-manual-approval")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(
                output / "model_research" / "manual_approval_report.json",
                {
                    "status": "blocked_by_gates",
                    "approval_request_allowed": False,
                    "blocking_reasons": ["manual_approval_not_recommended"],
                    "active_write_allowed": False,
                    "customer_prediction_write_allowed": False,
                },
            )

            board = build_research_decision_board()

        self.assertEqual(board["manual_approval_summary"]["status"], "blocked_by_gates")
        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("manual_approval_workflow:manual_approval_not_recommended", board["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

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


class PromotionDryRunEvidenceDecisionBoardTest(unittest.TestCase):
    def test_blocked_promotion_dry_run_evidence_keeps_active_publish_disabled(self) -> None:
        tmp = _workspace_tmp("promotion-evidence-board")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "model_research" / "promotion_dry_run_evidence_report.json",
                {
                    "status": "blocked",
                    "candidate_version": "v12",
                    "requested_action": "promotion_dry_run_only",
                    "active_write_allowed": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                    "artifact_boundary_checks": {"active_model_json_absent": True},
                    "blocking_reasons": ["manual_approval_missing"],
                    "report_path": str(output / "model_research" / "promotion_dry_run_evidence_report.json"),
                },
            )
            board = build_research_decision_board()

        self.assertFalse(board["active_publish_allowed"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])
        self.assertEqual(board["promotion_dry_run_summary"]["status"], "blocked")
        self.assertFalse(board["promotion_dry_run_summary"]["active_publish_allowed"])
        self.assertIn("promotion_dry_run_evidence:manual_approval_missing", board["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

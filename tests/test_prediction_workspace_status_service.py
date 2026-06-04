from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.prediction_workspace_status_service import build_prediction_workspace_status  # noqa: E402


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


class PredictionWorkspaceStatusServiceTest(unittest.TestCase):
    def test_blocked_decision_board_keeps_prediction_workspace_blocked(self) -> None:
        tmp = _workspace_tmp("prediction-workspace-blocked")
        board_path = tmp / "outputs" / "model_research" / "research_decision_board.json"
        _write_json(
            board_path,
            {
                "status": "blocked",
                "current_research_state": "managed_data_blocked",
                "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                "candidate_training_allowed": False,
                "manual_approval_recommended": False,
                "active_publish_allowed": False,
                "blocking_reasons": ["managed_proxy_endpoint_or_token_missing"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
        )

        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status = build_prediction_workspace_status()

        self.assertEqual(status["status"], "blocked")
        self.assertEqual(status["prediction_status"], "blocked")
        self.assertEqual(status["current_research_state"], "managed_data_blocked")
        self.assertEqual(status["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")
        self.assertFalse(status["active_model_available"])
        self.assertFalse(status["prediction_generation_allowed"])
        self.assertFalse(status["active_publish_allowed"])
        self.assertFalse(status["customer_prediction_generated"])
        self.assertIn("manual_approval_recommended", status["required_gates"])
        self.assertIn("managed_proxy_endpoint_or_token_missing", status["blocking_reasons"])

    def test_active_model_or_customer_prediction_paths_are_reported_as_violations(self) -> None:
        tmp = _workspace_tmp("prediction-workspace-violation")
        board_path = tmp / "outputs" / "model_research" / "research_decision_board.json"
        _write_json(
            board_path,
            {
                "status": "blocked",
                "current_research_state": "governance_lockdown",
                "next_allowed_action": "resolve_governance_incident",
                "active_publish_allowed": False,
                "customer_prediction_generated": False,
            },
        )
        _write_json(tmp / "outputs" / "model_registry" / "active_model.json", {"unexpected": True})
        (tmp / "outputs" / "customer_predictions").mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status = build_prediction_workspace_status()

        self.assertEqual(status["status"], "violation")
        self.assertTrue(status["active_model_path_exists"])
        self.assertTrue(status["customer_predictions_path_exists"])
        self.assertIn("unexpected_active_model_artifact", status["blocking_reasons"])
        self.assertIn("unexpected_customer_predictions_artifact", status["blocking_reasons"])
        self.assertFalse(status["training_invoked"])
        self.assertFalse(status["active_updated"])
        self.assertFalse(status["customer_prediction_generated"])

    def test_missing_decision_board_is_incomplete_not_pass(self) -> None:
        tmp = _workspace_tmp("prediction-workspace-missing-board")

        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status = build_prediction_workspace_status()

        self.assertEqual(status["status"], "blocked")
        self.assertEqual(status["decision_board_status"], "missing")
        self.assertFalse(status["prediction_generation_allowed"])
        self.assertIn("decision_board_missing", status["blocking_reasons"])
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()

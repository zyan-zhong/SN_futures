from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_access_control_service import (  # noqa: E402
    build_access_control_report,
    build_permission_matrix,
    classify_api_action,
    detect_forbidden_ui_actions,
    refresh_access_control_report,
    validate_action_against_permissions,
)
from sn_futures.services.research_run_ledger_service import build_run_ledger_report  # noqa: E402


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


class GovernanceAccessControlServiceTest(unittest.TestCase):
    def test_permission_matrix_forbids_active_prediction_and_secret_writes(self) -> None:
        matrix = build_permission_matrix()

        self.assertFalse(matrix["active_write"]["default_allowed"])
        self.assertFalse(matrix["customer_prediction_write"]["default_allowed"])
        self.assertFalse(matrix["secret_write"]["default_allowed"])
        serialized = json.dumps(matrix, ensure_ascii=False)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("endpoint secret", serialized)
        self.assertNotIn("raw-secret", serialized)

    def test_action_classification_covers_high_risk_routes(self) -> None:
        self.assertEqual(classify_api_action("POST", "/api/terminal/models/approve-active")["category"], "active_write")
        self.assertEqual(classify_api_action("POST", "/api/terminal/refresh/predictions")["category"], "customer_prediction_write")
        self.assertEqual(classify_api_action("POST", "/api/terminal/settings/secrets")["category"], "secret_write")
        self.assertEqual(classify_api_action("POST", "/api/terminal/feature-store/build-v12")["category"], "heavy_build")
        self.assertEqual(classify_api_action("POST", "/api/terminal/research/run-candidate-v12")["category"], "research_train")
        self.assertEqual(classify_api_action("POST", "/api/terminal/models/promote-candidate")["category"], "promotion_dry_run")
        self.assertEqual(classify_api_action("POST", "/api/terminal/research/refresh-decision-board")["category"], "safe_refresh")

    def test_current_blocked_state_blocks_heavy_build_and_research_train(self) -> None:
        decision_board = {
            "current_research_state": "managed_data_blocked",
            "candidate_training_allowed": False,
            "training_dataset_v12_allowed": False,
        }
        heavy = validate_action_against_permissions(
            {"id": "build_fs_v12", "category": "heavy_build"},
            decision_board=decision_board,
        )
        train = validate_action_against_permissions(
            {"id": "candidate_v12", "category": "research_train"},
            decision_board=decision_board,
        )

        self.assertFalse(heavy["allowed"])
        self.assertIn("heavy_build_blocked_by_decision_board", heavy["blocking_reasons"])
        self.assertFalse(train["allowed"])
        self.assertIn("candidate_training_not_allowed", train["blocking_reasons"])

    def test_promotion_dry_run_is_allowed_only_without_active_side_effect(self) -> None:
        allowed = validate_action_against_permissions(
            {"id": "promotion_dry_run", "category": "promotion_dry_run", "active_updated": False},
            decision_board={"current_research_state": "blocked"},
        )
        blocked = validate_action_against_permissions(
            {"id": "promotion_write", "category": "promotion_dry_run", "active_updated": True},
            decision_board={"current_research_state": "blocked"},
        )

        self.assertTrue(allowed["allowed"])
        self.assertFalse(blocked["allowed"])
        self.assertIn("promotion_dry_run_must_not_write_active", blocked["blocking_reasons"])

    def test_safe_refresh_is_allowed_only_without_training_side_effect(self) -> None:
        allowed = validate_action_against_permissions(
            {"id": "refresh_board", "category": "safe_refresh", "training_invoked": False},
            decision_board={},
        )
        blocked = validate_action_against_permissions(
            {"id": "bad_refresh", "category": "safe_refresh", "training_invoked": True},
            decision_board={},
        )

        self.assertTrue(allowed["allowed"])
        self.assertFalse(blocked["allowed"])
        self.assertIn("safe_refresh_must_not_train", blocked["blocking_reasons"])

    def test_forbidden_ui_actions_are_detected_without_accepting_raw_secret_fields(self) -> None:
        result = detect_forbidden_ui_actions(
            {
                "GovernanceConsolePage.tsx": "<button>publish active</button>",
                "SettingsPage.tsx": "SN_TUSHARE_TOKEN raw input",
            }
        )

        self.assertGreater(result["violation_count"], 0)
        self.assertIn("active_publish_button_exposed", result["violations"])
        self.assertIn("raw_secret_input_field_exposed", result["violations"])

    def test_report_blocks_high_risk_actions_and_does_not_trigger_training(self) -> None:
        tmp = _workspace_tmp("access-control-report")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "current_research_state": "managed_data_blocked",
                    "candidate_training_allowed": False,
                    "training_dataset_v12_allowed": False,
                    "blocking_reasons": ["managed_proxy_disabled"],
                },
            )

            report = build_access_control_report()

        self.assertIn(report["status"], {"blocked", "guarded"})
        self.assertFalse(report["active_write_allowed"])
        self.assertFalse(report["customer_prediction_write_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertTrue(report["allowed_safe_actions"])
        self.assertTrue(report["blocked_heavy_actions"])
        self.assertTrue(report["blocked_secret_actions"])
        self.assertIn("active_write", report["forbidden_actions"])
        self.assertNotIn("raw-secret", json.dumps(report, ensure_ascii=False))

    def test_refresh_access_control_records_safe_refresh_in_run_ledger(self) -> None:
        tmp = _workspace_tmp("access-control-ledger")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "current_research_state": "managed_data_blocked",
                    "candidate_training_allowed": False,
                    "training_dataset_v12_allowed": False,
                },
            )
            report = refresh_access_control_report()
            ledger = build_run_ledger_report(record_current=False)

        self.assertEqual(report["training_invoked"], False)
        self.assertGreaterEqual(ledger["latest_run_count"], 1)
        self.assertIn("governance_access_control", json.dumps(ledger["latest_runs"], ensure_ascii=False))
        self.assertEqual(ledger["heavy_task_count"], 0)


if __name__ == "__main__":
    unittest.main()

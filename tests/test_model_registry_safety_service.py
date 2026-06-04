from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.model_registry_safety_service import (  # noqa: E402
    build_model_registry_safety_contract,
    build_registry_safety_report,
    detect_unapproved_active_model,
    validate_active_write_preconditions,
    validate_rollback_plan,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_decision_board(output: Path, *, manual: bool = False, active_allowed: bool = False) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "ready" if manual else "blocked",
            "manual_approval_recommended": manual,
            "active_publish_allowed": active_allowed,
            "blocking_reasons": [] if manual else ["managed_data_blocked"],
        },
    )


def _write_promotion(output: Path, *, status: str = "failed", passed: bool = False, dry_run: bool = True) -> None:
    _write_json(
        output / "model_registry" / "promotion_report_v10.json",
        {
            "status": status,
            "passed": passed,
            "dry_run": dry_run,
            "active_updated": False,
            "passed_candidates": [{"model_id": "candidate_v10_5d"}] if passed else [],
        },
    )


class ModelRegistrySafetyServiceTest(unittest.TestCase):
    def test_active_model_without_approval_is_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            active_path = output / "model_registry" / "active_model.json"
            _write_json(active_path, {"status": "active_available", "candidate_version": "v10"})
            before = active_path.read_text(encoding="utf-8")

            result = build_registry_safety_report(candidate_version="v10")
            after = active_path.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "violation")
        self.assertFalse(result["active_write_allowed"])
        self.assertTrue(result["current_active_model_exists"])
        self.assertTrue(result["unapproved_active_detected"])
        self.assertIn("unapproved_active_model_detected", result["blocking_reasons"])
        self.assertEqual(before, after)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_missing_rollback_target_blocks_registry_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_decision_board(output, manual=True, active_allowed=False)
            _write_promotion(output, status="pass", passed=True, dry_run=True)

            result = build_registry_safety_report(candidate_version="v10")

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["rollback_target_available"])
        self.assertFalse(result["active_write_allowed"])
        self.assertIn("rollback_target_missing", result["blocking_reasons"])

    def test_promotion_dry_run_fail_blocks_active_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_decision_board(output, manual=True, active_allowed=False)
            _write_promotion(output, status="failed", passed=False, dry_run=True)
            _write_json(output / "model_registry" / "rollback" / "active_model_previous.json", {"status": "previous_active"})

            result = build_registry_safety_report(candidate_version="v10")

        self.assertEqual(result["promotion_dry_run_status"], "failed")
        self.assertFalse(result["active_write_allowed"])
        self.assertIn("promotion_dry_run_failed", result["blocking_reasons"])

    def test_current_blocked_state_disallows_active_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_decision_board(output, manual=False, active_allowed=False)
            _write_promotion(output, status="pass", passed=True, dry_run=True)
            _write_json(output / "model_registry" / "rollback" / "active_model_previous.json", {"status": "previous_active"})

            result = build_registry_safety_report(candidate_version="v10")

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["active_write_allowed"])
        self.assertIn("manual_approval_not_recommended", result["blocking_reasons"])

    def test_service_does_not_write_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_decision_board(output, manual=True, active_allowed=False)
            _write_promotion(output, status="pass", passed=True, dry_run=True)
            _write_json(output / "model_registry" / "rollback" / "active_model_previous.json", {"status": "previous_active"})

            result = build_registry_safety_report(candidate_version="v10")

            self.assertFalse((output / "model_registry" / "active_model.json").exists())

        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_public_helpers_describe_contract_preconditions(self) -> None:
        contract = build_model_registry_safety_contract(candidate_version="v10")
        rollback = validate_rollback_plan(
            rollback_candidates=[{"path": "rollback/active_model_previous.json", "exists": True}],
        )
        approval = detect_unapproved_active_model(
            active_model={"status": "active_available"},
            release_audit={"status": "active_released", "active_updated": True},
        )
        preconditions = validate_active_write_preconditions(
            decision_board={"manual_approval_recommended": True, "active_publish_allowed": False},
            promotion_report={"status": "pass", "passed": True, "dry_run": True, "active_updated": False},
            rollback_plan=rollback,
            unapproved_active=approval,
        )

        self.assertEqual(contract["candidate_version"], "v10")
        self.assertTrue(rollback["rollback_target_available"])
        self.assertFalse(approval["unapproved_active_detected"])
        self.assertEqual(preconditions["status"], "blocked")
        self.assertFalse(preconditions["active_write_allowed"])
        self.assertIn("active_publish_workflow_not_implemented", preconditions["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

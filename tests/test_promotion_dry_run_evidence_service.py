from __future__ import annotations

import json
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.promotion_dry_run_evidence_service import (  # noqa: E402
    build_promotion_dry_run_evidence,
    build_promotion_dry_run_report,
    simulate_registry_write_plan,
    validate_no_active_write_boundary,
    validate_no_customer_prediction_boundary,
    validate_promotion_dry_run_preconditions,
)


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


def _seed_ready_inputs(output: Path) -> None:
    future_expiry = (datetime.now() + timedelta(hours=6)).isoformat(timespec="seconds")
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:00",
            "current_research_state": "ready_for_manual_review",
            "manual_approval_recommended": True,
            "active_publish_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "manual_approval_report.json",
        {
            "status": "approved_for_shadow_only",
            "generated_at": "2026-06-03T12:00:01",
            "expires_at": future_expiry,
            "two_person_review_pass": True,
            "requested_action": "promotion_dry_run_only",
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
        },
    )
    _write_json(
        output / "model_research" / "shadow_mode_readiness_spec.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:02",
            "shadow_mode_allowed": True,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "model_registry_safety_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:03",
            "active_write_allowed": False,
            "rollback_target_available": True,
            "unapproved_active_detected": False,
            "blocking_reasons": [],
        },
    )
    _write_json(
        output / "model_research" / "evidence_freshness_report.json",
        {
            "status": "pass",
            "generated_at": "2026-06-03T12:00:04",
            "stale_reports": [],
            "missing_timestamps": [],
            "timestamp_inversions": [],
        },
    )
    _write_json(
        output / "model_research" / "production_cutover_checklist_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:05",
            "cutover_allowed": True,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
            "blocking_reasons": [],
        },
    )


class PromotionDryRunEvidenceServiceTest(unittest.TestCase):
    def test_current_blocked_state_blocks_promotion_dry_run_evidence(self) -> None:
        tmp = _workspace_tmp("promotion-evidence-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_promotion_dry_run_report(candidate_version="v12")

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["active_write_allowed"])
        self.assertFalse(report["active_write_attempted"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_write_allowed"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(report["training_invoked"])
        self.assertIn("decision_board_blocked", report["blocking_reasons"])

    def test_manual_registry_cutover_and_stale_evidence_each_block(self) -> None:
        cases = [
            ("manual_approval_report.json", None, "manual_approval_missing"),
            ("model_registry_safety_report.json", {"status": "violation"}, "registry_safety_not_pass"),
            ("production_cutover_checklist_report.json", {"status": "blocked", "cutover_allowed": False}, "production_cutover_checklist_not_pass"),
            ("evidence_freshness_report.json", {"status": "blocked", "stale_reports": ["candidate_v12"]}, "evidence_freshness_not_pass"),
        ]
        for filename, override, reason in cases:
            with self.subTest(reason=reason):
                tmp = _workspace_tmp(f"promotion-evidence-{reason}")
                with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
                    output = Path(tmp) / "outputs"
                    _seed_ready_inputs(output)
                    path = output / "model_research" / filename
                    if override is None:
                        path.unlink()
                    else:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload.update(override)
                        _write_json(path, payload)
                    preconditions = validate_promotion_dry_run_preconditions(candidate_version="v12")
                    report = build_promotion_dry_run_evidence(candidate_version="v12")

                self.assertEqual(preconditions["status"], "blocked")
                self.assertIn(reason, preconditions["blocking_reasons"])
                self.assertIn(reason, report["blocking_reasons"])
                self.assertFalse(report["active_updated"])
                self.assertFalse(report["customer_prediction_generated"])

    def test_ready_inputs_only_create_simulation_report_not_active_or_prediction(self) -> None:
        tmp = _workspace_tmp("promotion-evidence-ready")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_ready_inputs(output)
            report = build_promotion_dry_run_evidence(candidate_version="v12")
            active_check = validate_no_active_write_boundary()
            prediction_check = validate_no_customer_prediction_boundary()
            ledger = output / "model_research" / "run_ledger" / "research_run_ledger.jsonl"
            ledger_text = ledger.read_text(encoding="utf-8")

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["requested_action"], "promotion_dry_run_only")
        self.assertFalse(report["active_write_allowed"])
        self.assertFalse(report["active_write_attempted"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_write_allowed"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(report["training_invoked"])
        self.assertEqual(active_check["status"], "pass")
        self.assertEqual(prediction_check["status"], "pass")
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())
        self.assertIn("promotion_dry_run_evidence", ledger_text)
        self.assertIn('"run_type": "safe_dry_run"', ledger_text)

    def test_simulated_registry_write_plan_does_not_modify_active_pointer(self) -> None:
        tmp = _workspace_tmp("promotion-evidence-pointer")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            pointer_path = output / "model_registry" / "active_pointer.json"
            _write_json(pointer_path, {"active_candidate": "existing_v0"})
            before = pointer_path.read_text(encoding="utf-8")
            plan = simulate_registry_write_plan(candidate_version="v12")
            after = pointer_path.read_text(encoding="utf-8")

        self.assertTrue(plan["simulation_only"])
        self.assertFalse(plan["actual_registry_write_performed"])
        self.assertEqual(before, after)

    def test_report_sanitizes_secret_like_evidence(self) -> None:
        tmp = _workspace_tmp("promotion-evidence-sanitized")
        raw_secret = "super-secret-token-1234567890"
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_ready_inputs(output)
            board_path = output / "model_research" / "research_decision_board.json"
            board = json.loads(board_path.read_text(encoding="utf-8"))
            board["Authorization"] = f"Bearer {raw_secret}"
            board["endpoint_secret"] = raw_secret
            _write_json(board_path, board)
            report = build_promotion_dry_run_evidence(candidate_version="v12")

        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(raw_secret, encoded)
        self.assertIn("promotion_dry_run_evidence", report["dry_run_version"])


if __name__ == "__main__":
    unittest.main()

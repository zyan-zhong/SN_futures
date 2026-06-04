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

from sn_futures.services.manual_approval_service import (  # noqa: E402
    build_manual_approval_report,
    create_manual_approval_request,
    record_manual_approval_decision,
    refresh_manual_approval_status,
    validate_manual_approval_preconditions,
    validate_reviewer_identity_shape,
    validate_two_person_review,
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


def _write_ready_evidence(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "ready_for_manual_review",
            "current_research_state": "ready_for_manual_review",
            "manual_approval_recommended": True,
            "active_publish_allowed": False,
            "candidate_v10_summary": {
                "status": "success",
                "manual_approval_recommended": True,
                "cost_attribution_pass": True,
            },
            "candidate_v12_summary": {"status": "success", "manual_approval_recommended": True},
            "blocking_reasons": [],
            "stale_or_missing_reports": [],
        },
    )
    _write_json(
        output / "model_research" / "evidence_bundle_index.json",
        {
            "status": "complete",
            "missing_reports": [],
            "incomplete_reports": [],
            "all_required_evidence_present": True,
        },
    )
    _write_json(
        output / "model_research" / "model_registry_safety_report.json",
        {
            "status": "blocked",
            "active_write_allowed": False,
            "unapproved_active_detected": False,
            "blocking_reasons": ["active_publish_not_supported_by_manual_approval_workflow"],
        },
    )
    _write_json(
        output / "model_research" / "shadow_mode_readiness_spec.json",
        {"status": "ready", "shadow_mode_allowed": True, "blocked_gates": []},
    )
    _write_json(
        output / "model_research" / "incident_drill_report.json",
        {"status": "ready", "real_lockdown_state": {"lockdown_triggered": False, "lockdown_reasons": []}},
    )


class ManualApprovalServiceTest(unittest.TestCase):
    def test_decision_board_blocked_cannot_request_approval(self) -> None:
        tmp = _workspace_tmp("manual-board-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "manual_approval_recommended": False,
                    "blocking_reasons": ["managed_data_blocked"],
                },
            )
            result = create_manual_approval_request(requested_action="shadow_mode_only", candidate_version="v12")

        self.assertEqual(result["status"], "blocked_by_gates")
        self.assertFalse(result["approval_request_allowed"])
        self.assertIn("decision_board_blocked", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_manual_approval_recommended_false_blocks_request(self) -> None:
        preconditions = validate_manual_approval_preconditions(
            decision_board={"status": "ready", "manual_approval_recommended": False, "blocking_reasons": []},
            evidence_bundle={"status": "complete", "missing_reports": [], "incomplete_reports": []},
            registry_safety={"status": "blocked", "active_write_allowed": False},
            shadow_readiness={"status": "ready", "shadow_mode_allowed": True},
            incident_drill={"real_lockdown_state": {"lockdown_triggered": False}},
            requested_action="shadow_mode_only",
        )

        self.assertFalse(preconditions["approval_request_allowed"])
        self.assertIn("manual_approval_not_recommended", preconditions["blocking_reasons"])

    def test_cost_attribution_fail_blocks_request(self) -> None:
        preconditions = validate_manual_approval_preconditions(
            decision_board={
                "status": "ready_for_manual_review",
                "manual_approval_recommended": True,
                "candidate_v10_summary": {"cost_attribution_pass": False},
                "blocking_reasons": ["cost_attribution:institutional_2x_cost_negative"],
            },
            evidence_bundle={"status": "complete", "missing_reports": [], "incomplete_reports": []},
            registry_safety={"status": "blocked", "active_write_allowed": False},
            shadow_readiness={"status": "ready", "shadow_mode_allowed": True},
            incident_drill={"real_lockdown_state": {"lockdown_triggered": False}},
            requested_action="shadow_mode_only",
        )

        self.assertFalse(preconditions["approval_request_allowed"])
        self.assertIn("cost_attribution_failed", preconditions["blocking_reasons"])

    def test_stale_evidence_and_missing_bundle_block_request(self) -> None:
        preconditions = validate_manual_approval_preconditions(
            decision_board={
                "status": "ready_for_manual_review",
                "manual_approval_recommended": True,
                "stale_or_missing_reports": ["candidate_v12_report:stale"],
            },
            evidence_bundle={},
            registry_safety={"status": "blocked", "active_write_allowed": False},
            shadow_readiness={"status": "ready", "shadow_mode_allowed": True},
            incident_drill={"real_lockdown_state": {"lockdown_triggered": False}},
            requested_action="shadow_mode_only",
        )

        self.assertFalse(preconditions["approval_request_allowed"])
        self.assertIn("stale_evidence_present", preconditions["blocking_reasons"])
        self.assertIn("evidence_bundle_missing", preconditions["blocking_reasons"])

    def test_incident_lockdown_blocks_request(self) -> None:
        preconditions = validate_manual_approval_preconditions(
            decision_board={"status": "ready_for_manual_review", "manual_approval_recommended": True},
            evidence_bundle={"status": "complete", "missing_reports": [], "incomplete_reports": []},
            registry_safety={"status": "blocked", "active_write_allowed": False},
            shadow_readiness={"status": "ready", "shadow_mode_allowed": True},
            incident_drill={"real_lockdown_state": {"lockdown_triggered": True, "lockdown_reasons": ["secret_leak_detected"]}},
            requested_action="shadow_mode_only",
        )

        self.assertFalse(preconditions["approval_request_allowed"])
        self.assertIn("incident_lockdown_active", preconditions["blocking_reasons"])

    def test_shadow_not_allowed_blocks_shadow_approval(self) -> None:
        preconditions = validate_manual_approval_preconditions(
            decision_board={"status": "ready_for_manual_review", "manual_approval_recommended": True},
            evidence_bundle={"status": "complete", "missing_reports": [], "incomplete_reports": []},
            registry_safety={"status": "blocked", "active_write_allowed": False},
            shadow_readiness={"status": "blocked", "shadow_mode_allowed": False},
            incident_drill={"real_lockdown_state": {"lockdown_triggered": False}},
            requested_action="shadow_mode_only",
        )

        self.assertFalse(preconditions["approval_request_allowed"])
        self.assertIn("shadow_mode_not_allowed", preconditions["blocking_reasons"])

    def test_active_publish_and_customer_prediction_actions_are_forbidden(self) -> None:
        for action in ["active_publish", "customer_prediction"]:
            preconditions = validate_manual_approval_preconditions(
                decision_board={"status": "ready_for_manual_review", "manual_approval_recommended": True},
                evidence_bundle={"status": "complete", "missing_reports": [], "incomplete_reports": []},
                registry_safety={"status": "blocked", "active_write_allowed": False},
                shadow_readiness={"status": "ready", "shadow_mode_allowed": True},
                incident_drill={"real_lockdown_state": {"lockdown_triggered": False}},
                requested_action=action,
            )
            self.assertFalse(preconditions["approval_request_allowed"])
            self.assertIn("requested_action_not_allowed", preconditions["blocking_reasons"])

    def test_two_person_review_requires_distinct_valid_reviewers(self) -> None:
        one = validate_two_person_review([{"reviewer_id": "alice", "display_name": "Alice"}])
        same = validate_two_person_review([
            {"reviewer_id": "alice", "display_name": "Alice"},
            {"reviewer_id": "alice", "display_name": "Alice again"},
        ])
        valid = validate_two_person_review([
            {"reviewer_id": "alice", "display_name": "Alice"},
            {"reviewer_id": "bob", "display_name": "Bob"},
        ])
        bad_identity = validate_reviewer_identity_shape({"reviewer_id": "Authorization: Bearer raw-secret", "display_name": "Alice"})

        self.assertFalse(one["two_person_review_pass"])
        self.assertIn("reviewer_count_below_two", one["blocking_reasons"])
        self.assertFalse(same["two_person_review_pass"])
        self.assertIn("reviewers_must_be_distinct", same["blocking_reasons"])
        self.assertTrue(valid["two_person_review_pass"])
        self.assertFalse(bad_identity["valid"])
        self.assertNotIn("raw-secret", json.dumps(bad_identity, ensure_ascii=False))

    def test_expired_approval_cannot_be_used(self) -> None:
        tmp = _workspace_tmp("manual-expired")
        expired = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ready_evidence(output)
            _write_json(
                output / "model_research" / "manual_approval_report.json",
                {
                    "status": "pending_review",
                    "candidate_version": "v12",
                    "requested_action": "shadow_mode_only",
                    "expires_at": expired,
                    "reviewers": [],
                },
            )
            result = record_manual_approval_decision(
                decision="approve",
                reviewers=[
                    {"reviewer_id": "alice", "display_name": "Alice"},
                    {"reviewer_id": "bob", "display_name": "Bob"},
                ],
            )

        self.assertEqual(result["status"], "expired")
        self.assertIn("approval_expired", result["blocking_reasons"])

    def test_create_and_approve_shadow_request_never_writes_active_or_prediction(self) -> None:
        tmp = _workspace_tmp("manual-approve")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ready_evidence(output)
            request = create_manual_approval_request(requested_action="shadow_mode_only", candidate_version="v12")
            approved = record_manual_approval_decision(
                decision="approve",
                reviewers=[
                    {"reviewer_id": "alice", "display_name": "Alice"},
                    {"reviewer_id": "bob", "display_name": "Bob"},
                ],
            )

        self.assertEqual(request["status"], "pending_review")
        self.assertEqual(approved["status"], "approved_for_shadow_only")
        self.assertTrue(approved["two_person_review_pass"])
        self.assertFalse(approved["active_write_allowed"])
        self.assertFalse(approved["customer_prediction_write_allowed"])
        self.assertFalse(approved["training_invoked"])
        self.assertFalse(approved["active_updated"])
        self.assertFalse(approved["customer_prediction_generated"])
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())
        serialized = json.dumps(approved, ensure_ascii=False)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("endpoint secret", serialized)
        self.assertNotIn("raw-secret", serialized)

    def test_refresh_status_in_current_blocked_state_is_report_only(self) -> None:
        tmp = _workspace_tmp("manual-refresh")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = refresh_manual_approval_status()

        self.assertIn(report["status"], {"blocked_by_gates", "not_requested"})
        self.assertFalse(report["approval_request_allowed"])
        self.assertFalse(report["active_write_allowed"])
        self.assertFalse(report["customer_prediction_write_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.evidence_bundle_service import (
    build_evidence_bundle_index,
    build_reproducibility_checklist,
    collect_evidence_files,
    compute_evidence_hashes,
    validate_evidence_completeness,
    write_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class EvidenceBundleServiceTest(unittest.TestCase):
    def test_missing_reports_are_marked_missing_not_pass(self) -> None:
        tmp = _workspace_tmp("evidence-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            files = collect_evidence_files()
            completeness = validate_evidence_completeness(files)
            bundle = build_evidence_bundle_index()

        self.assertGreater(len(completeness["missing_reports"]), 0)
        self.assertEqual(bundle["status"], "blocked")
        self.assertFalse(bundle["reproducibility_checklist"]["all_required_evidence_present"])
        self.assertIn("missing_reports", bundle["safety_flags"])
        self.assertFalse(bundle["training_invoked"])
        self.assertFalse(bundle["active_updated"])
        self.assertFalse(bundle["customer_prediction_generated"])

    def test_incomplete_report_is_marked_incomplete(self) -> None:
        tmp = _workspace_tmp("evidence-incomplete")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {"setup_status": "ready", "training_invoked": False},
            )

            bundle = build_evidence_bundle_index()

        self.assertIn("managed_proxy_setup", bundle["incomplete_reports"])
        self.assertEqual(bundle["status"], "blocked")

    def test_hash_computation_is_stable_and_does_not_include_secret_values(self) -> None:
        tmp = _workspace_tmp("evidence-hash")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            path = output / "model_research" / "research_decision_board.json"
            _write_json(
                path,
                {
                    "status": "blocked",
                    "current_research_state": "managed_data_blocked",
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                    "token": "raw-secret-token-should-not-appear",
                },
            )
            files = collect_evidence_files()
            first = compute_evidence_hashes(files)
            second = compute_evidence_hashes(files)
            bundle = build_evidence_bundle_index()
            serialized = json.dumps(bundle, ensure_ascii=False)

        self.assertEqual(first["research_decision_board"]["sha256"], second["research_decision_board"]["sha256"])
        self.assertNotIn("raw-secret-token-should-not-appear", serialized)
        self.assertIn("research_decision_board", bundle["file_hashes"])

    def test_write_evidence_bundle_does_not_trigger_downstream_actions_or_active(self) -> None:
        tmp = _workspace_tmp("evidence-write")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "current_research_state": "managed_data_blocked",
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                    "manual_approval_recommended": False,
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            bundle = write_evidence_bundle()
            bundle_path = Path(bundle["bundle_path"])

        self.assertTrue(bundle_path.exists())
        self.assertFalse(bundle["training_invoked"])
        self.assertFalse(bundle["active_updated"])
        self.assertFalse(bundle["customer_prediction_generated"])
        self.assertTrue(bundle["no_active_confirmation"]["confirmed"])
        self.assertTrue(bundle["no_prediction_confirmation"]["confirmed"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())

    def test_reproducibility_checklist_includes_required_operational_items(self) -> None:
        checklist = build_reproducibility_checklist(
            current_research_state="managed_data_blocked",
            next_allowed_action="configure_managed_proxy_endpoint_or_token",
            missing_reports=["managed_proxy_health"],
            incomplete_reports=[],
            safety_flags=["no_active_confirmed"],
        )

        self.assertIn("code tests passed summary", checklist)
        self.assertIn("frontend tests passed summary", checklist)
        self.assertIn("secret scan status", checklist)
        self.assertEqual(checklist["current_blockers"], ["managed_proxy_health"])
        self.assertEqual(checklist["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")
        self.assertGreater(len(checklist["required_human_manual_steps"]), 0)


if __name__ == "__main__":
    unittest.main()

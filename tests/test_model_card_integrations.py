from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.evidence_bundle_service import write_evidence_bundle
from sn_futures.services.external_audit_export_service import write_external_audit_package
from sn_futures.services.model_card_service import write_model_card
from sn_futures.services.research_decision_board_service import build_research_decision_board


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


def _seed_minimal_board(output: Path, *, model_card_status: str = "ready") -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "manual_approval_recommended": True,
            "active_publish_allowed": False,
            "blocking_reasons": [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "evidence_bundle_index.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:00",
            "missing_reports": [],
            "incomplete_reports": [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "cost_stress_attribution.json",
        {"status": "fail", "passed": False, "failure_drivers": ["year_specific_cost_drag"]},
    )
    _write_json(
        output / "diagnostics" / "managed_proxy_setup_report.json",
        {"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"]},
    )
    _write_json(
        output / "model_research" / "model_card.json",
        {
            "status": model_card_status,
            "current_status": "managed_data_blocked / research_only",
            "manual_approval_summary": {"manual_approval_recommended": False},
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class ModelCardIntegrationsTest(unittest.TestCase):
    def test_evidence_bundle_indexes_model_card_and_risk_disclosure_paths(self) -> None:
        tmp = _workspace_tmp("model-card-evidence")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal_board(output)
            write_model_card()
            bundle = write_evidence_bundle()

        self.assertIn("model_card_json", bundle["evidence_files"])
        self.assertIn("model_card_md", bundle["evidence_files"])
        self.assertIn("risk_disclosure", bundle["evidence_files"])
        self.assertIn("model_card_json", bundle["file_hashes"])

    def test_external_audit_export_references_redacted_model_card_summary(self) -> None:
        tmp = _workspace_tmp("model-card-audit")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal_board(output)
            write_model_card()
            write_evidence_bundle()
            _write_json(
                output / "model_research" / "run_ledger" / "research_run_ledger_report.json",
                {"status": "ready", "latest_run_count": 1, "violation_count": 0},
            )
            package = write_external_audit_package()
            serialized = json.dumps(package, ensure_ascii=False)

        self.assertIn("model_card", package["evidence_files"])
        self.assertIn("research_only", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Bearer ", serialized)

    def test_decision_board_blocks_manual_approval_when_model_card_missing_or_incomplete(self) -> None:
        tmp = _workspace_tmp("model-card-board-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal_board(output, model_card_status="incomplete")
            board = build_research_decision_board()

        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("model_card:incomplete", board["blocking_reasons"])

    def test_complete_model_card_does_not_open_active_publish(self) -> None:
        tmp = _workspace_tmp("model-card-board-complete")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal_board(output, model_card_status="ready")
            board = build_research_decision_board()

        self.assertFalse(board["active_publish_allowed"])
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

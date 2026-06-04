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
from sn_futures.services.governance_maturity_matrix_service import write_governance_maturity_matrix
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


def _seed_minimal(output: Path, *, matrix_status: str = "ready") -> None:
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
    _write_json(output / "model_research" / "evidence_bundle_index.json", {"status": "ready", "missing_reports": [], "incomplete_reports": []})
    _write_json(output / "model_research" / "run_ledger" / "research_run_ledger_report.json", {"status": "ready", "violation_count": 0})
    _write_json(output / "model_research" / "cost_stress_attribution.json", {"status": "fail", "passed": False})
    _write_json(output / "diagnostics" / "managed_proxy_setup_report.json", {"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"]})
    _write_json(
        output / "model_research" / "governance_maturity_matrix.json",
        {
            "status": matrix_status,
            "production_readiness": False,
            "critical_gaps": ["managed_proxy_disabled"],
            "current_research_state": "managed_data_blocked",
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class GovernanceMaturityMatrixIntegrationsTest(unittest.TestCase):
    def test_evidence_bundle_indexes_maturity_matrix_report(self) -> None:
        tmp = _workspace_tmp("maturity-evidence")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal(output)
            write_governance_maturity_matrix()
            bundle = write_evidence_bundle()

        self.assertIn("governance_maturity_matrix", bundle["evidence_files"])
        self.assertIn("governance_maturity_matrix", bundle["file_hashes"])

    def test_external_audit_export_references_maturity_summary(self) -> None:
        tmp = _workspace_tmp("maturity-audit")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal(output)
            write_governance_maturity_matrix()
            write_evidence_bundle()
            package = write_external_audit_package()
            serialized = json.dumps(package, ensure_ascii=False)

        self.assertIn("governance_maturity_matrix", package["evidence_files"])
        self.assertIn("managed_data_blocked", serialized)
        self.assertNotIn("Authorization", serialized)

    def test_model_card_references_maturity_status_and_critical_gaps(self) -> None:
        tmp = _workspace_tmp("maturity-model-card")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal(output)
            write_governance_maturity_matrix()
            card = write_model_card()

        self.assertIn("maturity_matrix_summary", card)
        self.assertEqual(card["maturity_matrix_summary"]["status"], "incomplete")
        self.assertIn("managed_proxy_disabled", card["maturity_matrix_summary"]["critical_gaps"])
        self.assertFalse(card["active_model_status"]["active_publish_allowed"])

    def test_decision_board_blocks_manual_approval_when_maturity_matrix_incomplete(self) -> None:
        tmp = _workspace_tmp("maturity-board")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_minimal(output, matrix_status="incomplete")
            board = build_research_decision_board()

        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("governance_maturity_matrix:incomplete", board["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

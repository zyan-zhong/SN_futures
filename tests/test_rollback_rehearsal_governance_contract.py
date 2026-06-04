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
    classify_api_action,
    refresh_access_control_report,
)
from sn_futures.services.research_decision_board_service import build_research_decision_board  # noqa: E402
from sn_futures.services.rollback_rehearsal_service import build_rollback_rehearsal_plan  # noqa: E402


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


class RollbackRehearsalGovernanceContractTest(unittest.TestCase):
    def test_access_control_classifies_simulated_quarantine_as_safe_dry_run(self) -> None:
        classified = classify_api_action("POST", "/api/terminal/governance/simulate-artifact-quarantine")

        self.assertEqual(classified["category"], "safe_dry_run")

    def test_access_control_inventory_includes_rollback_actions(self) -> None:
        tmp = _workspace_tmp("rollback-access")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = refresh_access_control_report()

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertIn("read_rollback_rehearsal", serialized)
        self.assertIn("refresh_rollback_rehearsal", serialized)
        self.assertIn("simulate_artifact_quarantine", serialized)

    def test_decision_board_enters_lockdown_when_rollback_quarantine_needed(self) -> None:
        tmp = _workspace_tmp("rollback-board")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            _write_json(tmp / "outputs" / "model_registry" / "active_model.json", {"status": "unexpected"})
            rollback = build_rollback_rehearsal_plan()
            board = build_research_decision_board()

        self.assertTrue(rollback["quarantine_needed"])
        self.assertEqual(board["current_research_state"], "governance_lockdown")
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("resolve_governance_incident", board["next_allowed_action"])

    def test_clean_rollback_rehearsal_does_not_allow_active_publish(self) -> None:
        tmp = _workspace_tmp("rollback-board-clean")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            rollback = build_rollback_rehearsal_plan()
            board = build_research_decision_board()

        self.assertFalse(rollback["quarantine_needed"])
        self.assertFalse(board["active_publish_allowed"])


if __name__ == "__main__":
    unittest.main()

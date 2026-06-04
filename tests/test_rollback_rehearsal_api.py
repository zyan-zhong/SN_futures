from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class RollbackRehearsalApiTest(unittest.TestCase):
    def test_api_docs_include_rollback_rehearsal_endpoints(self) -> None:
        serialized = json.dumps(TERMINAL_API_DOCS, ensure_ascii=False)

        self.assertIn("/api/terminal/governance/rollback-rehearsal", serialized)
        self.assertIn("/api/terminal/governance/refresh-rollback-rehearsal", serialized)
        self.assertIn("/api/terminal/governance/simulate-artifact-quarantine", serialized)

    def test_refresh_endpoint_writes_report_without_forbidden_side_effects(self) -> None:
        tmp = _workspace_tmp("rollback-api-refresh")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/refresh-rollback-rehearsal",
                method="POST",
                body=b"{}",
            )

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"pass", "ready"})
        self.assertFalse(payload["quarantine_needed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())

    def test_simulate_quarantine_endpoint_is_simulation_only_even_if_body_requests_delete(self) -> None:
        tmp = _workspace_tmp("rollback-api-sim")
        active = tmp / "outputs" / "model_registry" / "active_model.json"
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text("{}", encoding="utf-8")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/simulate-artifact-quarantine",
                method="POST",
                body=json.dumps({"delete": True, "move": True}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertTrue(payload["simulation_only"])
        self.assertTrue(active.exists())
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

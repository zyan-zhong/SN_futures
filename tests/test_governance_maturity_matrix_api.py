from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class GovernanceMaturityMatrixApiTest(unittest.TestCase):
    def test_terminal_docs_expose_maturity_matrix_endpoints(self) -> None:
        endpoints = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/governance/maturity-matrix"), endpoints)
        self.assertIn(("POST", "/api/terminal/governance/refresh-maturity-matrix"), endpoints)

    def test_get_maturity_matrix_returns_current_or_computed_report(self) -> None:
        tmp = _workspace_tmp("maturity-api-get")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/maturity-matrix", method="GET")

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"ready", "incomplete", "blocked"})
        self.assertFalse(payload["production_readiness"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_maturity_matrix_writes_report_without_heavy_side_effects(self) -> None:
        tmp = _workspace_tmp("maturity-api-post")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            status, payload = handle_terminal_api("/api/terminal/governance/refresh-maturity-matrix", method="POST")

        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertFalse(payload["production_readiness"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()

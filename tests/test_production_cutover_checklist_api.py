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


class ProductionCutoverChecklistApiTest(unittest.TestCase):
    def test_terminal_docs_expose_cutover_endpoints(self) -> None:
        endpoints = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/governance/production-cutover-checklist"), endpoints)
        self.assertIn(("POST", "/api/terminal/governance/refresh-production-cutover-checklist"), endpoints)
        self.assertIn(("POST", "/api/terminal/governance/build-noop-release-plan"), endpoints)

    def test_get_cutover_checklist_returns_blocked_without_side_effects(self) -> None:
        tmp = _workspace_tmp("cutover-api-get")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/production-cutover-checklist", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["cutover_allowed"])
        self.assertFalse(payload["active_publish_allowed"])
        self.assertFalse(payload["customer_prediction_write_allowed"])
        self.assertFalse(payload["training_invoked"])

    def test_post_refresh_cutover_checklist_writes_report(self) -> None:
        tmp = _workspace_tmp("cutover-api-refresh")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/refresh-production-cutover-checklist", method="POST")

        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_post_build_noop_release_plan_writes_no_customer_or_active_outputs(self) -> None:
        tmp = _workspace_tmp("cutover-api-noop")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/build-noop-release-plan",
                method="POST",
                body={"candidate_version": "v12"},
            )
            output = Path(tmp) / "outputs"

        self.assertEqual(status, 200)
        self.assertEqual(payload["release_type"], "noop")
        self.assertTrue(payload["noop_release_plan_ready"])
        self.assertTrue(Path(payload["plan_path"]).exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()

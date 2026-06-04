from __future__ import annotations

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


class ShadowReplayEvaluatorApiTest(unittest.TestCase):
    def test_terminal_docs_expose_shadow_replay_endpoints(self) -> None:
        endpoints = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/governance/shadow-replay"), endpoints)
        self.assertIn(("POST", "/api/terminal/governance/refresh-shadow-replay"), endpoints)

    def test_get_shadow_replay_returns_safe_report_without_side_effects(self) -> None:
        tmp = _workspace_tmp("shadow-replay-api-get")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/shadow-replay", method="GET")
            output = Path(tmp) / "outputs"

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"blocked", "skipped", "research_only"})
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse((output / "customer_predictions").exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_post_refresh_shadow_replay_writes_report_not_customer_prediction(self) -> None:
        tmp = _workspace_tmp("shadow-replay-api-post")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/refresh-shadow-replay",
                method="POST",
                body={"candidate_version": "v10"},
            )
            output = Path(tmp) / "outputs"

        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse((output / "customer_predictions").exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()

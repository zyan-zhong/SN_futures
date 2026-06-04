from __future__ import annotations

import json
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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ModelCardApiTest(unittest.TestCase):
    def test_terminal_docs_expose_model_card_endpoints(self) -> None:
        paths = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/model-card", paths)
        self.assertIn("/api/terminal/governance/refresh-model-card", paths)

    def test_get_model_card_returns_current_or_computed_payload_without_training(self) -> None:
        tmp = _workspace_tmp("model-card-api-get")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/model-card", method="GET")

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"ready", "incomplete", "blocked"})
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_model_card_writes_reports_without_active_or_prediction(self) -> None:
        tmp = _workspace_tmp("model-card-api-post")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "current_research_state": "managed_data_blocked",
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                    "manual_approval_recommended": False,
                    "active_publish_allowed": False,
                    "blocking_reasons": ["managed_proxy_disabled"],
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )
            status, payload = handle_terminal_api("/api/terminal/governance/refresh-model-card", method="POST")

        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertTrue(Path(payload["model_card_md_path"]).exists())
        self.assertTrue(Path(payload["risk_disclosure_path"]).exists())
        self.assertFalse(payload["active_model_status"]["exists"])
        self.assertFalse(payload["customer_prediction_status"]["exists"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()

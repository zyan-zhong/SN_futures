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


def _seed_required_reports(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:00",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "evidence_bundle_index.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:01",
            "missing_reports": [],
            "incomplete_reports": [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "run_ledger" / "research_run_ledger_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:02",
            "violation_count": 0,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class ExternalAuditExportApiTest(unittest.TestCase):
    def test_terminal_docs_expose_external_audit_export_endpoints(self) -> None:
        endpoints = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/governance/external-audit-export"), endpoints)
        self.assertIn(("POST", "/api/terminal/governance/refresh-external-audit-export"), endpoints)

    def test_get_external_audit_export_returns_current_or_computed_index(self) -> None:
        tmp = _workspace_tmp("external-audit-api-get")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/governance/external-audit-export", method="GET")

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"incomplete", "ready", "violation"})
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_post_refresh_external_audit_export_writes_package(self) -> None:
        tmp = _workspace_tmp("external-audit-api-post")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_required_reports(output)
            status, payload = handle_terminal_api("/api/terminal/governance/refresh-external-audit-export", method="POST")

        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["audit_index_path"]).exists())
        self.assertTrue(Path(payload["review_summary_path"]).exists())
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

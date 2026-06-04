from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.external_audit_export_service import (
    build_external_audit_index,
    build_external_review_summary,
    collect_audit_export_sources,
    compute_audit_file_hashes,
    redact_audit_payload,
    validate_audit_export_no_secrets,
    write_external_audit_package,
)


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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_required_reports(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:00",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "blocking_reasons": ["managed_proxy_disabled"],
            "manual_approval_recommended": False,
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
            "bundle_version": "evidence_bundle_v1",
            "missing_reports": ["managed_proxy_health"],
            "incomplete_reports": [],
            "evidence_file_count": 1,
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
            "latest_run_count": 2,
            "violation_count": 0,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class ExternalAuditExportServiceTest(unittest.TestCase):
    def test_missing_required_reports_make_export_incomplete_not_pass(self) -> None:
        tmp = _workspace_tmp("external-audit-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            sources = collect_audit_export_sources()
            index = build_external_audit_index()

        self.assertEqual(index["status"], "incomplete")
        self.assertIn("research_decision_board", index["missing_reports"])
        self.assertIn("evidence_bundle", index["missing_reports"])
        self.assertIn("run_ledger", index["missing_reports"])
        self.assertFalse(index["training_invoked"])
        self.assertFalse(index["active_updated"])
        self.assertFalse(index["customer_prediction_generated"])
        self.assertIn("research_decision_board", sources)

    def test_redaction_removes_tokens_authorization_endpoint_and_raw_rows(self) -> None:
        raw = {
            "Authorization": "Bearer raw-secret-token-should-not-appear",
            "SN_TUSHARE_TOKEN": "0ad377e1f726e9e073e1caa199dc77bd4b34b5bebff1c0b6bfc96293",
            "endpoint_url": "https://secret.example.com/api/private?token=raw-secret",
            "managed_rows": [{"spot_price": 100, "source_timestamp": "2026-06-03T12:00:00"}],
            "oof_trace": [{"signal": 1, "confidence": 0.99}],
            "safe_status": "blocked",
        }

        redacted = redact_audit_payload(raw)
        serialized = json.dumps(redacted, ensure_ascii=False)

        self.assertNotIn("raw-secret-token-should-not-appear", serialized)
        self.assertNotIn("0ad377e1f726e9e073e1caa199dc77bd4b34b5bebff1c0b6bfc96293", serialized)
        self.assertNotIn("https://secret.example.com", serialized)
        self.assertNotIn("spot_price\": 100", serialized)
        self.assertIn("safe_status", serialized)
        self.assertGreaterEqual(len(redacted["redacted_fields"]), 3)
        self.assertGreaterEqual(len(redacted["omitted_sensitive_files"]), 1)

    def test_oof_trace_is_exported_only_as_path_hash_and_summary(self) -> None:
        tmp = _workspace_tmp("external-audit-oof")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_required_reports(output)
            oof_path = output / "walk_forward" / "v10" / "oof_trace_test.csv"
            _write_text(oof_path, "date,signal,confidence\n2026-01-01,1,0.99\n")

            package = write_external_audit_package()
            audit_index = Path(package["audit_index_path"]).read_text(encoding="utf-8")
            oof_entries = [
                item
                for key, item in package["evidence_files"].items()
                if str(key).startswith("sensitive_artifact:oof_trace")
            ]

        self.assertEqual(oof_entries[0]["path"], str(oof_path))
        self.assertIn("oof_trace_test.csv", audit_index)
        self.assertNotIn("2026-01-01,1,0.99", audit_index)
        self.assertIn("oof_trace_omitted", audit_index)

    def test_active_or_customer_predictions_without_approval_mark_violation(self) -> None:
        tmp = _workspace_tmp("external-audit-violation")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_required_reports(output)
            _write_json(output / "model_registry" / "active_model.json", {"candidate_version": "v10"})
            package = write_external_audit_package()

        self.assertEqual(package["status"], "violation")
        self.assertFalse(package["active_model_confirmation"]["confirmed"])
        self.assertIn("unapproved_active_model_present", package["blocking_reasons"])

    def test_write_package_creates_expected_files_and_records_report_write_run(self) -> None:
        tmp = _workspace_tmp("external-audit-write")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_required_reports(output)
            package = write_external_audit_package()

            export_root = Path(package["export_root"])
            ledger = output / "model_research" / "run_ledger" / "research_run_ledger.jsonl"
            ledger_text = ledger.read_text(encoding="utf-8")

        self.assertTrue((export_root / "audit_index.json").exists())
        self.assertTrue((export_root / "review_summary.md").exists())
        self.assertTrue((export_root / "evidence_file_manifest.json").exists())
        self.assertTrue((export_root / "hash_manifest.json").exists())
        self.assertTrue((export_root / "redaction_report.json").exists())
        self.assertIn("external_audit_export", ledger_text)
        self.assertIn('"run_type": "report_write"', ledger_text)
        self.assertFalse(package["training_invoked"])
        self.assertFalse(package["active_updated"])
        self.assertFalse(package["customer_prediction_generated"])

    def test_validate_export_no_secrets_fails_on_raw_secret_text(self) -> None:
        result = validate_audit_export_no_secrets(
            {"summary": "Authorization: Bearer raw-secret-token-should-not-appear"}
        )

        self.assertEqual(result["status"], "fail")
        self.assertIn("secret_pattern_detected", result["blocking_reasons"])

    def test_review_summary_contains_required_sections(self) -> None:
        index = {
            "status": "incomplete",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "blocking_reasons": ["managed_proxy_disabled"],
            "missing_reports": ["managed_proxy_health"],
            "incomplete_reports": [],
            "evidence_files": {"research_decision_board": {"path": "board.json"}},
            "active_model_confirmation": {"confirmed": True},
            "customer_prediction_confirmation": {"confirmed": True},
        }

        summary = build_external_review_summary(index)

        self.assertIn("Current Status", summary)
        self.assertIn("Why System Is Blocked", summary)
        self.assertIn("What Has Been Validated", summary)
        self.assertIn("What Has Not Been Validated", summary)
        self.assertIn("No Active / No Prediction Confirmation", summary)


if __name__ == "__main__":
    unittest.main()

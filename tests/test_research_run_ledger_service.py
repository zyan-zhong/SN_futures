from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_run_ledger_service import (
    append_run_ledger,
    build_run_ledger_report,
    compute_run_output_hashes,
    finalize_research_run,
    start_research_run,
    validate_no_forbidden_side_effects,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ResearchRunLedgerServiceTest(unittest.TestCase):
    def test_safe_check_without_forbidden_outputs_finalizes_success(self) -> None:
        tmp = _workspace_tmp("run-ledger-safe")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs" / "diagnostics" / "managed_proxy_setup_report.json"
            _write(output, json.dumps({"status": "blocked", "generated_at": "2026-06-03T12:00:00"}))

            run = start_research_run(
                service_name="managed_proxy_setup",
                run_type="safe_check",
                input_paths=[],
                output_paths=[str(output)],
            )
            finalized = finalize_research_run(run)

        self.assertEqual(finalized["status"], "success")
        self.assertEqual(finalized["service_name"], "managed_proxy_setup")
        self.assertFalse(finalized["training_invoked"])
        self.assertFalse(finalized["active_updated"])
        self.assertFalse(finalized["customer_prediction_generated"])
        self.assertIn(str(output), finalized["output_hashes"])

    def test_forbidden_output_present_marks_violation(self) -> None:
        tmp = _workspace_tmp("run-ledger-violation")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            active = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            _write(active, json.dumps({"status": "unexpected"}))

            result = validate_no_forbidden_side_effects(
                {
                    "run_id": "run-test",
                    "run_type": "safe_check",
                    "forbidden_side_effects": ["active_model", "customer_prediction"],
                    "output_paths": [str(active)],
                }
            )

        self.assertEqual(result["status"], "violation")
        self.assertIn("forbidden_output:active_model", result["blocking_reasons"])

    def test_run_without_run_id_is_invalid(self) -> None:
        result = finalize_research_run({"service_name": "decision_board", "run_type": "report_refresh"})

        self.assertEqual(result["status"], "invalid")
        self.assertIn("run_id_missing", result["blocking_reasons"])

    def test_run_manifest_sanitizes_token_like_values(self) -> None:
        tmp = _workspace_tmp("run-ledger-sanitize")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            run = start_research_run(
                service_name="safe-token-service",
                run_type="safe_check",
                input_paths=["SN_TUSHARE_TOKEN=raw-secret-token-should-not-appear"],
                output_paths=[],
            )
            serialized = json.dumps(run, ensure_ascii=False)

        self.assertNotIn("raw-secret-token-should-not-appear", serialized)
        self.assertIn("SN_TUSHARE_TOKEN=***", serialized)

    def test_append_only_ledger_preserves_history(self) -> None:
        tmp = _workspace_tmp("run-ledger-append")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            first = finalize_research_run(start_research_run(service_name="decision_board", run_type="report_refresh"))
            second = finalize_research_run(start_research_run(service_name="evidence_bundle", run_type="report_refresh"))
            append_run_ledger(first)
            append_run_ledger(second)
            report = build_run_ledger_report(record_current=False)
            ledger_path = Path(report["ledger_path"])
            lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(len(lines), 2)
        self.assertEqual(report["latest_run_count"], 2)
        self.assertEqual(report["safe_check_count"], 0)
        self.assertEqual(report["heavy_task_count"], 0)

    def test_output_hashes_are_stable(self) -> None:
        tmp = _workspace_tmp("run-ledger-hash")
        path = tmp / "outputs" / "model_research" / "research_decision_board.json"
        _write(path, json.dumps({"status": "blocked"}, sort_keys=True))

        first = compute_run_output_hashes([str(path)])
        second = compute_run_output_hashes([str(path)])

        self.assertEqual(first[str(path)]["sha256"], second[str(path)]["sha256"])
        self.assertGreater(first[str(path)]["size_bytes"], 0)

    def test_refresh_report_records_current_safe_reports_without_training(self) -> None:
        tmp = _workspace_tmp("run-ledger-refresh")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            setup = Path(tmp) / "outputs" / "diagnostics" / "managed_proxy_setup_report.json"
            board = Path(tmp) / "outputs" / "model_research" / "research_decision_board.json"
            _write(setup, json.dumps({"status": "blocked", "generated_at": "2026-06-03T12:00:00"}))
            _write(board, json.dumps({"status": "blocked", "generated_at": "2026-06-03T12:00:01"}))

            report = build_run_ledger_report(record_current=True)

        self.assertEqual(report["status"], "ready")
        self.assertGreaterEqual(report["latest_run_count"], 2)
        self.assertEqual(report["violation_count"], 0)
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_observability_service import (  # noqa: E402
    build_governance_observability_report,
    collect_governance_telemetry,
    compute_error_budget_status,
    compute_governance_slo_status,
    compute_safe_check_error_rate,
    compute_safe_check_latency_metrics,
    compute_secret_scan_status,
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


def _write_ledger(output: Path, entries: list[dict[str, object]]) -> Path:
    path = output / "model_research" / "run_ledger" / "research_run_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in entries), encoding="utf-8")
    return path


def _safe_entry(run_id: str, *, status: str = "success", latency_seconds: int = 1) -> dict[str, object]:
    return {
        "run_id": run_id,
        "service_name": "managed_proxy_health",
        "run_type": "safe_check",
        "started_at": "2026-06-03T12:00:00",
        "finished_at": f"2026-06-03T12:00:{latency_seconds:02d}",
        "status": status,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _write_supporting_reports(output: Path, *, secret_findings: int = 0, stale_reports: list[str] | None = None, forbidden_violations: int = 0) -> None:
    _write_json(
        output / "model_research" / "evidence_freshness_report.json",
        {
            "status": "pass" if not stale_reports else "blocked",
            "generated_at": "2026-06-03T12:00:00",
            "stale_reports": stale_reports or [],
            "missing_reports": [],
            "missing_timestamps": [],
            "timestamp_inversions": [],
            "blocking_reasons": [f"stale:{item}" for item in stale_reports or []],
        },
    )
    _write_json(
        output / "model_research" / "governance_access_control_report.json",
        {
            "status": "guarded",
            "ui_api_violations_count": forbidden_violations,
            "forbidden_action_violation_count": forbidden_violations,
            "forbidden_actions": ["active_write", "customer_prediction_write", "secret_write"],
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
        },
    )
    _write_json(
        output / "diagnostics" / "runtime_secret_scan.json",
        {
            "scanned_at": "2026-06-03T12:00:00",
            "finding_count": secret_findings,
            "findings": [],
        },
    )


class GovernanceObservabilityServiceTest(unittest.TestCase):
    def test_missing_run_ledger_marks_observability_missing(self) -> None:
        tmp = _workspace_tmp("observability-missing-ledger")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_supporting_reports(output)

            report = build_governance_observability_report()

        self.assertEqual(report["status"], "missing")
        self.assertIn("run_ledger_missing", report["blocking_reasons"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_latency_and_error_rate_metrics_are_computed_from_safe_checks(self) -> None:
        entries = [
            _safe_entry("run-1", latency_seconds=1),
            _safe_entry("run-2", latency_seconds=2),
            _safe_entry("run-3", status="failed", latency_seconds=20),
        ]

        latency = compute_safe_check_latency_metrics(entries)
        error_rate = compute_safe_check_error_rate(entries)

        self.assertEqual(latency["safe_check_count"], 3)
        self.assertGreaterEqual(latency["p95_latency_ms"], 20000)
        self.assertEqual(error_rate["safe_check_failure_count"], 1)
        self.assertAlmostEqual(error_rate["safe_check_error_rate"], 1 / 3)

    def test_failed_secret_scan_fails_slo(self) -> None:
        tmp = _workspace_tmp("observability-secret-fail")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ledger(output, [_safe_entry("run-1")])
            _write_supporting_reports(output, secret_findings=1)

            report = build_governance_observability_report()

        self.assertEqual(report["telemetry_summary"]["secret_scan_status"], "fail")
        self.assertEqual(report["slo_results"]["secret_scan_pass"]["status"], "fail")
        self.assertIn("secret_scan_failed", report["blocking_reasons"])

    def test_stale_critical_reports_fail_slo(self) -> None:
        tmp = _workspace_tmp("observability-stale")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ledger(output, [_safe_entry("run-1")])
            _write_supporting_reports(output, stale_reports=["managed_data_audit"])

            report = build_governance_observability_report()

        self.assertEqual(report["telemetry_summary"]["stale_report_count"], 1)
        self.assertEqual(report["slo_results"]["stale_critical_reports_zero"]["status"], "fail")
        self.assertIn("stale_critical_reports_present", report["blocking_reasons"])

    def test_forbidden_action_violation_fails_slo(self) -> None:
        tmp = _workspace_tmp("observability-forbidden")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ledger(output, [_safe_entry("run-1")])
            _write_supporting_reports(output, forbidden_violations=2)

            report = build_governance_observability_report()

        self.assertEqual(report["telemetry_summary"]["forbidden_action_violation_count"], 2)
        self.assertEqual(report["slo_results"]["forbidden_action_exposure_zero"]["status"], "fail")
        self.assertIn("forbidden_action_violation_present", report["blocking_reasons"])

    def test_active_model_and_customer_prediction_outputs_fail_slo_when_unapproved(self) -> None:
        tmp = _workspace_tmp("observability-output-violations")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ledger(output, [_safe_entry("run-1")])
            _write_supporting_reports(output)
            _write_json(output / "model_registry" / "active_model.json", {"model_id": "unapproved"})
            predictions_dir = output / "customer_predictions"
            predictions_dir.mkdir(parents=True, exist_ok=True)
            (predictions_dir / "latest.json").write_text("{}", encoding="utf-8")

            report = build_governance_observability_report()

        self.assertEqual(report["telemetry_summary"]["active_model_violation_count"], 1)
        self.assertEqual(report["telemetry_summary"]["customer_prediction_violation_count"], 1)
        self.assertEqual(report["slo_results"]["active_prediction_violations_zero"]["status"], "fail")
        self.assertIn("active_model_violation_present", report["blocking_reasons"])
        self.assertIn("customer_prediction_violation_present", report["blocking_reasons"])

    def test_high_latency_consumes_error_budget(self) -> None:
        telemetry = {
            "safe_check_error_rate": 0.0,
            "p95_latency_ms": 15000,
            "safe_check_count": 3,
            "safe_check_failure_count": 0,
        }

        budget = compute_error_budget_status(telemetry)

        self.assertEqual(budget["status"], "consumed")
        self.assertIn("latency_budget_consumed", budget["budget_events"])

    def test_high_failure_rate_exhausts_error_budget(self) -> None:
        telemetry = {
            "safe_check_error_rate": 0.50,
            "p95_latency_ms": 1000,
            "safe_check_count": 4,
            "safe_check_failure_count": 2,
        }

        budget = compute_error_budget_status(telemetry)

        self.assertEqual(budget["status"], "exhausted")
        self.assertEqual(budget["remaining_ratio"], 0.0)

    def test_pass_report_contains_required_observability_shape_and_no_token_words(self) -> None:
        tmp = _workspace_tmp("observability-pass")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ledger(output, [_safe_entry("run-1"), _safe_entry("run-2")])
            _write_supporting_reports(output)

            telemetry = collect_governance_telemetry()
            secret = compute_secret_scan_status()
            slo = compute_governance_slo_status(telemetry)
            report = build_governance_observability_report()

        self.assertEqual(secret["status"], "pass")
        self.assertEqual(slo["status"], "pass")
        self.assertEqual(report["status"], "pass")
        self.assertGreaterEqual(report["telemetry_summary"]["safe_check_success_count"], 2)
        self.assertEqual(report["telemetry_summary"]["safe_check_error_rate"], 0.0)
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("raw-secret", serialized)
        self.assertNotIn("endpoint secret", serialized)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.evidence_freshness_service import (
    build_evidence_freshness_report,
    collect_evidence_timestamps,
    compute_report_age,
    detect_cross_report_version_mismatch,
    detect_stale_reports,
    detect_upstream_downstream_timestamp_inversion,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"
BASE_TIME = datetime(2026, 6, 3, 12, 0, 0)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ts(hours_delta: int = 0) -> str:
    return (BASE_TIME + timedelta(hours=hours_delta)).isoformat(timespec="seconds")


class EvidenceFreshnessServiceTest(unittest.TestCase):
    def test_missing_generated_at_is_incomplete_and_blocking(self) -> None:
        tmp = _workspace_tmp("freshness-missing-ts")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "diagnostics" / "managed_proxy_health.json", {"status": "ready"})

            timestamps = collect_evidence_timestamps()
            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertEqual(timestamps["managed_proxy_health"]["timestamp_status"], "missing")
        self.assertIn("managed_proxy_health", report["missing_timestamps"])
        self.assertEqual(report["status"], "blocked")
        self.assertIn("freshness:managed_proxy_health_missing_generated_at", report["blocking_reasons"])

    def test_report_age_over_threshold_is_stale_and_not_pass(self) -> None:
        tmp = _workspace_tmp("freshness-stale-health")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {"status": "ready", "generated_at": _ts(-30), "v12_allowed": True},
            )

            timestamps = collect_evidence_timestamps()
            stale = detect_stale_reports(timestamps, now=BASE_TIME)
            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertGreater(compute_report_age(_ts(-30), now=BASE_TIME), 24)
        self.assertIn("managed_proxy_health", stale)
        self.assertIn("managed_proxy_health", report["stale_reports"])
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_downstream_report_older_than_upstream_is_timestamp_inversion(self) -> None:
        tmp = _workspace_tmp("freshness-inversion-fs")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "ready", "generated_at": _ts(0)})
            _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "ready", "generated_at": _ts(-2)})

            timestamps = collect_evidence_timestamps()
            inversions = detect_upstream_downstream_timestamp_inversion(timestamps)
            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertIn(
            {"upstream": "managed_data_audit", "downstream": "feature_store_v12_manifest"},
            [{key: item[key] for key in ("upstream", "downstream")} for item in inversions],
        )
        self.assertTrue(any(item["downstream"] == "feature_store_v12_manifest" for item in report["timestamp_inversions"]))
        self.assertIn("freshness:feature_store_v12_manifest_older_than_managed_data_audit", report["blocking_reasons"])

    def test_candidate_report_older_than_training_dataset_is_stale(self) -> None:
        tmp = _workspace_tmp("freshness-candidate-before-td")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "training_dataset_manifest_v12.json", {"status": "ready", "generated_at": _ts(0), "dataset_version": "v12"})
            _write_json(
                output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
                {"status": "success", "generated_at": _ts(-1), "dataset_version": "v12"},
            )

            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertTrue(any(item["upstream"] == "training_dataset_v12_manifest" for item in report["timestamp_inversions"]))
        self.assertIn("freshness:candidate_v12_report_older_than_training_dataset_v12_manifest", report["blocking_reasons"])

    def test_training_dataset_older_than_feature_store_is_stale(self) -> None:
        tmp = _workspace_tmp("freshness-td-before-fs")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "ready", "generated_at": _ts(0)})
            _write_json(output / "training_dataset_manifest_v12.json", {"status": "ready", "generated_at": _ts(-1)})

            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertTrue(any(item["downstream"] == "training_dataset_v12_manifest" for item in report["timestamp_inversions"]))
        self.assertIn("freshness:training_dataset_v12_manifest_older_than_feature_store_v12_manifest", report["blocking_reasons"])

    def test_feature_store_older_than_pit_audit_is_stale(self) -> None:
        tmp = _workspace_tmp("freshness-fs-before-audit")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "ready", "generated_at": _ts(0)})
            _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "ready", "generated_at": _ts(-1)})

            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertTrue(any(item["upstream"] == "managed_data_audit" for item in report["timestamp_inversions"]))
        self.assertIn("feature_store_v12_manifest", {item["downstream"] for item in report["timestamp_inversions"]})

    def test_version_mismatch_is_reported(self) -> None:
        tmp = _workspace_tmp("freshness-version-mismatch")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(output / "training_dataset_manifest_v12.json", {"status": "ready", "generated_at": _ts(0), "dataset_version": "v12"})
            _write_json(
                output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
                {"status": "success", "generated_at": _ts(1), "dataset_version": "v11"},
            )

            timestamps = collect_evidence_timestamps()
            mismatches = detect_cross_report_version_mismatch(timestamps)
            report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertTrue(mismatches)
        self.assertIn("candidate_v12_report", {item["report"] for item in report["version_mismatches"]})
        self.assertIn("freshness:candidate_v12_report_dataset_version_mismatch", report["blocking_reasons"])

    def test_freshness_auditor_does_not_trigger_heavy_downstream_actions(self) -> None:
        tmp = _workspace_tmp("freshness-no-heavy")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            with patch("sn_futures.services.feature_store_v12_service.build_feature_store_v12", side_effect=AssertionError("no fs build")):
                with patch("sn_futures.services.training_dataset_v12_service.build_training_dataset_v12", side_effect=AssertionError("no td build")):
                    with patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_research", side_effect=AssertionError("no candidate")):
                        report = build_evidence_freshness_report(now=BASE_TIME)

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

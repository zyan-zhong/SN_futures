from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.candidate_v12_research_service import run_candidate_v12_research, validate_candidate_v12_readiness


class CandidateV12BlockedFirstTest(unittest.TestCase):
    def test_missing_training_dataset_manifest_blocks_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = run_candidate_v12_research(build_missing=False)
            report_path = Path(result["report_path"])
            report_exists = report_path.exists()
            oof_dir = Path(tmp) / "outputs" / "walk_forward" / "v12"
            active_model_path = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            customer_predictions_dir = Path(tmp) / "outputs" / "customer_predictions"

        self.assertEqual(result["candidate_version"], "v12")
        self.assertEqual(result["dataset_version"], "v12")
        self.assertEqual(result["feature_store_version"], "v12")
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(report_exists)
        self.assertIn("training_dataset_v12_manifest_missing", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        self.assertEqual(result["oof_trace_path"], "")
        self.assertEqual(result["cpcv_report_path"], "")
        self.assertEqual(result["promotion_dry_run_result"]["status"], "skipped")
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(active_model_path.exists())
        self.assertFalse(customer_predictions_dir.exists())
        self.assertFalse(any(oof_dir.glob("oof_trace_*.csv")) if oof_dir.exists() else False)

    def test_blocked_training_dataset_never_invokes_research_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            manifest_path = output / "training_dataset_manifest_v12.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """
                {
                  "status": "blocked",
                  "dataset_version": "v12",
                  "feature_store_version": "v12",
                  "feature_store_status": "blocked",
                  "dataset_paths": {},
                  "no_lookahead_pass": false,
                  "point_in_time_join_ready": false,
                  "candidate_v12_allowed": false,
                  "managed_data_used": false,
                  "fake_data_used": false,
                  "mock_data_used": false,
                  "blocked_reasons": ["managed_proxy_disabled"]
                }
                """,
                encoding="utf-8",
            )
            with (
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_research_training") as training,
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_cpcv_validation") as cpcv,
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_promotion_dry_run") as promotion,
            ):
                result = run_candidate_v12_research(build_missing=False)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("training_dataset_v12_blocked", result["blocking_reasons"])
        self.assertIn("managed_proxy_disabled", result["blocking_reasons"])
        self.assertFalse(result["readiness_checks"]["candidate_v12_allowed"]["passed"])
        training.assert_not_called()
        cpcv.assert_not_called()
        promotion.assert_not_called()

    def test_readiness_blocks_when_any_v12_gate_flag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            dataset_dir = output / "training_datasets" / "v12"
            dataset_dir.mkdir(parents=True)
            paths = {h: str(dataset_dir / f"train_{h}.parquet") for h in ("1d", "3d", "5d", "10d", "20d")}
            (output / "training_dataset_manifest_v12.json").write_text(
                __import__("json").dumps(
                    {
                        "status": "ready",
                        "dataset_version": "v12",
                        "feature_store_version": "v12",
                        "feature_store_status": "blocked",
                        "dataset_paths": paths,
                        "no_lookahead_pass": False,
                        "point_in_time_join_ready": False,
                        "candidate_v12_allowed": False,
                        "managed_data_used": True,
                        "fake_data_used": False,
                        "mock_data_used": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            readiness = validate_candidate_v12_readiness()

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("feature_store_v12_blocked", readiness["blocking_reasons"])
        self.assertIn("training_dataset_v12_no_lookahead_failed", readiness["blocking_reasons"])
        self.assertIn("training_dataset_v12_pit_not_ready", readiness["blocking_reasons"])
        self.assertIn("candidate_v12_not_allowed_by_dataset", readiness["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()

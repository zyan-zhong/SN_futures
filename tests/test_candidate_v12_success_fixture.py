from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.candidate_v12_research_service import run_candidate_v12_research


def _write_ready_training_dataset_v12(root: str) -> None:
    output = Path(root) / "outputs"
    dataset_dir = output / "training_datasets" / "v12"
    feature_dir = output / "feature_store" / "v12"
    dataset_dir.mkdir(parents=True)
    feature_dir.mkdir(parents=True)
    dataset_paths: dict[str, str] = {}
    for horizon in ("1d", "3d", "5d", "10d", "20d"):
        path = dataset_dir / f"train_{horizon}.parquet"
        pd.DataFrame(
            {
                "trade_date": pd.date_range("2026-01-01", periods=12).strftime("%Y-%m-%d"),
                "horizon": horizon,
                "target_return": [0.01, -0.004, 0.006, 0.002, -0.003, 0.008, 0.004, -0.002, 0.007, 0.003, -0.001, 0.005],
                "target_direction": [1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1],
                "split": ["train"] * 9 + ["validation"] * 3,
                "sample_weight": [1.0] * 12,
                "managed_regime_label": ["managed_tight_basis", "managed_range", "managed_loose_inventory"] * 4,
            }
        ).to_parquet(path, index=False)
        dataset_paths[horizon] = str(path)
    (feature_dir / "feature_store.csv").write_text("trade_date,close\n2026-01-01,210000\n", encoding="utf-8")
    (feature_dir / "feature_store_manifest.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "feature_store_version": "v12",
                "feature_store_path": str(feature_dir / "feature_store.csv"),
                "no_lookahead_pass": True,
                "point_in_time_join_ready": True,
                "managed_data_used": True,
                "fake_data_used": False,
                "mock_data_used": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output / "training_dataset_manifest_v12.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "dataset_version": "v12",
                "feature_store_version": "v12",
                "feature_store_status": "ready",
                "feature_store_manifest_path": str(feature_dir / "feature_store_manifest.json"),
                "dataset_paths": dataset_paths,
                "no_lookahead_pass": True,
                "point_in_time_join_ready": True,
                "candidate_v12_allowed": True,
                "managed_data_used": True,
                "fake_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class CandidateV12SuccessFixtureTest(unittest.TestCase):
    def test_ready_dataset_runs_research_only_pipeline_and_dry_run_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_ready_training_dataset_v12(tmp)
            with (
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_research_training") as training,
                patch("sn_futures.services.candidate_v12_research_service.build_candidate_v12_oof_trace") as oof,
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_cpcv_validation") as cpcv,
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_institutional_validation") as institutional,
                patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_promotion_dry_run") as promotion,
            ):
                training.return_value = {"status": "success", "candidate_version": "v12", "active_updated": False}
                oof.return_value = {"status": "success", "oof_trace_path": str(Path(tmp) / "outputs" / "walk_forward" / "v12" / "oof_trace_5d.csv")}
                cpcv.return_value = {
                    "status": "success",
                    "report_path": str(Path(tmp) / "outputs" / "validation" / "cpcv" / "candidate_v12_cpcv_report.json"),
                    "pbo": {"pbo": 0.1},
                    "reality_check": {"passed": True, "aggregate_p_value": 0.03},
                }
                institutional.return_value = {
                    "status": "success",
                    "passed": True,
                    "cost_stress": {"2x_cost": {"expectancy": 0.01}, "3x_cost": {"expectancy": 0.008}},
                    "dominance_checks": {
                        "single_regime_contribution": 0.35,
                        "single_fold_contribution": 0.3,
                        "single_year_contribution": 0.32,
                    },
                }
                promotion.return_value = {"status": "success", "passed": True, "dry_run": True, "active_updated": False}

                result = run_candidate_v12_research(build_missing=False)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["candidate_version"], "v12")
        self.assertEqual(result["dataset_version"], "v12")
        self.assertEqual(result["feature_store_version"], "v12")
        self.assertTrue(result["training_invoked"])
        self.assertTrue(result["gate_checks"]["pbo_lt_0_2"])
        self.assertTrue(result["gate_checks"]["reality_check_pass"])
        self.assertTrue(result["gate_checks"]["year_concentration_pass"])
        self.assertTrue(result["gate_checks"]["institutional_cost_stress_pass"])
        self.assertTrue(result["manual_approval_recommended"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(result["fake_data_used"])
        self.assertFalse(result["mock_data_used"])
        self.assertEqual(training.call_args.kwargs["dataset_version"], "v12")
        self.assertEqual(training.call_args.kwargs["feature_store_version"], "v12")
        promotion.assert_called_once()


if __name__ == "__main__":
    unittest.main()

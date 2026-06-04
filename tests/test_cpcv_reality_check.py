from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.cpcv_validation_service import build_cpcv_report, reality_check_by_path


class CPCVRealityCheckTest(unittest.TestCase):
    def test_reality_check_reports_path_level_bootstrap_p_values(self) -> None:
        path_metrics = [
            {
                "path_id": f"path_{idx}",
                "selected_strategy": "stable",
                "strategy_metrics": {
                    "stable": {
                        "train_metric": 0.010 + idx * 0.001,
                        "test_metric": 0.009 + idx * 0.001,
                        "test_returns": [0.010, 0.012, 0.009, 0.011, 0.013, 0.010],
                    }
                },
            }
            for idx in range(4)
        ]

        result = reality_check_by_path(path_metrics, bootstrap_samples=120, seed=7)

        self.assertEqual(result["path_count"], 4)
        self.assertEqual(len(result["reality_check_by_path"]), 4)
        self.assertLessEqual(result["aggregate_p_value"], 0.05)
        self.assertTrue(result["passed"])
        self.assertEqual(result["method"], "cpcv_path_bootstrap_reality_check")

    def test_build_cpcv_report_writes_research_only_artifact(self) -> None:
        path_metrics = [
            {
                "path_id": "path_1",
                "strategy_metrics": {
                    "stable": {"train_metric": 0.020, "test_metric": 0.018, "test_returns": [0.01, 0.011, 0.012, 0.013, 0.014]},
                    "weak": {"train_metric": 0.004, "test_metric": 0.003, "test_returns": [0.001, 0.002, 0.003, 0.001, 0.002]},
                },
            },
            {
                "path_id": "path_2",
                "strategy_metrics": {
                    "stable": {"train_metric": 0.019, "test_metric": 0.017, "test_returns": [0.011, 0.012, 0.010, 0.014, 0.012]},
                    "weak": {"train_metric": 0.003, "test_metric": 0.002, "test_returns": [0.001, 0.002, 0.001, 0.003, 0.001]},
                },
            },
        ]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = build_cpcv_report(candidate_version="v9", path_metrics=path_metrics)
            report_path = Path(report["report_path"])
            payload = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertTrue(report_path.exists())
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
            self.assertFalse((Path(tmp) / "outputs" / "customer_predictions.json").exists())

        self.assertEqual(payload["candidate_version"], "v9")
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["research_only"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertIn("pbo", payload)
        self.assertIn("reality_check", payload)

    def test_build_cpcv_report_handles_oof_without_regime_neutral_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            oof_dir = Path(tmp) / "outputs" / "walk_forward" / "v10"
            oof_dir.mkdir(parents=True, exist_ok=True)
            rows = ["realized_return,predicted_direction,is_high_confidence_top_10,is_high_confidence_top_20"]
            rows.extend(["0.01,1,1,1", "0.02,1,1,1", "-0.01,-1,0,1", "0.015,1,0,1"] * 4)
            (oof_dir / "oof_trace_5d.csv").write_text("\n".join(rows), encoding="utf-8")

            report = build_cpcv_report(candidate_version="v10", n_groups=4, test_group_count=1, bootstrap_samples=40)

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["candidate_version"], "v10")
        self.assertEqual(report["source"], "walk_forward_oof_v10")
        self.assertIn("pbo", report)
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_terminal_api_exposes_cpcv_research_validation_report(self) -> None:
        with patch("sn_futures.api.terminal_api.build_cpcv_report") as build_report:
            build_report.return_value = {
                "status": "success",
                "candidate_version": "v9",
                "split_count": 15,
                "research_only": True,
                "active_updated": False,
                "customer_prediction_generated": False,
            }

            status, payload = handle_terminal_api(
                "/api/terminal/research/cpcv-report",
                method="GET",
                query={"candidate_version": "v9"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["split_count"], 15)
        self.assertTrue(payload["research_only"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

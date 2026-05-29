from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.candidate_diagnostics_service import build_candidate_diagnostics_report


def _write_candidate_fixture(root: str) -> None:
    output = Path(root) / "outputs"
    registry = output / "model_registry"
    wf_dir = output / "walk_forward"
    ds_dir = output / "training_datasets"
    registry.mkdir(parents=True, exist_ok=True)
    wf_dir.mkdir(parents=True, exist_ok=True)
    ds_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "feature_cols": ["close", "volume", "regime_label"],
        "label_cols": ["ret_1d", "direction_1d"],
        "leakage_check_pass": True,
        "sample_data_used": False,
        "baseline_used": False,
        "sample_count_by_horizon": {"1d": 120},
        "feature_count": 3,
        "label_distribution_by_horizon": {"1d": {"1": 60, "-1": 55, "0": 5}},
        "return_summary_by_horizon": {"1d": {"mean": 0.001, "std": 0.02, "min": -0.04, "max": 0.05}},
        "dataset_paths": {"1d": str(ds_dir / "train_1d.csv")},
    }
    (output / "training_dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(
        {
            "label_start_time": pd.date_range("2025-01-01", periods=120, freq="D").astype(str),
            "y_return": [0.01 if i % 2 else -0.008 for i in range(120)],
            "y_direction": [1 if i % 2 else -1 for i in range(120)],
            "regime_label": ["TREND_UP" if i < 60 else "RANGE" for i in range(120)],
            "close": [210000 + i for i in range(120)],
            "volume": [1000 + i for i in range(120)],
        }
    ).to_csv(ds_dir / "train_1d.csv", index=False)
    metrics = {
        "directional_accuracy": 0.45,
        "precision_up": 0.42,
        "precision_down": 0.31,
        "recall_up": 0.2,
        "recall_down": 0.1,
        "brier_score": 0.26,
        "calibration_error": 0.03,
        "coverage_rate": 0.25,
        "cost_adjusted_expectancy": -0.001,
        "max_drawdown_proxy": -0.12,
        "sample_count": 120,
    }
    (registry / "candidate_training_status.json").write_text(
        json.dumps({"status": "success", "metrics_by_horizon": {"1d": metrics}, "records": [{"horizon": "1d", "model_id": "candidate_x"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (registry / "promotion_report.json").write_text(
        json.dumps({"decisions": [{"horizon": "1d", "failure_reasons": ["方向准确率未显著超过朴素阈值", "Brier 概率误差过高"]}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (wf_dir / "wf_1d.json").write_text(
        json.dumps(
            {
                "horizon": "1d",
                "metrics": metrics,
                "folds": [
                    {
                        "fold": 1,
                        "validation_start": "2025-04-01",
                        "validation_end": "2025-05-01",
                        "validation_samples": 30,
                        "metrics": metrics,
                        "feature_importance": [{"feature": "close", "importance": 0.7}, {"feature": "volume", "importance": 0.3}],
                    }
                ],
                "feature_importance": [{"feature": "close", "importance": 0.7}, {"feature": "volume", "importance": 0.3}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class CandidateDiagnosticsServiceTest(unittest.TestCase):
    def test_no_candidate_returns_chinese_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_candidate_diagnostics_report()
        self.assertEqual(payload["status"], "no_candidate")
        self.assertFalse(payload["active_written"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertIn("暂无 candidate", payload["message_zh"])

    def test_candidate_diagnostics_contains_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_candidate_fixture(tmp)
            payload = build_candidate_diagnostics_report()
        self.assertEqual(payload["status"], "success")
        self.assertIn("1d", payload["horizons"])
        item = payload["horizons"]["1d"]
        self.assertIn("confusion_matrix", item)
        self.assertIn("calibration_bins", item)
        self.assertIn("confidence_deciles", item)
        self.assertIn("regime_performance", item)
        self.assertIn("feature_importance_top", item)
        self.assertGreaterEqual(item["confidence_deciles"][0]["coverage"], 0)
        self.assertFalse(payload["active_written"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

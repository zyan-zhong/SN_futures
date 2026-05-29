from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.model_promotion_service import evaluate_promotion_gate, get_active_model_status, promote_candidate


def _write_candidate_state(root: str, *, metrics: dict | None = None, manifest_updates: dict | None = None) -> Path:
    output = Path(root) / "outputs"
    registry_dir = output / "model_registry"
    artifact_dir = registry_dir / "candidate_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / "candidate_1d.json"
    artifact.write_text(json.dumps({"model": "candidate"}, ensure_ascii=False), encoding="utf-8")
    base_metrics = {
        "fold_count": 5,
        "sample_count": 800,
        "directional_accuracy": 0.58,
        "naive_directional_accuracy": 0.50,
        "brier_score": 0.20,
        "calibration_error": 0.04,
        "cost_adjusted_expectancy": 0.01,
        "max_drawdown_proxy": -0.08,
    }
    base_metrics.update(metrics or {})
    record = {
        "model_id": "candidate_test_1d",
        "model_type": "hist_gradient_boosting_candidate",
        "horizon": "1d",
        "feature_set_version": "test",
        "label_version": "test",
        "train_period": {},
        "validation_period": {},
        "test_period": {},
        "created_at": "2026-05-25T00:00:00",
        "status": "candidate",
        "metrics": base_metrics,
        "artifact_path": str(artifact),
        "data_quality_snapshot": {"sample_data_used": False, "baseline_used": False, "data_quality_score": 0.95},
        "feature_columns": ["close", "rsi_14"],
        "label_columns": ["direction_1d", "ret_1d"],
    }
    (registry_dir / "candidate_model_registry.json").write_text(
        json.dumps({"models": [record]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (registry_dir / "candidate_training_status.json").write_text(
        json.dumps({"status": "success", "metrics_by_horizon": {"1d": base_metrics}, "records": [record]}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "status": "success",
        "exists": True,
        "sample_data_used": False,
        "baseline_used": False,
        "leakage_check_pass": True,
        "feature_count": 2,
        "missing_rate_by_feature": {"close": 0.0, "rsi_14": 0.05},
        "data_quality_score": 0.95,
    }
    manifest.update(manifest_updates or {})
    (output / "training_dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return output


class ModelPromotionServiceTest(unittest.TestCase):
    def test_gate_pass_writes_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_candidate_state(tmp)
            report = promote_candidate()
            self.assertTrue(report["passed"])
            self.assertTrue(report["active_updated"])
            active_path = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            self.assertTrue(active_path.exists())
            active = get_active_model_status()
            self.assertTrue(active["exists"])

    def test_cost_expectancy_fail_does_not_write_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_candidate_state(tmp, metrics={"cost_adjusted_expectancy": 0.0})
            report = promote_candidate()
            self.assertFalse(report["passed"])
            self.assertFalse(report["active_updated"])
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
            self.assertTrue((Path(tmp) / "outputs" / "model_registry" / "candidate_rejected.json").exists())
            dumped = json.dumps(report, ensure_ascii=False)
            self.assertIn("成本后期望不为正", dumped)

    def test_sample_and_leakage_fail_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_candidate_state(tmp, manifest_updates={"sample_data_used": True, "leakage_check_pass": False})
            report = evaluate_promotion_gate()
            dumped = json.dumps(report, ensure_ascii=False)
            self.assertFalse(report["passed"])
            self.assertIn("样例数据不可晋级", dumped)
            self.assertIn("泄漏检查未通过", dumped)


if __name__ == "__main__":
    unittest.main()

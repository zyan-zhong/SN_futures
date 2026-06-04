from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v8_research_service import run_candidate_v8_research
from sn_futures.services.model_promotion_service import evaluate_promotion_gate
from sn_futures.services.stable_strategy_policy_service import V7_ALLOWED_MODELS, build_stable_strategy_policy


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class PboReductionWithoutComplexityTest(unittest.TestCase):
    def test_policy_uses_no_more_complex_model_set_and_training_fold_only_rules(self) -> None:
        policy = build_stable_strategy_policy(
            source_candidate_version="v7",
            target_candidate_version="v8",
            horizon_metrics={"5d": {"max_drawdown_proxy": -0.1, "directional_accuracy": 0.55, "naive_directional_accuracy": 0.5, "brier_score": 0.2}},
            institutional_validation={"probability_of_backtest_overfitting": {"pbo": 1.0}},
            feature_stability={"stable_features": ["fee_rate"], "unstable_features": ["unstable_factor"]},
            v7_models=V7_ALLOWED_MODELS,
        )

        self.assertTrue(set(policy["complexity"]["models"]).issubset(set(V7_ALLOWED_MODELS)))
        self.assertTrue(policy["complexity"]["not_higher_than_v7"])
        self.assertTrue(policy["training_fold_only_selection"])
        self.assertFalse(policy["validation_fold_tuning"])
        self.assertFalse(policy["uses_final_backtest_for_tuning"])

    def test_candidate_v8_runs_dry_run_only_and_does_not_write_active(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False),
            patch("sn_futures.services.candidate_v8_research_service.run_candidate_training") as train,
            patch("sn_futures.services.candidate_v8_research_service.run_research_backtest") as backtest,
            patch("sn_futures.services.candidate_v8_research_service.build_feature_stability_evidence") as stability,
            patch("sn_futures.services.candidate_v8_research_service.run_institutional_validation") as validate,
            patch("sn_futures.services.candidate_v8_research_service.promote_candidate") as promote,
            patch("sn_futures.services.candidate_v8_research_service.archive_research_run") as archive,
        ):
            out = Path(tmp) / "outputs"
            _write(
                out / "feature_store" / "v7" / "feature_store_manifest.json",
                {
                    "version": "v7",
                    "status": "success",
                    "usable_fields": ["fee_rate", "cost_pressure_score", "member_position_available_flag"],
                    "cost_features": ["fee_rate", "cost_pressure_score"],
                    "positioning_features": ["member_position_available_flag"],
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "no_lookahead_pass": True,
                    "leakage_check_pass": True,
                },
            )
            _write(
                out / "training_dataset_manifest_v7.json",
                {
                    "dataset_version": "v7",
                    "status": "success",
                    "feature_cols": ["fee_rate", "cost_pressure_score", "member_position_available_flag"],
                    "leakage_check_pass": True,
                    "no_lookahead_pass": True,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                },
            )
            train.return_value = {"status": "success", "candidate_version": "v8", "registry_path": str(out / "model_registry" / "candidate_v8_model_registry.json")}
            backtest.return_value = {"status": "success", "horizons": {"5d": {"metrics": {"turnover": 0.1, "trade_count": 12, "max_drawdown": -0.05}}}}
            stability.return_value = {"status": "success", "stability_score": 0.60, "stable_features": ["fee_rate"], "unstable_features": []}
            validate.return_value = {
                "status": "success",
                "passed": False,
                "probability_of_backtest_overfitting": {"pbo": 0.8},
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.1},
                "reality_check": {"p_value": 0.7},
            }
            promote.return_value = {"status": "failed", "passed": False, "active_updated": False}
            archive.return_value = {"artifact_dir": str(out / "research_artifacts" / "v8"), "run_id": "v8-test"}

            result = run_candidate_v8_research(horizons=("5d",), build_missing=False)

        train.assert_called_once()
        self.assertEqual(train.call_args.kwargs["candidate_version"], "v8")
        self.assertEqual(train.call_args.kwargs["dataset_version"], "v7")
        self.assertEqual(train.call_args.kwargs["feature_set"], "tushare_cost_positioning_stable")
        self.assertTrue(set(train.call_args.kwargs["models"]).issubset(set(V7_ALLOWED_MODELS)))
        validate.assert_called_once_with(candidate_version="v8", dry_run=True)
        promote.assert_called_once_with(candidate_version="v8", dry_run=True)
        self.assertTrue(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())

    def test_candidate_v8_promotion_uses_declared_dataset_v7_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            record = {
                "model_id": "candidate_v8_policy_adjusted_20d",
                "model_type": "hist_gradient_boosting_candidate",
                "horizon": "20d",
                "feature_set_version": "v7",
                "label_version": "forward_return_triple_barrier_20d",
                "train_period": {"start": "2020-01-01", "end": "2025-01-01"},
                "validation_period": {"method": "purged_walk_forward", "fold_count": "5"},
                "test_period": {"status": "not_promoted_no_customer_prediction"},
                "created_at": "2026-06-01T00:00:00",
                "status": "candidate",
                "metrics": {
                    "fold_count": 5,
                    "sample_count": 500,
                    "directional_accuracy": 0.58,
                    "naive_directional_accuracy": 0.50,
                    "brier_score": 0.20,
                    "calibration_error": 0.03,
                    "cost_adjusted_expectancy": 0.01,
                    "max_drawdown_proxy": -0.08,
                },
                "artifact_path": str(out / "model_registry" / "candidate_artifacts" / "v8" / "model.json"),
                "data_quality_snapshot": {"dataset_version": "v7", "data_quality_score": 1.0},
                "feature_columns": ["fee_rate", "cost_pressure_score"],
                "label_columns": ["direction_20d", "ret_20d"],
            }
            _write(
                out / "model_registry" / "candidate_v8_training_status.json",
                {
                    "status": "success",
                    "candidate_version": "v8",
                    "dataset_version": "v7",
                    "records": [record],
                    "metrics_by_horizon": {"20d": record["metrics"]},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )
            _write(out / "model_registry" / "candidate_v8_model_registry.json", {"models": [record]})
            _write(
                out / "training_dataset_manifest_v7.json",
                {
                    "status": "success",
                    "dataset_version": "v7",
                    "feature_count": 2,
                    "missing_rate_by_feature": {"fee_rate": 0.0, "cost_pressure_score": 0.0},
                    "leakage_check_pass": True,
                    "sample_data_used": False,
                    "baseline_used": False,
                    "mock_data_used": False,
                    "data_quality_score": 1.0,
                },
            )

            report = evaluate_promotion_gate(candidate_version="v8", dry_run=True)

        self.assertTrue(report["passed"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        failures = [reason for decision in report["decisions"] for reason in decision.get("failure_reasons", [])]
        self.assertNotIn("泄漏检查未通过", failures)


if __name__ == "__main__":
    unittest.main()

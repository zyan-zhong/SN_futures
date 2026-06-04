from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v6_gated_research_service import run_candidate_v6_gated_research


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _coverage_report(output_dir: Path, *, positive_delta: bool = False) -> None:
    delta = 0.4 if positive_delta else 0.0
    before = 0.0 if positive_delta else 0.166667
    after = 0.4 if positive_delta else 0.166667
    _write_json(
        output_dir / "diagnostics" / "data_source_coverage_improvement.json",
        {
            "status": "success",
            "source_status": {
                "tushare": {"status": "token_missing", "configured": False},
                "managed_proxy": {"status": "disabled", "enabled": False},
                "alpha": {"status": "using_cache_rate_limited", "configured": True, "from_cache": True},
                "newsapi": {"status": "success", "configured": True},
            },
            "feature_coverage_delta": {
                "cross_market": {"before": before, "after": after, "delta": delta},
                "event": {"before": 0.875, "after": 0.875, "delta": 0.0},
                "basis": {"before": 0.0, "after": 0.0, "delta": 0.0},
                "inventory": {"before": 0.0, "after": 0.0, "delta": 0.0},
                "term_structure": {"before": 0.166667, "after": 0.166667, "delta": 0.0},
            },
            "feature_store_v5": {
                "status": "success",
                "usable_fields": ["usd_cny_return", "us10y_change", "supply_shock_score"],
                "leakage_check_pass": True,
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "group_coverage": {
                    "cross_market": {"coverage_rate": after, "usable_fields": ["usd_cny_return", "us10y_change"]},
                    "event": {"coverage_rate": 0.875, "usable_fields": ["supply_shock_score"]},
                },
            },
        },
    )


def _real_data_validation_report(output_dir: Path, *, ready: bool = True) -> None:
    before_rate = 0.0
    after_rate = 0.4 if ready else 0.0
    usable_fields = ["usd_cny_return", "us10y_change", "supply_shock_score"] if ready else []
    _write_json(
        output_dir / "diagnostics" / "real_data_coverage_validation.json",
        {
            "status": "success",
            "feature_coverage_before": {
                "groups": [
                    {"group": "cross_market", "coverage_rate": before_rate},
                    {"group": "event", "coverage_rate": 0.875},
                ],
            },
            "feature_coverage_after": {
                "groups": [
                    {"group": "cross_market", "coverage_rate": after_rate},
                    {"group": "event", "coverage_rate": 0.875},
                ],
            },
            "feature_store_v5": {
                "status": "success",
                "usable_fields": usable_fields,
                "no_lookahead_pass": True,
                "leakage_check_pass": True,
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
            },
        },
    )


def _feature_stability_report(output_dir: Path, *, passed: bool = True) -> None:
    _write_json(
        output_dir / "model_registry" / "feature_stability_report_v5.json",
        {
            "candidate_version": "v5",
            "evidence_status": "success" if passed else "missing",
            "stability_score": 0.71 if passed else 0.0,
            "threshold": 0.55,
            "passed": passed,
            "stable_features": ["usd_cny_return", "supply_shock_score"] if passed else [],
            "unstable_features": [] if passed else ["usd_cny_return"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class CandidateV6GatedResearchServiceTest(unittest.TestCase):
    def test_blocks_without_feature_coverage_increment_and_does_not_train(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _coverage_report(output, positive_delta=False)
            _real_data_validation_report(output, ready=False)
            _feature_stability_report(output, passed=True)
            with patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer:
                result = run_candidate_v6_gated_research(horizons=("1d",))

        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["v6_admission"]["eligible"])
        self.assertIn("feature_coverage_delta_empty", result["v6_admission"]["blocked_reasons"])
        self.assertEqual(result["candidate"]["status"], "not_run")
        self.assertFalse((output / "model_registry" / "candidate_v6_model_registry.json").exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())

    def test_blocks_when_prompt90_readiness_is_not_ready_even_if_coverage_report_has_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _coverage_report(output, positive_delta=True)
            _real_data_validation_report(output, ready=False)
            _feature_stability_report(output, passed=True)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer:
                result = run_candidate_v6_gated_research(horizons=("1d",))

        dataset.assert_not_called()
        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_v6_readiness_not_ready", result["blocking_reasons"])
        self.assertIn("new_real_factor_group_missing", result["blocking_reasons"])
        self.assertEqual(result["candidate_v6_readiness"]["status"], "blocked")
        self.assertEqual(result["candidate"]["status"], "not_run")
        self.assertEqual(result["promotion_dry_run"]["status"], "not_run")

    def test_blocks_when_feature_stability_evidence_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _coverage_report(output, positive_delta=True)
            _real_data_validation_report(output, ready=True)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer:
                result = run_candidate_v6_gated_research(horizons=("1d",))

        dataset.assert_not_called()
        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("feature_stability_evidence_missing", result["blocking_reasons"])
        self.assertEqual(result["feature_stability_evidence"]["evidence_status"], "missing")
        self.assertEqual(result["candidate"]["status"], "not_run")

    def test_runs_candidate_v6_research_chain_when_admission_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _coverage_report(output, positive_delta=True)
            _real_data_validation_report(output, ready=True)
            _feature_stability_report(output, passed=True)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer, \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report") as oof, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest") as backtest, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation") as validation, \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate") as promote:
                dataset.return_value = {
                    "status": "success",
                    "dataset_version": "v6",
                    "leakage_check_pass": True,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "feature_cols": ["usd_cny_return", "us10y_change", "supply_shock_score"],
                }
                trainer.return_value = {
                    "status": "success",
                    "candidate_version": "v6",
                    "metrics_by_horizon": {"1d": {"directional_accuracy": 0.56, "fold_count": 3}},
                    "oof_trace_paths": {"1d": str(output / "walk_forward" / "v6" / "oof_trace_1d.csv")},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                oof.return_value = {"status": "success", "candidate_version": "v6"}
                backtest.return_value = {"status": "success", "candidate_version": "v6"}
                validation.return_value = {"status": "success", "passed": False, "dry_run": True}
                promote.return_value = {"status": "failed", "passed": False, "dry_run": True, "active_updated": False}

                result = run_candidate_v6_gated_research(horizons=("1d",))

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["v6_admission"]["eligible"])
        self.assertEqual(result["candidate_v6_readiness"]["status"], "ready")
        self.assertTrue(result["feature_stability_evidence"]["passed"])
        self.assertIn("usd_cny_return", result["new_fields"])
        trainer.assert_called_once()
        self.assertEqual(trainer.call_args.kwargs["candidate_version"], "v6")
        self.assertEqual(trainer.call_args.kwargs["dataset_version"], "v6")
        self.assertTrue(promote.call_args.kwargs["dry_run"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())

    def test_blocks_when_training_dataset_v6_leakage_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _coverage_report(output, positive_delta=True)
            _real_data_validation_report(output, ready=True)
            _feature_stability_report(output, passed=True)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer:
                dataset.return_value = {
                    "status": "success",
                    "dataset_version": "v6",
                    "leakage_check_pass": False,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "feature_cols": ["usd_cny_return"],
                }
                result = run_candidate_v6_gated_research(horizons=("1d",))

        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("training_dataset_v6_leakage_failed", result["v6_admission"]["blocked_reasons"])
        self.assertEqual(result["candidate"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()

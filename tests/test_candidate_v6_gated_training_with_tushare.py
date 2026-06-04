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


def _coverage(groups: dict[str, float]) -> dict[str, object]:
    return {
        "sample_count": 120,
        "groups": [
            {"group": group, "coverage_rate": rate, "feature_count": 10, "available_feature_count": int(rate * 10)}
            for group, rate in groups.items()
        ],
        "usable_feature_cols": [],
    }


def _write_ready_v6_inputs(output: Path) -> None:
    feature_store = {
        "version": "v6",
        "status": "success",
        "generated_at": "2026-06-01T09:00:00",
        "row_count": 120,
        "usable_fields": ["open_interest", "settlement"],
        "tushare_used": True,
        "tushare_fields": ["open_interest", "settlement"],
        "leakage_check_pass": True,
        "no_lookahead_pass": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
    }
    feature_store_dir = output / "feature_store" / "v6"
    feature_store_dir.mkdir(parents=True, exist_ok=True)
    (feature_store_dir / "feature_store.csv").write_text("trade_date,close,open_interest,settlement\n2026-05-29,210000,12000,210100\n", encoding="utf-8")
    _write_json(feature_store_dir / "feature_store_manifest.json", feature_store)
    _write_json(
        output / "diagnostics" / "data_source_coverage_improvement.json",
        {
            "status": "success",
            "feature_coverage_delta": {
                "raw_market": {"before": 0.833333, "after": 1.0, "delta": 0.166667},
                "inventory": {"before": 0.0, "after": 0.0, "delta": 0.0},
            },
            "feature_store_v6": feature_store,
        },
    )
    _write_json(
        output / "diagnostics" / "real_data_coverage_validation.json",
        {
            "generated_at": "2026-06-01T09:00:00",
            "feature_coverage_before": _coverage({"raw_market": 0.833333}),
            "feature_coverage_after": _coverage({"raw_market": 1.0}),
            "feature_store_v5": feature_store,
            "feature_store_v6": feature_store,
        },
    )
    _write_json(
        output / "model_registry" / "feature_stability_report_v5.json",
        {
            "candidate_version": "v5",
            "evidence_status": "success",
            "stability_score": 0.72,
            "threshold": 0.55,
            "passed": True,
            "stable_features": ["open_interest", "settlement"],
            "unstable_features": [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class CandidateV6GatedTrainingWithTushareTest(unittest.TestCase):
    def test_ready_v6_uses_feature_store_v6_and_institutional_tushare_feature_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_ready_v6_inputs(output)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer, \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report") as oof, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest") as backtest, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation") as validation, \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate") as promote:
                dataset.return_value = {
                    "status": "success",
                    "dataset_version": "v6",
                    "feature_store_version": "v6",
                    "feature_set": "institutional_tushare_enhanced",
                    "leakage_check_pass": True,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "feature_cols": ["open_interest", "settlement"],
                }
                trainer.return_value = {
                    "status": "success",
                    "candidate_version": "v6",
                    "metrics_by_horizon": {"1d": {"directional_accuracy": 0.56, "fold_count": 3}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                oof.return_value = {"status": "success", "candidate_version": "v6"}
                backtest.return_value = {"status": "success", "candidate_version": "v6"}
                validation.return_value = {"status": "failed", "passed": False, "dry_run": True}
                promote.return_value = {"status": "failed", "passed": False, "dry_run": True, "active_updated": False}

                result = run_candidate_v6_gated_research(horizons=("1d",))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feature_store_version"], "v6")
        self.assertEqual(result["feature_set"], "institutional_tushare_enhanced")
        self.assertEqual(dataset.call_args.kwargs["feature_store_version"], "v6")
        self.assertEqual(dataset.call_args.kwargs["dataset_version"], "v6")
        self.assertEqual(dataset.call_args.kwargs["feature_set"], "institutional_tushare_enhanced")
        self.assertEqual(trainer.call_args.kwargs["candidate_version"], "v6")
        self.assertEqual(trainer.call_args.kwargs["dataset_version"], "v6")
        for expected_filter in ("stale_data", "roll_period", "low_liquidity", "high_turnover", "event_shock"):
            self.assertIn(expected_filter, trainer.call_args.kwargs["no_trade_filters"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_ready_readiness_overrides_stale_coverage_improvement_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_ready_v6_inputs(output)
            _write_json(
                output / "diagnostics" / "data_source_coverage_improvement.json",
                {
                    "status": "success",
                    "feature_coverage_delta": {
                        "raw_market": {"before": 1.0, "after": 1.0, "delta": 0.0},
                    },
                    "feature_store_v6": {
                        "version": "v6",
                        "status": "success",
                        "usable_fields": ["open_interest", "settlement"],
                        "leakage_check_pass": True,
                        "no_lookahead_pass": True,
                        "sample_data_used": False,
                        "mock_data_used": False,
                        "baseline_used": False,
                    },
                },
            )
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer, \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value={"status": "failed", "passed": False, "dry_run": True}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}):
                dataset.return_value = {
                    "status": "success",
                    "dataset_version": "v6",
                    "feature_store_version": "v6",
                    "feature_set": "institutional_tushare_enhanced",
                    "leakage_check_pass": True,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "feature_cols": ["open_interest", "settlement"],
                }
                trainer.return_value = {
                    "status": "success",
                    "candidate_version": "v6",
                    "metrics_by_horizon": {"1d": {"directional_accuracy": 0.56, "fold_count": 3}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }

                result = run_candidate_v6_gated_research(horizons=("1d",))

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["v6_admission"]["candidate_v6_readiness_ready"])
        self.assertNotIn("feature_coverage_delta_empty", result["v6_admission"]["blocked_reasons"])
        self.assertNotIn("new_real_factor_group_missing", result["v6_admission"]["blocked_reasons"])
        trainer.assert_called_once()


if __name__ == "__main__":
    unittest.main()

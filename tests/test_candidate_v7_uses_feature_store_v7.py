from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v7_research_service import run_candidate_v7_research


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _seed_ready_v7(out: Path) -> None:
    _write(
        out / "feature_store" / "v7" / "feature_store_manifest.json",
        {
            "version": "v7",
            "status": "success",
            "usable_fields": ["fee_rate", "cost_pressure_score", "member_position_available_flag", "member_position_event_score"],
            "cost_features": ["fee_rate", "cost_pressure_score"],
            "positioning_features": ["member_position_available_flag", "member_position_event_score"],
            "sparse_features": ["member_net_position"],
            "sample_data_used": False,
            "mock_data_used": False,
            "baseline_used": False,
            "no_lookahead_pass": True,
            "leakage_check_pass": True,
            "feature_store_path": str(out / "feature_store" / "v7" / "feature_store.csv"),
        },
    )
    _write(
        out / "training_dataset_manifest_v7.json",
        {
            "dataset_version": "v7",
            "feature_store_version": "v7",
            "status": "success",
            "feature_cols": ["fee_rate", "cost_pressure_score", "member_position_available_flag", "member_position_event_score"],
            "cost_features": ["fee_rate", "cost_pressure_score"],
            "positioning_features": ["member_position_available_flag", "member_position_event_score"],
            "sparse_features": ["member_net_position"],
            "leakage_check_pass": True,
            "no_lookahead_pass": True,
            "sample_data_used": False,
            "mock_data_used": False,
            "baseline_used": False,
        },
    )


class CandidateV7UsesFeatureStoreV7Test(unittest.TestCase):
    def test_candidate_v7_uses_v7_dataset_and_cost_positioning_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.candidate_v7_research_service.run_candidate_training"
        ) as train, patch("sn_futures.services.candidate_v7_research_service.get_oof_integrity_report") as integrity, patch(
            "sn_futures.services.candidate_v7_research_service.run_research_backtest"
        ) as backtest, patch("sn_futures.services.candidate_v7_research_service.run_institutional_validation") as validation, patch(
            "sn_futures.services.candidate_v7_research_service.promote_candidate"
        ) as promote:
            out = Path(tmp) / "outputs"
            _seed_ready_v7(out)
            train.return_value = {"status": "success", "metrics_by_horizon": {"1d": {"cost_adjusted_expectancy": 0.001}}, "registry_path": str(out / "model_registry" / "candidate_v7_model_registry.json")}
            integrity.return_value = {"status": "success"}
            backtest.return_value = {"status": "success", "horizons": {"1d": {"metrics": {"expectancy": 0.001}}}}
            validation.return_value = {"status": "success", "passed": False, "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.1}, "probability_of_backtest_overfitting": {"pbo": 0.4}}
            promote.return_value = {"status": "failed", "passed": False, "dry_run": True, "active_updated": False}

            result = run_candidate_v7_research(horizons=("1d",), build_missing=False)

        self.assertEqual(result["candidate_version"], "v7")
        self.assertEqual(result["dataset_version"], "v7")
        self.assertEqual(result["feature_store_version"], "v7")
        self.assertEqual(result["feature_set"], "tushare_cost_positioning_enhanced")
        self.assertIn("fee_rate", result["v7_feature_evidence"]["cost_features"])
        self.assertIn("member_position_event_score", result["v7_feature_evidence"]["positioning_features"])
        train.assert_called_once()
        kwargs = train.call_args.kwargs
        self.assertEqual(kwargs["candidate_version"], "v7")
        self.assertEqual(kwargs["dataset_version"], "v7")
        self.assertEqual(kwargs["feature_set"], "tushare_cost_positioning_enhanced")
        self.assertIn("high_cost_pressure", kwargs["no_trade_filters"])


if __name__ == "__main__":
    unittest.main()

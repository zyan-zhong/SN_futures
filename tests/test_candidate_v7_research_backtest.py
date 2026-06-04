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


class CandidateV7ResearchBacktestTest(unittest.TestCase):
    def test_candidate_v7_outputs_registry_validation_promotion_and_backtest_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.candidate_v7_research_service.run_candidate_training"
        ) as train, patch("sn_futures.services.candidate_v7_research_service.get_oof_integrity_report", return_value={"status": "success"}), patch(
            "sn_futures.services.candidate_v7_research_service.run_research_backtest"
        ) as backtest, patch("sn_futures.services.candidate_v7_research_service.run_institutional_validation") as validation, patch(
            "sn_futures.services.candidate_v7_research_service.promote_candidate"
        ) as promote:
            out = Path(tmp) / "outputs"
            _write(out / "feature_store" / "v7" / "feature_store_manifest.json", {"version": "v7", "status": "success", "usable_fields": ["fee_rate", "member_position_event_score"], "cost_features": ["fee_rate"], "positioning_features": ["member_position_event_score"], "leakage_check_pass": True, "no_lookahead_pass": True, "sample_data_used": False, "mock_data_used": False, "baseline_used": False})
            _write(out / "training_dataset_manifest_v7.json", {"dataset_version": "v7", "status": "success", "feature_cols": ["fee_rate", "member_position_event_score"], "leakage_check_pass": True, "no_lookahead_pass": True, "sample_data_used": False, "mock_data_used": False, "baseline_used": False})
            train.return_value = {"status": "success", "metrics_by_horizon": {"1d": {"cost_adjusted_expectancy": 0.001}}, "registry_path": str(out / "model_registry" / "candidate_v7_model_registry.json")}
            backtest.return_value = {"status": "success", "horizons": {"1d": {"metrics": {"expectancy": 0.001, "cost_stress": {"2x_cost": {"expectancy": -0.0001}, "3x_cost": {"expectancy": -0.0002}}}}}, "research_only": True}
            validation.return_value = {
                "status": "success",
                "passed": False,
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.2},
                "probability_of_backtest_overfitting": {"pbo": 0.3},
                "reality_check": {"p_value": 0.2},
            }
            promote.return_value = {"status": "failed", "passed": False, "dry_run": True, "active_updated": False}

            result = run_candidate_v7_research(horizons=("1d",), build_missing=False)
            self.assertTrue(Path(result["candidate_v7_registry_path"]).exists())
            self.assertTrue(Path(result["institutional_validation_path"]).exists())
            self.assertTrue(Path(result["promotion_dry_run_path"]).exists())

        self.assertEqual(result["status"], "success")
        self.assertIn("PBO", result["stability_objective"]["metrics"])
        self.assertIn("DSR", result["stability_objective"]["metrics"])
        self.assertIn("cost_stress", result["stability_objective"]["metrics"])
        self.assertEqual(result["research_backtest"]["status"], "success")
        self.assertFalse(result["manual_approval_recommended"])


if __name__ == "__main__":
    unittest.main()

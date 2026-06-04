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


class CandidateV7NoActiveWriteTest(unittest.TestCase):
    def test_promotion_dry_run_never_writes_active_or_customer_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.candidate_v7_research_service.run_candidate_training"
        ) as train, patch("sn_futures.services.candidate_v7_research_service.get_oof_integrity_report", return_value={"status": "success"}), patch(
            "sn_futures.services.candidate_v7_research_service.run_research_backtest", return_value={"status": "success", "horizons": {}}
        ), patch("sn_futures.services.candidate_v7_research_service.run_institutional_validation", return_value={"status": "success", "passed": False}), patch(
            "sn_futures.services.candidate_v7_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}
        ):
            out = Path(tmp) / "outputs"
            _write(out / "feature_store" / "v7" / "feature_store_manifest.json", {"version": "v7", "status": "success", "usable_fields": ["fee_rate", "member_position_event_score"], "cost_features": ["fee_rate"], "positioning_features": ["member_position_event_score"], "leakage_check_pass": True, "no_lookahead_pass": True, "sample_data_used": False, "mock_data_used": False, "baseline_used": False})
            _write(out / "training_dataset_manifest_v7.json", {"dataset_version": "v7", "status": "success", "feature_cols": ["fee_rate", "member_position_event_score"], "leakage_check_pass": True, "no_lookahead_pass": True, "sample_data_used": False, "mock_data_used": False, "baseline_used": False})
            train.return_value = {"status": "success", "metrics_by_horizon": {"1d": {}}, "registry_path": str(out / "model_registry" / "candidate_v7_model_registry.json")}

            result = run_candidate_v7_research(horizons=("1d",), build_missing=False)

            self.assertFalse((out / "model_registry" / "active_model.json").exists())
            self.assertFalse((out / "customer_predictions.json").exists())
            self.assertFalse((out / "sn_live_predictions.json").exists())

        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(result["baseline_used"])
        self.assertFalse(result["promotion_gate_lowered"])


if __name__ == "__main__":
    unittest.main()

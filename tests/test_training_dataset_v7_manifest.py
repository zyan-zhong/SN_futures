from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v7_service import build_feature_store_v7, build_training_dataset_v7


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _market_rows(days: int = 140) -> list[dict]:
    start = date(2025, 9, 1)
    return [
        {
            "trade_date": (start + timedelta(days=i)).isoformat(),
            "open": 230000 + i * 6,
            "high": 231000 + i * 6,
            "low": 229000 + i * 6,
            "close": 230500 + i * 6,
            "volume": 3000 + i,
        }
        for i in range(days)
    ]


class TrainingDatasetV7ManifestTest(unittest.TestCase):
    def test_training_dataset_v7_uses_cost_and_sparse_positioning_features_without_predictions_or_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            market = _market_rows()
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "sn_tushare_daily.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "open_interest": 60000 + i, "settlement": row["close"] + 5} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_tushare_settlement.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "settlement": row["close"] + 7, "trading_fee_rate": 0.00015, "trading_fee": 2.8, "long_margin_rate": 0.11, "short_margin_rate": 0.12, "offset_today_fee": 1.2} for row in market]})
            _write(out / "fundamentals" / "sn_tushare_holding.json", {"rows": [{"trade_date": market[i]["trade_date"], "contract": "SN2606", "long_position": 2000 + i, "short_position": 1500 + i, "long_change": 5, "short_change": -4} for i in range(0, len(market), 14)]})

            build_feature_store_v7()
            manifest = build_training_dataset_v7(horizons=(1, 3), min_feature_coverage=0.0)
            self.assertTrue(Path(manifest["manifest_path"]).exists())
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
            self.assertFalse((Path(tmp) / "outputs" / "customer_predictions.json").exists())

        self.assertEqual(manifest["dataset_version"], "v7")
        self.assertEqual(manifest["feature_store_version"], "v7")
        self.assertEqual(manifest["feature_set"], "institutional_tushare_cost_positioning")
        self.assertIn("fee_rate", manifest["feature_cols"])
        self.assertIn("margin_spread", manifest["feature_cols"])
        self.assertIn("member_position_available_flag", manifest["feature_cols"])
        self.assertIn("member_position_event_score", manifest["feature_cols"])
        self.assertIn("cost_features", manifest)
        self.assertIn("positioning_features", manifest)
        self.assertIn("sparse_feature_policy", manifest)
        self.assertTrue(manifest["leakage_check_pass"])
        self.assertTrue(manifest["no_lookahead_pass"])
        self.assertFalse(manifest["sample_data_used"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["baseline_used"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertTrue(manifest["dataset_paths"])


if __name__ == "__main__":
    unittest.main()

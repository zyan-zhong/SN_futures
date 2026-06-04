from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v5, build_training_dataset_v5


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class TrainingDatasetV5Test(unittest.TestCase):
    def test_training_dataset_v5_uses_feature_store_without_training_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            out = Path(tmp) / "outputs"
            start = date(2026, 1, 1)
            market = [{"trade_date": (start + timedelta(days=i)).isoformat(), "open": 250000 + i, "high": 251000 + i, "low": 249000 + i, "close": 250500 + i, "volume": 1000 + i} for i in range(90)]
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "managed_fundamentals.json", {"rows": [{"trade_date": row["trade_date"], "symbol": "SN", "spot_price": 251000 + i, "spot_futures_basis": 500 + i, "shfe_inventory": 8000 + i, "lme_tin_close": 33500 + i, "near_contract_close": 250000 + i, "far_contract_close": 249000 + i} for i, row in enumerate(market)]})
            build_feature_store_v5()

            manifest = build_training_dataset_v5(horizons=(1, 3), min_feature_coverage=0.5)

            self.assertEqual(manifest["dataset_version"], "v5")
            self.assertEqual(manifest["feature_store_version"], "v5")
            self.assertGreater(manifest["feature_count"], 0)
            self.assertIn("spot_futures_basis", manifest["feature_cols"])
            self.assertTrue(manifest["leakage_check_pass"])
            self.assertFalse(manifest["sample_data_used"])
            self.assertFalse(manifest["baseline_used"])
            self.assertFalse(manifest["customer_prediction_generated"])
            self.assertFalse((out / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()

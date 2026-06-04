from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v7_service import build_feature_store_v7


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _market_rows(count: int = 90) -> list[dict[str, object]]:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for i in range(count):
        close = 200000 + i * 10
        rows.append(
            {
                "trade_date": (start + timedelta(days=i)).isoformat(),
                "open": close - 50,
                "high": close + 100,
                "low": close - 100,
                "close": close,
                "volume": 1000 + i,
                "open_interest": 5000 + i,
            }
        )
    return rows


class InventoryMissingRiskFeatureTest(unittest.TestCase):
    def test_missing_warehouse_receipt_enters_risk_features_not_inventory_numeric_factor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            fundamentals = out / "fundamentals"
            _write_json(out / "sn_market_history.json", {"history": _market_rows()})
            _write_json(
                fundamentals / "tushare_provider_status.json",
                {"results": {"tushare_warehouse": {"status": "no_sn_rows", "attempted": True, "row_count": 0}}},
            )

            manifest = build_feature_store_v7()
            frame = pd.read_csv(manifest["feature_store_path"])

        self.assertEqual(manifest["status"], "success")
        self.assertIn("inventory_missing_flag", frame.columns)
        self.assertIn("warehouse_data_quality_score", frame.columns)
        self.assertTrue((frame["inventory_missing_flag"] == 1).all())
        self.assertTrue((frame["warehouse_data_quality_score"] == 0).all())
        self.assertIn("inventory_missing_flag", manifest["usable_fields"])
        self.assertIn("warehouse_data_quality_score", manifest["usable_fields"])
        self.assertEqual(manifest["field_sources"]["inventory_missing_flag"], "warehouse_missing_policy")
        self.assertEqual(manifest["warehouse_missing_policy"]["reason"], "tushare_fut_wsr_no_sn_rows")
        self.assertNotIn("fake_warehouse_receipt", frame.columns)
        self.assertNotIn("warehouse_receipt", manifest["usable_fields"])
        self.assertNotIn("warehouse_receipt_delta_1w", manifest["usable_fields"])
        self.assertEqual(manifest["customer_prediction_generated"], False)
        self.assertEqual(manifest["active_model_written"], False)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v10_service import build_feature_store_v10


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class FeatureStoreV10ManagedFundamentalsTest(unittest.TestCase):
    def test_v10_uses_real_managed_basis_inventory_warehouse_and_lme_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            try:
                out = Path(tmp) / "outputs"
                history = [
                    {
                        "trade_date": f"2026-03-{day:02d}",
                        "open": 250000 + day,
                        "high": 251000 + day,
                        "low": 249000 + day,
                        "close": 250500 + day,
                        "volume": 1000 + day,
                        "open_interest": 20000 + day,
                    }
                    for day in range(1, 29)
                ] + [
                    {
                        "trade_date": f"2026-04-{day:02d}",
                        "open": 250100 + day,
                        "high": 251100 + day,
                        "low": 249100 + day,
                        "close": 250600 + day,
                        "volume": 1100 + day,
                        "open_interest": 21000 + day,
                    }
                    for day in range(1, 29)
                ] + [
                    {
                        "trade_date": f"2026-05-{day:02d}",
                        "open": 250200 + day,
                        "high": 251200 + day,
                        "low": 249200 + day,
                        "close": 250700 + day,
                        "volume": 1200 + day,
                        "open_interest": 22000 + day,
                    }
                    for day in range(1, 29)
                ]
                _write(out / "sn_market_history.json", {"history": history})
                _write(
                    out / "fundamentals" / "managed_fundamentals.json",
                    {
                        "source": "managed_data_proxy",
                        "mock_data_used": False,
                        "sample_data_used": False,
                        "rows": [
                            {
                                "trade_date": row["trade_date"],
                                "symbol": "SN",
                                "spot_price": row["close"] + 800 + i,
                                "spot_premium": 1200 + i,
                                "spot_futures_basis": 800 + i,
                                "shfe_inventory": 8000 + i * 3,
                                "shfe_warehouse_receipt": 4100 + i * 2,
                                "lme_tin_close": 33500 + i * 5,
                                "lme_inventory": 4700 + i,
                                "near_contract": "SN2606",
                                "far_contract": "SN2607",
                                "near_contract_close": row["close"] - 100,
                                "far_contract_close": row["close"] - 600,
                                "near_open_interest": 42000 + i,
                                "far_open_interest": 36000 + i,
                                "main_contract": "SN2606",
                            }
                            for i, row in enumerate(history)
                        ],
                    },
                )
                manifest = build_feature_store_v10()
                self.assertTrue(Path(manifest["feature_store_path"]).exists())
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)

        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["version"], "v10")
        self.assertTrue(manifest["managed_fundamentals_used"])
        self.assertEqual(manifest["feature_store_v10_readiness"]["status"], "ready")
        usable = set(manifest["usable_fields"])
        for field in (
            "spot_futures_basis",
            "basis_zscore_60",
            "shfe_inventory_delta_1w",
            "shfe_warehouse_receipt",
            "lme_tin_return_1d",
            "lme_inventory_delta_1w",
            "near_far_spread",
        ):
            self.assertIn(field, usable)
        self.assertEqual(manifest["field_sources"]["spot_futures_basis"], "managed_proxy")
        self.assertEqual(manifest["field_sources"]["lme_tin_close"], "managed_proxy")
        self.assertTrue(manifest["no_lookahead_pass"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["sample_data_used"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertFalse(manifest["active_model_written"])


if __name__ == "__main__":
    unittest.main()

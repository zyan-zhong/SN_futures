from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v11_service import build_feature_store_v11


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class FeatureStoreV11ManagedProxyTest(unittest.TestCase):
    def test_v11_readiness_uses_existing_real_managed_fundamentals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            try:
                out = Path(tmp) / "outputs"
                history = [
                    {
                        "trade_date": f"2026-04-{day:02d}",
                        "open": 250000 + day,
                        "high": 251000 + day,
                        "low": 249000 + day,
                        "close": 250500 + day,
                        "volume": 1000 + day,
                        "open_interest": 20000 + day,
                    }
                    for day in range(1, 32)
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
                                "shfe_inventory": 8000 + i,
                                "shfe_warehouse_receipt": 4100 + i,
                                "lme_tin_close": 33500 + i,
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
                manifest = build_feature_store_v11()
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)

        self.assertEqual(manifest["version"], "v11")
        self.assertEqual(manifest["status"], "success")
        self.assertTrue(manifest["feature_store_v11_readiness"]["ready"])
        self.assertTrue(manifest["managed_fundamentals_used"])
        self.assertTrue(manifest["no_fake_data"])
        self.assertFalse(manifest["sample_data_used"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertIn("spot_futures_basis", manifest["managed_fundamental_fields"])
        self.assertIn("lme_tin_close", manifest["managed_fundamental_fields"])
        self.assertEqual(manifest["field_sources"]["spot_futures_basis"], "managed_proxy")


if __name__ == "__main__":
    unittest.main()

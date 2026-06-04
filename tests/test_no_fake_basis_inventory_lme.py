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


class NoFakeBasisInventoryLmeTest(unittest.TestCase):
    def test_no_managed_proxy_keeps_fundamental_fields_missing_not_faked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
            os.environ.pop("SN_MANAGED_DATA_PROXY_URL", None)
            os.environ.pop("SN_MANAGED_DATA_PROXY_ENABLED", None)
            try:
                out = Path(tmp) / "outputs"
                _write(
                    out / "sn_market_history.json",
                    {
                        "history": [
                            {"trade_date": f"2026-05-{day:02d}", "open": 250000 + day, "high": 251000 + day, "low": 249000 + day, "close": 250500 + day, "volume": 1000 + day}
                            for day in range(1, 31)
                        ]
                    },
                )
                _write(
                    out / "fundamentals" / "tushare_provider_status.json",
                    {
                        "results": {
                            "tushare_warehouse": {
                                "status": "no_sn_rows",
                                "row_count": 0,
                                "message_zh": "fut_wsr returned no real SN rows",
                            }
                        }
                    },
                )
                manifest = build_feature_store_v10()
                store = (out / "feature_store" / "v10" / "feature_store.csv").read_text(encoding="utf-8")
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)

        self.assertEqual(manifest["version"], "v10")
        self.assertFalse(manifest["managed_fundamentals_used"])
        self.assertEqual(manifest["managed_proxy_status"]["status"], "disabled")
        self.assertEqual(manifest["fut_wsr_status"], "no_sn_rows")
        self.assertEqual(manifest["feature_store_v10_readiness"]["status"], "blocked")
        self.assertEqual(manifest["managed_fundamental_fields"], [])
        self.assertTrue(all(not ready for ready in manifest["feature_store_v10_readiness"]["group_ready"].values()))
        self.assertTrue(manifest["no_fake_data"])
        self.assertIn("inventory_missing_flag", manifest["usable_fields"])
        self.assertNotIn("fake_warehouse_receipt", store)
        self.assertNotIn("fake_basis", store)
        self.assertNotIn("fake_lme", store)
        for field in ("shfe_warehouse_receipt", "spot_futures_basis", "lme_tin_close"):
            self.assertIn(field, manifest["missing_managed_fields"])
            self.assertNotIn(field, manifest["usable_fields"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertFalse(manifest["active_model_written"])


if __name__ == "__main__":
    unittest.main()

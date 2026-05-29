from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.cross_market_feature_join_service import build_cross_market_feature_frame


class CrossMarketTemporalAlignmentTest(unittest.TestCase):
    def test_forward_fill_to_market_dates_is_limited_to_five_trading_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            fundamentals = output / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            (fundamentals / "sn_cross_market.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {"trade_date": "2025-01-03", "usd_cny": 7.1, "us10y": 4.0, "copper_global_proxy": 9000.0}
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            market = pd.DataFrame(index=pd.bdate_range("2025-01-06", periods=8))

            aligned, diagnostics = build_cross_market_feature_frame(market)

            self.assertEqual(float(aligned.iloc[0]["usd_cny"]), 7.1)
            self.assertTrue(pd.isna(aligned.iloc[-1]["usd_cny"]))
            self.assertGreater(diagnostics["stale_row_count"], 0)
            self.assertEqual(diagnostics["max_forward_fill_trading_days"], 5)
            self.assertIn("usd_cny", diagnostics["fields"])


if __name__ == "__main__":
    unittest.main()

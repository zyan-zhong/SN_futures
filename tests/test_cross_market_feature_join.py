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


class CrossMarketFeatureJoinTest(unittest.TestCase):
    def test_cross_market_join_keeps_copper_proxy_separate_from_lme_tin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            rows = []
            for idx, day in enumerate(pd.bdate_range("2025-01-01", periods=10)):
                rows.append(
                    {
                        "trade_date": day.strftime("%Y-%m-%d"),
                        "usd_cny": 7.0 + idx * 0.01,
                        "us10y": 4.0 + idx * 0.02,
                        "copper_global_proxy": 9000.0 + idx * 10,
                    }
                )
            (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")
            market = pd.DataFrame(index=pd.bdate_range("2025-01-01", periods=10))

            aligned, diagnostics = build_cross_market_feature_frame(market)

            self.assertIn("usd_cny_return", aligned.columns)
            self.assertIn("us10y_change", aligned.columns)
            self.assertIn("copper_global_proxy_return", aligned.columns)
            self.assertIn("copper_proxy_return", aligned.columns)
            self.assertNotIn("lme_tin_close", aligned.columns)
            self.assertEqual(diagnostics["lme_tin_close_status"], "unavailable")
            self.assertGreater(diagnostics["field_diagnostics"]["copper_global_proxy_return"]["non_null_rate"], 0.7)


if __name__ == "__main__":
    unittest.main()

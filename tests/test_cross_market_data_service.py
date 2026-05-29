from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.cross_market_data_service import build_cross_market_rows


class CrossMarketDataServiceTest(unittest.TestCase):
    def test_missing_lme_tin_makes_cross_market_unavailable(self) -> None:
        result = build_cross_market_rows([], [{"trade_date": "2026-01-02", "usd_cny": 7.1}], [])
        self.assertFalse(result["success"])
        self.assertIn("LME", result["message_zh"])

    def test_lme_and_fx_generate_cross_market_rows(self) -> None:
        lme = [
            {"trade_date": "2026-01-01", "lme_tin_close": 30000},
            {"trade_date": "2026-01-02", "lme_tin_close": 30300},
        ]
        fx = [
            {"trade_date": "2026-01-01", "usd_cny": 7.0},
            {"trade_date": "2026-01-02", "usd_cny": 7.1},
        ]
        result = build_cross_market_rows(lme, fx, [], [{"trade_date": "2026-01-02", "close": 215000}])
        self.assertTrue(result["success"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertIn("lme_tin_return_1d", result["rows"][1])
        self.assertIn("lme_shfe_spread", result["rows"][1])


if __name__ == "__main__":
    unittest.main()


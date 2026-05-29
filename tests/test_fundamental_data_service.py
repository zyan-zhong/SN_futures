from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.fundamental_data_service import build_inventory_rows, build_spot_basis_rows


class FundamentalDataServiceTest(unittest.TestCase):
    def test_missing_spot_data_makes_basis_unavailable(self) -> None:
        result = build_spot_basis_rows([], [{"trade_date": "2026-01-02", "close": 210000}])
        self.assertFalse(result["success"])
        self.assertIn("现货", result["message_zh"])

    def test_real_inventory_rows_are_usable(self) -> None:
        shfe = [{"trade_date": f"2026-01-{day:02d}", "shfe_inventory": 1000 + day} for day in range(1, 12)]
        lme = [{"trade_date": f"2026-01-{day:02d}", "lme_inventory": 2000 + day} for day in range(1, 12)]
        result = build_inventory_rows(shfe, lme, [])
        self.assertTrue(result["success"])
        self.assertEqual(len(result["rows"]), 11)
        self.assertIn("global_visible_inventory", result["rows"][-1])
        self.assertIn("inventory_delta_1w", result["rows"][-1])


if __name__ == "__main__":
    unittest.main()


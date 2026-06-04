from __future__ import annotations

import unittest
import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import normalize_managed_fundamental_rows


class ManagedProxySchemaTest(unittest.TestCase):
    def test_standard_schema_keeps_structured_sn_fundamentals(self) -> None:
        rows = normalize_managed_fundamental_rows(
            [
                {
                    "trade_date": "2026-05-20",
                    "symbol": "SN",
                    "spot_price": "270000",
                    "spot_premium": "1200",
                    "spot_futures_basis": "800",
                    "shfe_inventory": "8000",
                    "shfe_warehouse_receipt": "4100",
                    "lme_tin_close": "33500",
                    "lme_inventory": "4700",
                    "near_contract": "SN2606",
                    "far_contract": "SN2607",
                    "near_contract_close": "269200",
                    "far_contract_close": "268600",
                    "near_open_interest": "42000",
                    "far_open_interest": "36000",
                    "main_contract": "SN2606",
                    "main_contract_switch_flag": 0,
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["trade_date"], "2026-05-20")
        self.assertEqual(row["near_contract"], "SN2606")
        self.assertAlmostEqual(row["spot_price"], 270000.0)
        self.assertAlmostEqual(row["lme_tin_close"], 33500.0)
        self.assertFalse(row["from_cache"])
        self.assertEqual(row["source"], "managed_data_proxy")

    def test_non_sn_rows_are_rejected_not_relabelled(self) -> None:
        rows = normalize_managed_fundamental_rows(
            [
                {
                    "trade_date": "2026-05-20",
                    "symbol": "CU",
                    "spot_price": 70000,
                    "near_contract": "CU2606",
                }
            ]
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()

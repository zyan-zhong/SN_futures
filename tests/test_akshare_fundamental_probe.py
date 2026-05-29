from __future__ import annotations

import sys
import unittest

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.shfe_public_data_service import probe_akshare_futures_fundamental_functions


class EmptyAkShare:
    pass


class NoTinAkShare:
    def futures_inventory_99(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "CU", "date": "2026-01-02", "inventory": 1000}])


class AkShareFundamentalProbeTest(unittest.TestCase):
    def test_missing_functions_are_function_unavailable(self) -> None:
        result = probe_akshare_futures_fundamental_functions(ak_module=EmptyAkShare())
        statuses = {row["function_name"]: row["status"] for row in result["functions"]}

        self.assertEqual(statuses["futures_inventory_99"], "function_unavailable")
        self.assertFalse(result["success"])

    def test_no_tin_rows_are_reported(self) -> None:
        result = probe_akshare_futures_fundamental_functions(ak_module=NoTinAkShare())
        row = next(item for item in result["functions"] if item["function_name"] == "futures_inventory_99")

        self.assertEqual(row["status"], "no_tin_rows")
        self.assertEqual(row["tin_row_count"], 0)


if __name__ == "__main__":
    unittest.main()

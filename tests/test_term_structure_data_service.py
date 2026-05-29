from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.term_structure_data_service import normalize_contract_curve_rows


class TermStructureDataServiceTest(unittest.TestCase):
    def test_does_not_use_single_sn0_as_near_and_far(self) -> None:
        result = normalize_contract_curve_rows(
            [
                {"trade_date": "2026-01-02", "contract": "SN0", "close": 210000, "volume": 1000},
            ]
        )
        self.assertFalse(result["success"])
        self.assertIn("SN0", result["message_zh"])

    def test_real_multi_contract_rows_generate_near_far_fields(self) -> None:
        result = normalize_contract_curve_rows(
            [
                {"trade_date": "2026-01-02", "contract": "SN2601", "close": 210000, "volume": 1000, "open_interest": 3000},
                {"trade_date": "2026-01-02", "contract": "SN2605", "close": 212000, "volume": 800, "open_interest": 2500},
            ]
        )
        self.assertTrue(result["success"])
        row = result["rows"][0]
        self.assertEqual(row["near_contract"], "SN2601")
        self.assertEqual(row["far_contract"], "SN2605")
        self.assertIn("term_structure_slope", row)


if __name__ == "__main__":
    unittest.main()


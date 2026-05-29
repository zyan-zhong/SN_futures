from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.diagnostics.neutral_rate_audit import audit_neutral_rates


class NeutralRateAuditTest(unittest.TestCase):
    def test_extreme_neutral_rate_is_flagged_without_recommending_threshold_hack(self) -> None:
        audit = audit_neutral_rates({"next_5m": {"p_neutral": 0.95}})
        row = next(item for item in audit["rows"] if item["horizon"] == "next_5m")
        self.assertEqual(row["severity"], "red")
        self.assertIn("禁止只靠降阈值", row["reason"])

    def test_probabilities_can_be_derived_from_up_down(self) -> None:
        audit = audit_neutral_rates({"next_15m": {"prob_up": 0.42, "prob_down": 0.36}})
        row = next(item for item in audit["rows"] if item["horizon"] == "next_15m")
        self.assertAlmostEqual(row["p_neutral"], 0.22)


if __name__ == "__main__":
    unittest.main()

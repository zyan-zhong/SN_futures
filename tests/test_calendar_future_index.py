from __future__ import annotations

import sys
import unittest

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.chart_alignment import generate_future_trading_index
from sn_futures.trading_calendar import sn_trading_session_state


class CalendarFutureIndexTest(unittest.TestCase):
    def test_friday_night_session_does_not_jump_to_monday(self) -> None:
        state = sn_trading_session_state("2026-05-15T22:15:00+08:00")
        self.assertTrue(state["is_trading"])
        self.assertTrue(state["is_night"])
        idx = generate_future_trading_index("2026-05-15T22:15:00+08:00", "h5m")
        self.assertTrue(idx[0].startswith("2026-05-15T22:20"))

    def test_lunch_break_starts_next_valid_session(self) -> None:
        state = sn_trading_session_state("2026-05-14T12:00:00+08:00")
        self.assertFalse(state["is_trading"])
        self.assertIn("13:30:00", state["next_session_start"])

    def test_horizon_intervals_are_different(self) -> None:
        last = "2026-05-14T18:00:00+08:00"
        five = [pd.Timestamp(x) for x in generate_future_trading_index(last, "h5m")[:2]]
        fifteen = [pd.Timestamp(x) for x in generate_future_trading_index(last, "h15m")[:2]]
        self.assertEqual((five[1] - five[0]).total_seconds(), 300)
        self.assertEqual((fifteen[1] - fifteen[0]).total_seconds(), 900)


if __name__ == "__main__":
    unittest.main()

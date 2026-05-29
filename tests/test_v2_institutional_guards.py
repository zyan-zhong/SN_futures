import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.chart_alignment import build_forecast_curve, validate_chart_alignment
from sn_futures.data_quality import build_data_quality_report
from sn_futures.horizon_registry import get_horizon_config


class InstitutionalGuardTests(unittest.TestCase):
    def test_future_forecast_is_after_history(self):
        history = [{"date": "2026-05-14T21:00:00+08:00", "close": 421420.0}]
        card = {
            "anchor_close": 421420.0,
            "price_center": 422000.0,
            "range_low": 418000.0,
            "range_high": 426000.0,
            "prob_up": 0.56,
        }
        forecast = build_forecast_curve(live_card=card, last_timestamp=history[-1]["date"], horizon_key="next_15m")
        alignment = validate_chart_alignment(history, forecast)
        self.assertTrue(alignment["ok"], alignment)
        self.assertGreater(len(forecast), 0)
        self.assertIsNone(forecast[0]["close"])

    def test_horizon_steps_are_not_copied(self):
        self.assertEqual(get_horizon_config("next_5m").forecast_steps, 12)
        self.assertEqual(get_horizon_config("next_15m").forecast_steps, 16)
        self.assertEqual(get_horizon_config("next_30m").forecast_steps, 16)
        self.assertEqual(get_horizon_config("next_hour").forecast_steps, 12)
        self.assertEqual(get_horizon_config("one_to_two_weeks").forecast_steps, 10)
        self.assertEqual(get_horizon_config("one_to_three_months").forecast_steps, 60)

    def test_data_quality_detects_ohlc_and_negative_volume(self):
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2026-05-01", periods=3, freq="D"),
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 100.0, 103.0],
                "low": [99.0, 102.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [10.0, -1.0, 12.0],
                "open_interest": [100.0, 101.0, 102.0],
            }
        )
        report = build_data_quality_report(frame, timestamp_col="date", max_stale_hours=10_000)
        self.assertGreater(report.ohlc_error_count, 0)
        self.assertGreater(report.volume_anomaly_flags, 0)
        self.assertLess(report.quality_score, 1.0)


if __name__ == "__main__":
    unittest.main()

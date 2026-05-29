import unittest
import sys

sys.path.insert(0, "src")

from sn_futures.chart_alignment import build_forecast_curve
from sn_futures.diagnostics.forecast_path_audit import audit_single_forecast_path


class ForecastPathContinuityTest(unittest.TestCase):
    def test_forecast_path_is_continuous_and_not_flat(self):
        history = [
            {"date": "2026-05-14T14:55:00+08:00", "close": 420000 + idx * 20}
            for idx in range(8)
        ]
        last_price = history[-1]["close"]
        forecast = build_forecast_curve(
            live_card={
                "anchor_close": last_price,
                "price_center": last_price * 1.006,
                "range_low": last_price * 0.998,
                "range_high": last_price * 1.012,
                "prob_up": 0.61,
                "p_neutral": 0.12,
                "volatility": 0.004,
            },
            last_timestamp=history[-1]["date"],
            horizon_key="next_15m",
        )
        audit = audit_single_forecast_path({"horizon": "next_15m", "history_series": history, "forecast_series": forecast})
        centers = [round(row["pred_center"], 4) for row in forecast]
        self.assertTrue(audit["ok"], audit)
        self.assertGreater(len(set(centers)), 4)
        self.assertGreater(forecast[0]["date"], history[-1]["date"])
        for row in forecast:
            self.assertLessEqual(row["pred_low"], row["pred_center"])
            self.assertLessEqual(row["pred_center"], row["pred_high"])

    def test_extreme_first_jump_is_repaired(self):
        history = [
            {"date": "2026-05-14T14:55:00+08:00", "close": 420000 + idx * 10}
            for idx in range(8)
        ]
        last_price = history[-1]["close"]
        forecast = build_forecast_curve(
            live_card={
                "anchor_close": last_price,
                "price_center": last_price * 1.18,
                "range_low": last_price * 1.05,
                "range_high": last_price * 1.30,
                "prob_up": 0.58,
                "p_neutral": 0.10,
                "volatility": 0.002,
            },
            last_timestamp=history[-1]["date"],
            horizon_key="tomorrow",
        )
        self.assertEqual(forecast[0]["path_sanity_status"], "repaired")
        self.assertIn("first_step_jump_repaired", forecast[0]["path_repair_reasons"])
        self.assertLess(
            abs(forecast[0]["pred_center"] - last_price),
            abs(last_price * 1.18 - last_price),
        )
        audit = audit_single_forecast_path({"horizon": "tomorrow", "history_series": history, "forecast_series": forecast})
        self.assertTrue(audit["ok"], audit)


if __name__ == "__main__":
    unittest.main()

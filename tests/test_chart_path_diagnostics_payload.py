from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.v2_api import get_price_forecast_chart


class ChartPathDiagnosticsPayloadTest(unittest.TestCase):
    def test_chart_payload_contains_v37_path_diagnostics(self) -> None:
        payload = get_price_forecast_chart("tomorrow")
        self.assertIn("path_diagnostics", payload)
        self.assertIn("interval_policy", payload)
        self.assertIn("interval_growth_warning", payload)
        self.assertIn("event_shock_markers", payload)
        diagnostics = payload["path_diagnostics"]
        for key in [
            "first_step_gap",
            "interval_growth_rate",
            "center_flatline_rate",
            "direction_price_conflict",
            "price_band_reason",
        ]:
            self.assertIn(key, diagnostics)
        self.assertIsInstance(payload["event_shock_markers"], list)

    def test_short_and_long_horizons_have_different_growth_policies(self) -> None:
        short_payload = get_price_forecast_chart("next_5m")
        long_payload = get_price_forecast_chart("one_to_three_months")
        short_diag = short_payload["path_diagnostics"]
        long_diag = long_payload["path_diagnostics"]
        self.assertNotEqual(
            short_diag.get("max_interval_growth_allowed"),
            long_diag.get("max_interval_growth_allowed"),
        )


if __name__ == "__main__":
    unittest.main()

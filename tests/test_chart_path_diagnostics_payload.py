from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

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

    def test_live_quote_is_returned_as_display_overlay_not_history_bar(self) -> None:
        history = [{"ts": "2026-01-01", "close": 100.0, "source": "history"}]
        live_payload = {
            "cards": {"tomorrow": {"prediction_id": "p-1", "model_version": "m-1"}},
            "live_quote": {"symbol": "SN0", "latest": 120.0, "quote_time": "2026-01-02T10:00:00+08:00"},
        }
        with (
            patch("sn_futures.v2_api.get_live_predictions", return_value=live_payload),
            patch("sn_futures.v2_api._history_from_outputs", return_value=list(history)),
            patch("sn_futures.v2_api._forecast_points", return_value=[]),
            patch("sn_futures.v2_api.get_events_evidence", return_value={"events": []}),
        ):
            payload = get_price_forecast_chart("tomorrow")

        self.assertEqual(payload["history"], history)
        self.assertEqual(payload["latest_quote"], live_payload["live_quote"])
        self.assertEqual(
            payload["display_overlay"],
            {
                "type": "latest_quote_marker",
                "price": 120.0,
                "quote_time": "2026-01-02T10:00:00+08:00",
                "symbol": "SN0",
                "source": "live_quote",
            },
        )
        self.assertTrue(payload["manifest"]["history_immutable"])
        self.assertTrue(payload["manifest"]["live_overlay_used_for_display_only"])
        self.assertFalse(payload["manifest"]["live_overlay_used_for_training"])
        self.assertFalse(payload["manifest"]["live_overlay_used_for_backtest"])


if __name__ == "__main__":
    unittest.main()

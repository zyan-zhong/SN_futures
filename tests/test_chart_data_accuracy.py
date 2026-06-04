from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")


class ChartDataAccuracyTest(unittest.TestCase):
    def test_price_payload_keeps_dates_prices_and_downsamples_without_mixing_returns(self) -> None:
        from sn_futures.services.chart_payload_service import build_price_chart_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            output.mkdir(parents=True, exist_ok=True)
            rows = []
            for index in range(1200):
                rows.append(
                    {
                        "time": f"2024-01-{(index % 28) + 1:02d}",
                        "open": 200000 + index,
                        "high": 200010 + index,
                        "low": 199990 + index,
                        "close": 200005 + index,
                        "return_1d": 0.99,
                    }
                )
            (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")
            payload = build_price_chart_payload(max_points=500)

        self.assertLessEqual(len(payload["points"]), 500)
        self.assertEqual(payload["points"][0]["time"], rows[0]["time"])
        self.assertEqual(payload["points"][-1]["time"], rows[-1]["time"])
        self.assertNotIn("return_1d", payload["points"][0])
        self.assertTrue(all(point["close"] > 100000 for point in payload["points"]))
        self.assertEqual(payload["downsampled"], True)
        self.assertEqual(payload["downsample_method"], "stride_keep_ends")

    def test_drawdown_payload_clamps_positive_values_to_zero(self) -> None:
        from sn_futures.services.chart_payload_service import build_drawdown_curve_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            folder = Path(tmp) / "outputs" / "research_backtests" / "v5"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "drawdown_curve_1d.csv").write_text("ts,value\n2026-01-01,0.02\n2026-01-02,-0.05\n", encoding="utf-8")
            payload = build_drawdown_curve_payload(version="v5", horizon="1d")

        self.assertEqual(payload["chart_type"], "drawdown_curve")
        self.assertTrue(all(point["value"] <= 0 for point in payload["points"]))
        self.assertEqual(payload["units"]["drawdown"], "percent")


if __name__ == "__main__":
    unittest.main()

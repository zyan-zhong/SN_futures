from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.oof_trace_service import get_oof_trace_summary, write_oof_trace


class OOFTraceDiagnosticsTest(unittest.TestCase):
    def test_oof_trace_summary_builds_confidence_and_calibration_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            rows = []
            for idx in range(40):
                rows.append(
                    {
                        "horizon": "1d",
                        "fold_id": "1",
                        "label_start_time": f"2024-01-{idx % 28 + 1:02d}",
                        "label_end_time": f"2024-01-{idx % 28 + 2:02d}",
                        "realized_direction": 1 if idx % 2 else -1,
                        "realized_return": 0.01 if idx % 2 else -0.01,
                        "raw_prob_up": 0.7 if idx % 2 else 0.3,
                        "calibrated_prob_up": 0.7 if idx % 2 else 0.3,
                        "predicted_direction": 1 if idx % 3 else -1,
                        "expected_return": 0.004,
                        "confidence": 0.4 + idx / 100,
                        "cost_assumption": 0.0002,
                        "regime_label": "HIGH_VOL" if idx < 20 else "LOW_VOL",
                        "error_type": "high_confidence_wrong" if idx == 39 else "",
                        "drawdown_contribution": -0.02 if idx == 5 else 0.0,
                    }
                )
            write_oof_trace(rows, horizon="1d")
            summary = get_oof_trace_summary("1d")

            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["row_count"], 40)
            self.assertTrue(summary["calibration_bins"])
            self.assertTrue(summary["confidence_deciles"])
            self.assertIn("top_10pct", summary)
            self.assertTrue(summary["regime_error_hotspots"])
            self.assertTrue(summary["drawdown_contribution_samples"])
            self.assertFalse(summary["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()

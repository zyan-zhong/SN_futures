from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.sample_boundary_service import build_sample_data_boundary_report
from sn_futures.services.sample_data_service import sample_predictions


class SampleDataBoundaryTest(unittest.TestCase):
    def test_sample_predictions_are_observe_only_without_trade_points(self) -> None:
        cards = sample_predictions()
        self.assertTrue(cards)
        for card in cards:
            self.assertTrue(card["sample_mode"])
            self.assertEqual(card["signal"], "观望")
            self.assertIsNone(card["entry"])
            self.assertIsNone(card["stop_loss"])
            self.assertIsNone(card["take_profit"])

    def test_real_market_history_forces_sample_mode_off_for_research_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            output.mkdir(parents=True, exist_ok=True)
            (output / "sn_market_history.json").write_text(json.dumps({"history": [{"time": "2026-01-01", "close": 1}]}), encoding="utf-8")
            report = build_sample_data_boundary_report()

        self.assertTrue(report["real_data_available"])
        self.assertFalse(report["sample_mode"])
        self.assertFalse(report["training_sample_data_used"])
        self.assertFalse(report["candidate_sample_data_used"])
        self.assertFalse(report["backtest_sample_data_used"])
        self.assertFalse(report["active_sample_data_used"])


if __name__ == "__main__":
    unittest.main()

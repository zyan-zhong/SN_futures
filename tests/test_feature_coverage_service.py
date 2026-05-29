from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_coverage_service import build_feature_coverage_report


def _write_history(root: str, rows: int = 160) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    history = []
    for idx, day in enumerate(dates):
        close = 200000.0 + idx * 120.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 300,
                "high": close + 800,
                "low": close - 900,
                "close": close,
                "volume": 10000 + idx,
                "open_interest": None,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class FeatureCoverageServiceTest(unittest.TestCase):
    def test_ohlcv_history_generates_technical_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=180)
            report = build_feature_coverage_report()
        self.assertEqual(report["sample_count"], 180)
        technical = next(group for group in report["groups"] if group["group"] == "technical")
        self.assertGreaterEqual(technical["available_feature_count"], 12)
        self.assertTrue(report["training_readiness"]["can_train_ohlcv_model"])

    def test_missing_fundamental_fields_are_not_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=180)
            report = build_feature_coverage_report()
        by_group = {group["group"]: group for group in report["groups"]}
        self.assertEqual(by_group["basis"]["available_feature_count"], 0)
        self.assertEqual(by_group["inventory"]["available_feature_count"], 0)
        self.assertEqual(by_group["cross_market"]["available_feature_count"], 0)
        self.assertIn("spot_price", report["blocking_missing_fields"])
        self.assertIn("shfe_inventory", report["blocking_missing_fields"])
        self.assertIn("lme_tin_close", report["blocking_missing_fields"])

    def test_missing_events_degrade_event_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=180)
            report = build_feature_coverage_report()
        event = next(group for group in report["groups"] if group["group"] == "event")
        self.assertEqual(event["available_feature_count"], 0)
        self.assertGreater(event["missing_feature_count"], 0)

    def test_usable_features_exclude_label_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=180)
            report = build_feature_coverage_report()
        forbidden_prefixes = ("ret_", "direction_", "tb_", "meta_")
        self.assertTrue(report["usable_feature_cols"])
        for column in report["usable_feature_cols"]:
            self.assertFalse(column.startswith(forbidden_prefixes), column)


if __name__ == "__main__":
    unittest.main()

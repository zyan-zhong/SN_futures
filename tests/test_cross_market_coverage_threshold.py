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
from sn_futures.services.training_dataset_service import build_training_dataset


def _write_history(root: str, start: str = "2025-01-01", rows: int = 120) -> Path:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.bdate_range(start, periods=rows)):
        close = 220000.0 + idx * 55
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 300,
                "low": close - 280,
                "close": close,
                "volume": 9000 + idx,
                "open_interest": 100000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")
    return output


def _write_cross_market(output: Path, start: str, rows: int = 120) -> None:
    fundamentals = output / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    payload_rows = []
    for idx, day in enumerate(pd.bdate_range(start, periods=rows)):
        payload_rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "usd_cny": 7.0 + idx * 0.001,
                "us10y": 4.0 + idx * 0.002,
                "copper_global_proxy": 9000.0 + idx,
            }
        )
    (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": payload_rows}, ensure_ascii=False), encoding="utf-8")


class CrossMarketCoverageThresholdTest(unittest.TestCase):
    def test_non_overlapping_cross_market_file_does_not_raise_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_history(tmp, start="2025-01-01")
            _write_cross_market(output, start="2020-01-01")

            report = build_feature_coverage_report(report_version="v2")
            group = next(row for row in report["groups"] if row["group"] == "cross_market")

            self.assertEqual(group["coverage_rate"], 0.0)
            self.assertIn("no_date_overlap", report["cross_market_diagnostics"]["blocking_reasons"])

    def test_overlapping_cross_market_file_enters_coverage_and_v2_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_history(tmp, start="2025-01-01")
            _write_cross_market(output, start="2025-01-01")

            report = build_feature_coverage_report(report_version="v2")
            manifest = build_training_dataset(
                dataset_version="v2",
                feature_set="ohlcv_technical_regime_cross_market_event",
                min_feature_coverage=0.7,
            )
            group = next(row for row in report["groups"] if row["group"] == "cross_market")

            self.assertGreater(group["coverage_rate"], 0.0)
            self.assertIn("usd_cny_return", report["usable_feature_cols"])
            self.assertIn("us10y_change", report["usable_feature_cols"])
            self.assertIn("copper_global_proxy_return", report["usable_feature_cols"])
            self.assertIn("usd_cny_return", manifest["cross_market_feature_cols"])
            self.assertIn("us10y_change", manifest["cross_market_feature_cols"])
            self.assertIn("copper_global_proxy_return", manifest["cross_market_feature_cols"])
            self.assertNotIn("lme_tin_close", manifest["feature_cols"])
            self.assertFalse((Path(tmp) / "outputs" / "sn_live_predictions.json").exists())
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()

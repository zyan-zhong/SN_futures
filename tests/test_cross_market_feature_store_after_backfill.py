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
from sn_futures.services.feature_store_service import build_feature_store


def _write_market(root: str) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.bdate_range("2026-01-01", periods=90)):
        close = 220000 + idx * 100
        rows.append({"time": day.strftime("%Y-%m-%d"), "open": close - 20, "high": close + 100, "low": close - 100, "close": close, "volume": 1000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}), encoding="utf-8")


def _write_cross_market_cache(root: str) -> None:
    fundamentals = Path(root) / "outputs" / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.bdate_range("2026-01-01", periods=90)):
        rows.append({"trade_date": day.strftime("%Y-%m-%d"), "usd_cny": 7.0 + idx * 0.001, "us10y": 4.0 + idx * 0.002, "copper_global_proxy": 9000 + idx})
    payload = {"rows": rows, "from_cache": True, "status": "using_cache_rate_limited"}
    (fundamentals / "sn_cross_market.json").write_text(json.dumps(payload), encoding="utf-8")
    (fundamentals / "last_good_cross_market.json").write_text(json.dumps(payload), encoding="utf-8")
    (fundamentals / "fx_macro_provider_status.json").write_text(json.dumps({"status": "using_cache_rate_limited", "from_cache": True, "row_count": len(rows)}), encoding="utf-8")


class CrossMarketFeatureStoreAfterBackfillTest(unittest.TestCase):
    def test_coverage_and_feature_store_use_last_good_cross_market_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            _write_cross_market_cache(tmp)

            coverage = build_feature_coverage_report(report_version="v2")
            store = build_feature_store(version="v3")

        self.assertIn("usd_cny_return", coverage["usable_feature_cols"])
        self.assertIn("us10y_change", coverage["usable_feature_cols"])
        self.assertIn("copper_global_proxy_return", coverage["usable_feature_cols"])
        self.assertIn("usd_cny_return", store["usable_fields"])
        self.assertIn("us10y_change", store["usable_fields"])
        self.assertFalse((Path(tmp) / "outputs" / "sn_live_predictions.json").exists())
        self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()

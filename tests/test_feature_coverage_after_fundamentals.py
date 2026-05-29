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


def _write_history(root: str, rows: int = 180) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-01-01", periods=rows, freq="D")
    history = []
    for idx, day in enumerate(dates):
        close = 210000 + idx * 50
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 500,
                "low": close - 500,
                "close": close,
                "volume": 10000 + idx,
                "open_interest": 20000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class FeatureCoverageAfterFundamentalsTest(unittest.TestCase):
    def test_fundamental_files_raise_factor_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            dates = pd.date_range("2026-01-01", periods=180, freq="D")
            term_rows = [
                {
                    "trade_date": day.strftime("%Y-%m-%d"),
                    "near_contract_close": 210000 + idx * 50,
                    "far_contract_close": 211000 + idx * 48,
                    "near_open_interest": 20000 + idx,
                    "far_open_interest": 18000 + idx,
                    "main_contract": "SN2601",
                }
                for idx, day in enumerate(dates)
            ]
            basis_rows = [
                {"trade_date": day.strftime("%Y-%m-%d"), "spot_price": 211000 + idx * 50, "spot_premium": 200}
                for idx, day in enumerate(dates)
            ]
            inventory_rows = [
                {"trade_date": day.strftime("%Y-%m-%d"), "shfe_inventory": 1000 + idx, "lme_inventory": 2000 + idx}
                for idx, day in enumerate(dates)
            ]
            cross_rows = [
                {"trade_date": day.strftime("%Y-%m-%d"), "lme_tin_close": 30000 + idx, "usd_cny": 7.0 + idx * 0.0001, "dxy": 100 + idx * 0.01, "us10y": 4.0}
                for idx, day in enumerate(dates)
            ]
            for name, rows in {
                "sn_term_structure.json": term_rows,
                "sn_spot_basis.json": basis_rows,
                "sn_inventory.json": inventory_rows,
                "sn_cross_market.json": cross_rows,
            }.items():
                (fundamentals / name).write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")

            report = build_feature_coverage_report()

        by_group = {group["group"]: group for group in report["groups"]}
        self.assertGreater(by_group["term_structure"]["available_feature_count"], 0)
        self.assertGreater(by_group["basis"]["available_feature_count"], 0)
        self.assertGreater(by_group["inventory"]["available_feature_count"], 0)
        self.assertGreater(by_group["cross_market"]["available_feature_count"], 0)

    def test_used_in_model_false_news_does_not_enter_event_factor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            events = Path(tmp) / "outputs" / "events"
            events.mkdir(parents=True, exist_ok=True)
            (events / "news_events.json").write_text(
                json.dumps({"events": [{"published_at": "2026-01-10", "impact_score": 0.9, "used_in_model": False}]}),
                encoding="utf-8",
            )
            report = build_feature_coverage_report()

        event_group = next(group for group in report["groups"] if group["group"] == "event")
        self.assertEqual(event_group["available_feature_count"], 0)


if __name__ == "__main__":
    unittest.main()


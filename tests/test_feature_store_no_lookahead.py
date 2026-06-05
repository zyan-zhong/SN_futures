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

from sn_futures.services.feature_store_service import build_feature_store


def _write_market(root: str) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=80, freq="D")):
        close = 200000.0 + idx * 100.0
        rows.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 50,
                "high": close + 250,
                "low": close - 250,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class FeatureStoreNoLookaheadTest(unittest.TestCase):
    def test_event_factor_exact_date_join_does_not_leak_to_prior_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            events = Path(tmp) / "outputs" / "events"
            events.mkdir(parents=True, exist_ok=True)
            (events / "event_factor_inputs.json").write_text(
                json.dumps(
                    {
                        "used_in_model_count": 1,
                        "inputs": [
                            {
                                "trade_date": "2026-01-05",
                                "news_count": 1,
                                "used_in_model_count": 1,
                                "supply_shock_score": 0.7,
                                "event_recency_decay_score": 1.0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_feature_store(version="v3")
            frame = pd.read_csv(result["feature_store_path"])

        before = frame[pd.to_datetime(frame["trade_date"]) < pd.Timestamp("2026-01-05")]
        event_day = frame[frame["trade_date"] == "2026-01-05"].iloc[0]
        after = frame[pd.to_datetime(frame["trade_date"]) > pd.Timestamp("2026-01-05")]

        self.assertTrue((before["supply_shock_score"] == 0).all())
        self.assertAlmostEqual(float(event_day["supply_shock_score"]), 0.7)
        self.assertTrue((after["supply_shock_score"] == 0).all())
        self.assertEqual(event_day["_event_data_status"], "event_observed")
        self.assertTrue((before["_event_data_status"] == "true_zero_event").all())

    def test_used_in_model_false_events_do_not_enter_feature_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            events = Path(tmp) / "outputs" / "events"
            events.mkdir(parents=True, exist_ok=True)
            (events / "event_factor_inputs.json").write_text(
                json.dumps(
                    {
                        "used_in_model_count": 0,
                        "inputs": [
                            {
                                "trade_date": "2026-01-05",
                                "used_in_model": False,
                                "supply_shock_score": 0.9,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_feature_store(version="v3")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            frame = pd.read_csv(result["feature_store_path"])

        self.assertTrue((frame["supply_shock_score"] == 0).all())
        self.assertNotIn("supply_shock_score", manifest["usable_fields"])
        self.assertIn("supply_shock_score", manifest["excluded_fields"])
        self.assertIn("no_used_in_model_event_inputs", manifest["exclusion_reasons"]["supply_shock_score"])


if __name__ == "__main__":
    unittest.main()

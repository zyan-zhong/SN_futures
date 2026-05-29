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

from sn_futures.services.training_dataset_service import build_training_dataset


def _write_history(root: str, rows: int = 180) -> Path:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=rows, freq="D")):
        close = 210000.0 + idx * 75.0 + (idx % 7) * 30.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 120,
                "high": close + 420,
                "low": close - 360,
                "close": close,
                "volume": 9000 + idx,
                "open_interest": 120000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")
    return output


def _write_v2_inputs(output: Path, rows: int = 180) -> None:
    fundamentals = output / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    cross_rows = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=rows, freq="D")):
        cross_rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "usd_cny": 7.0 + idx * 0.0001,
                "usd_cny_return": 0.0001,
                "us10y": 4.0 + idx * 0.001,
                "us10y_change": 0.001,
                "copper_global_proxy": 9000.0 + idx,
                "copper_proxy_return": 0.0002,
                "source": "alpha_vantage_fixture",
            }
        )
    (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": cross_rows}, ensure_ascii=False), encoding="utf-8")

    events = output / "events"
    events.mkdir(parents=True, exist_ok=True)
    (events / "event_factor_inputs.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "published_at": "2025-02-01T08:00:00",
                        "category": "supply",
                        "impact_score": 0.7,
                        "used_in_model": True,
                    },
                    {
                        "published_at": "2025-02-01T08:00:00",
                        "category": "supply",
                        "impact_score": 100.0,
                        "used_in_model": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class FeatureSetV2CrossMarketEventTest(unittest.TestCase):
    def test_v2_feature_set_includes_real_cross_market_and_used_events_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_history(tmp)
            _write_v2_inputs(output)

            manifest = build_training_dataset(
                horizons=(1,),
                dataset_version="v2",
                feature_set="ohlcv_technical_regime_cross_market_event",
                min_feature_coverage=0.7,
            )

            self.assertEqual(manifest["status"], "success")
            self.assertIn("usd_cny", manifest["feature_cols"])
            self.assertIn("us10y", manifest["feature_cols"])
            self.assertIn("copper_global_proxy", manifest["feature_cols"])
            self.assertIn("news_event_score", manifest["feature_cols"])
            self.assertEqual(manifest["event_factor_input_count"], 1)
            self.assertFalse(manifest["sample_data_used"])
            self.assertFalse(manifest["baseline_used"])
            self.assertTrue(manifest["leakage_check_pass"])

            dataset_path = Path(manifest["dataset_paths"]["1d"])
            dataset = pd.read_parquet(dataset_path) if dataset_path.suffix == ".parquet" else pd.read_csv(dataset_path)
            self.assertLess(float(dataset["news_event_score"].max()), 1.0)
            self.assertNotIn("lme_tin_close", manifest["feature_cols"])
            self.assertNotIn("spot_futures_basis", manifest["feature_cols"])


if __name__ == "__main__":
    unittest.main()

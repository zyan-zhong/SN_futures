from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v5


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class FeatureStoreV5NoLookaheadTest(unittest.TestCase):
    def test_event_inputs_do_not_leak_to_prior_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            out = Path(tmp) / "outputs"
            start = date(2026, 1, 1)
            market = [{"trade_date": (start + timedelta(days=i)).isoformat(), "open": 1 + i, "high": 2 + i, "low": 1 + i, "close": 2 + i, "volume": 100 + i} for i in range(70)]
            _write(out / "sn_market_history.json", {"history": market})
            event_day = market[20]["trade_date"]
            _write(out / "events" / "event_factor_inputs.json", {"inputs": [{"trade_date": event_day, "used_in_model": True, "news_count": 1, "used_in_model_count": 1, "supply_shock_score": 0.9}]})

            manifest = build_feature_store_v5()
            frame = pd.read_csv(out / "feature_store" / "v5" / "feature_store.csv")
            before = frame[frame["trade_date"] < event_day]["supply_shock_score"].fillna(0).sum()
            on_day = float(frame.loc[frame["trade_date"] == event_day, "supply_shock_score"].iloc[0])

            self.assertEqual(before, 0.0)
            self.assertGreater(on_day, 0.0)
            self.assertTrue(manifest["no_lookahead_pass"])


if __name__ == "__main__":
    unittest.main()

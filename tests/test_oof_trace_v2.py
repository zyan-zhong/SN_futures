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
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 240) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 230000.0 + idx * 45.0 + (idx % 13) * 110.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 160,
                "high": close + 440,
                "low": close - 420,
                "close": close,
                "volume": 9500 + idx,
                "open_interest": 140000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class OOFTraceV2Test(unittest.TestCase):
    def test_oof_trace_v2_schema_contains_research_context_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), dataset_version="v2", feature_set="ohlcv_technical_regime_cross_market_event")
            result = run_candidate_training(horizons=("1d",), candidate_version="v2", dataset_version="v2")

            trace_path = Path(result["oof_trace_paths"]["1d"])
            frame = pd.read_csv(trace_path)

            for column in (
                "candidate_version",
                "dataset_version",
                "feature_set",
                "horizon",
                "fold_id",
                "label_end_time",
                "event_shock_score",
                "usd_cny",
                "us10y",
                "copper_global_proxy",
                "model_family",
            ):
                self.assertIn(column, frame.columns)
            self.assertEqual(set(frame["candidate_version"].dropna().unique()), {"v2"})
            self.assertEqual(set(frame["dataset_version"].dropna().unique()), {"v2"})
            self.assertGreater(len(frame), 0)


if __name__ == "__main__":
    unittest.main()

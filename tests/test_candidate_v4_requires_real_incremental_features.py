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

from sn_futures.services.feature_store_v4_service import check_feature_store_v4_readiness


def _write_market(root: str, periods: int = 120) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 50.0
        rows.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 50.0,
                "high": close + 250.0,
                "low": close - 250.0,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class CandidateV4RequiresRealIncrementalFeaturesTest(unittest.TestCase):
    def test_v4_readiness_blocks_when_cross_market_and_event_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            result = check_feature_store_v4_readiness()
            output = Path(tmp) / "outputs"

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["candidate_version"], "v4")
        self.assertEqual(result["incremental_feature_cols"], [])
        self.assertIn("没有真实新增 cross-market 或 event 字段", result["reason_zh"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()

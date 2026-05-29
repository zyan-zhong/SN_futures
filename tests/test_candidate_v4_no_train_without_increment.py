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

from sn_futures.services.feature_store_v4_service import run_candidate_v4_research


def _write_market(root: str, periods: int = 120) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 50.0
        rows.append({"time": day.strftime("%Y-%m-%d"), "open": close - 50, "high": close + 200, "low": close - 200, "close": close, "volume": 1000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class CandidateV4NoTrainWithoutIncrementTest(unittest.TestCase):
    def test_candidate_v4_does_not_train_or_overwrite_when_increment_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            output = Path(tmp) / "outputs"
            registry_dir = output / "model_registry"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "candidate_v3_model_registry.json").write_text("sentinel-v3", encoding="utf-8")
            with patch("sn_futures.services.feature_store_v4_service.run_candidate_training") as trainer:
                result = run_candidate_v4_research()
            v3_sentinel = (registry_dir / "candidate_v3_model_registry.json").read_text(encoding="utf-8")

        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(v3_sentinel, "sentinel-v3")
        self.assertFalse((registry_dir / "candidate_v4_model_registry.json").exists())
        self.assertFalse((registry_dir / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()

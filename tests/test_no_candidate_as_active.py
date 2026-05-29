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

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.governance.model_registry import ModelRegistry
from sn_futures.services.training_dataset_service import build_training_dataset
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 220) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 205000.0 + idx * 50.0 + (idx % 11) * 100.0
        history.append({"time": day.strftime("%Y-%m-%d"), "open": close - 100, "high": close + 450, "low": close - 450, "close": close, "volume": 9000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class NoCandidateAsActiveTest(unittest.TestCase):
    def test_candidate_training_does_not_create_active_or_prediction_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), min_feature_coverage=0.7)
            result = run_candidate_training(["1d"])
            registry = ModelRegistry(Path(result["registry_path"]))
            self.assertIsNone(registry.get_active_model("1d"))
            output = Path(tmp) / "outputs"
            self.assertFalse((output / "sn_live_predictions.json").exists())
            self.assertFalse((output / "sn_unified_forecast.json").exists())
            status, payload = handle_terminal_api("/api/terminal/predictions", "GET")
            self.assertEqual(status, 200)
            dumped = safe_json_dumps(payload).lower()
            self.assertNotIn("baseline forecast", dumped)
            self.assertNotIn("baseline backtest", dumped)


if __name__ == "__main__":
    unittest.main()

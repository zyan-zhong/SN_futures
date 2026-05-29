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
from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


def _write_history(root: str, rows: int = 80) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=rows, freq="D")):
        close = 250000.0 + idx * 80
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 120,
                "high": close + 450,
                "low": close - 520,
                "close": close,
                "volume": 9000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class TerminalTrainingDatasetApiTest(unittest.TestCase):
    def test_build_and_status_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            status, payload = handle_terminal_api(
                "/api/terminal/training-dataset/build",
                "POST",
                {},
                {"horizons": [1, 3], "min_feature_coverage": 0.7},
            )
            status2, payload2 = handle_terminal_api("/api/terminal/training-dataset/status", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload2["status"], "success")
        self.assertTrue(payload["leakage_check_pass"])
        safe_json_dumps(payload)

    def test_training_dataset_api_does_not_generate_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            handle_terminal_api("/api/terminal/training-dataset/build", "POST", {}, {"horizons": [1]})
            output_files = {path.name for path in (Path(tmp) / "outputs").glob("*")}
        self.assertNotIn("sn_live_predictions.json", output_files)
        self.assertNotIn("sn_unified_forecast.json", output_files)

    def test_docs_include_training_dataset_api(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/training-dataset/build", paths)
        self.assertIn("/api/terminal/training-dataset/status", paths)


if __name__ == "__main__":
    unittest.main()

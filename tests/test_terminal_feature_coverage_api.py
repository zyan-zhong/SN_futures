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


def _write_history(root: str) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=150, freq="D")):
        close = 210000.0 + idx * 100
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 600,
                "low": close - 700,
                "close": close,
                "volume": 5000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class TerminalFeatureCoverageApiTest(unittest.TestCase):
    def test_feature_coverage_endpoint_is_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            status, payload = handle_terminal_api("/api/terminal/factors/coverage", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertIn("groups", payload)
        self.assertIn("training_readiness", payload)
        dumped = safe_json_dumps(payload)
        self.assertNotIn("NaN", dumped)

    def test_feature_coverage_endpoint_does_not_generate_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            status, payload = handle_terminal_api("/api/terminal/factors/coverage", "GET", {}, None)
            output_files = {path.name for path in (Path(tmp) / "outputs").glob("*")}
        self.assertEqual(status, 200)
        self.assertNotIn("sn_live_predictions.json", output_files)
        self.assertNotIn("sn_unified_forecast.json", output_files)
        self.assertIn("不训练模型", payload["message_zh"])

    def test_docs_include_feature_coverage_endpoint(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/factors/coverage", paths)


if __name__ == "__main__":
    unittest.main()

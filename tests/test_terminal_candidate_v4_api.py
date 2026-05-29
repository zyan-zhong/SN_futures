from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


def _write_market(root: str, periods: int = 90) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200000 + idx * 50
        rows.append({"time": day.strftime("%Y-%m-%d"), "open": close - 10, "high": close + 100, "low": close - 100, "close": close, "volume": 1000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


def test_candidate_v4_api_is_documented() -> None:
    paths = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
    assert "/api/terminal/research/run-candidate-v4" in paths
    assert "/api/terminal/research/run-backtest" in paths
    assert "/api/terminal/research/equity-curve" in paths


def test_candidate_v4_api_blocks_without_increment_and_does_not_publish_active() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_market(tmp)
        status, payload = handle_terminal_api("/api/terminal/research/run-candidate-v4", "POST", {}, {"horizons": ["1d"]})
        output = Path(tmp) / "outputs"

    assert status == 200
    assert payload["status"] == "blocked"
    assert "没有真实新增 cross-market 或 event 字段" in payload["reason_zh"]
    assert not (output / "model_registry" / "active_model.json").exists()
    assert not (output / "sn_live_predictions.json").exists()

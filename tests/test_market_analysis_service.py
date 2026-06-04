from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.market_analysis_service import build_market_analysis


def _write_market_history(root: str, rows: int = 90) -> Path:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx in range(rows):
        close = 230000 + idx * 120 + (idx % 7) * 35
        history.append(
            {
                "time": f"2025-01-{(idx % 28) + 1:02d}" if idx < 28 else f"2025-02-{((idx - 28) % 28) + 1:02d}" if idx < 56 else f"2025-03-{((idx - 56) % 28) + 1:02d}",
                "open": close - 80,
                "high": close + 380,
                "low": close - 360,
                "close": close,
                "volume": 10000 + idx * 8,
            }
        )
    path = output / "sn_market_history.json"
    path.write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")
    (output / "sn_live_snapshot.json").write_text(
        json.dumps({"latest_price": history[-1]["close"], "realtime_status": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


class MarketAnalysisServiceTest(unittest.TestCase):
    def test_ohlcv_market_analysis_outputs_trend_volatility_levels_and_risk_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market_history(tmp)
            analysis = build_market_analysis()

        self.assertEqual(analysis["status"], "success")
        self.assertEqual(analysis["analysis_mode"], "ohlcv_regime_analysis")
        self.assertTrue(analysis["not_prediction"])
        self.assertIn(analysis["trend"]["short_term"], {"up", "down", "range"})
        self.assertIn("atr_14", analysis["volatility"])
        self.assertIn("support_levels", analysis["key_levels"])
        self.assertIn("volume_trend", analysis["volume_liquidity"])
        self.assertIn("label", analysis["regime"])
        self.assertIn("基本面数据不足", analysis["risk_flags"])

    def test_market_analysis_api_is_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market_history(tmp)
            status, payload = handle_terminal_api("/api/terminal/market-analysis")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["not_prediction"])


if __name__ == "__main__":
    unittest.main()

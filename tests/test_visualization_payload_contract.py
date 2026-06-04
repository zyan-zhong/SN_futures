from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")


class VisualizationPayloadContractTest(unittest.TestCase):
    def test_price_and_volume_payloads_have_explicit_chart_contract(self) -> None:
        from sn_futures.services.chart_payload_service import build_price_chart_payload, build_volume_chart_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            output.mkdir(parents=True, exist_ok=True)
            rows = [
                {"time": "2026-05-20", "open": 100, "high": 110, "low": 95, "close": 105, "volume": 1000},
                {"time": "2026-05-21", "open": 105, "high": 112, "low": 101, "close": 108, "volume": 1200},
            ]
            (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")

            price = build_price_chart_payload()
            volume = build_volume_chart_payload()

        self.assertEqual(price["schema_version"], 1)
        self.assertEqual(price["chart_type"], "price")
        self.assertEqual(price["x_field"], "time")
        self.assertEqual(price["y_fields"], ["open", "high", "low", "close"])
        self.assertEqual(price["units"]["price"], "CNY/ton")
        self.assertIn("sn_market_history.json", price["source_files"])
        self.assertEqual(price["points"][0]["time"], "2026-05-20")
        self.assertEqual(price["points"][1]["close"], 108)
        self.assertFalse(price["research_only"])
        self.assertEqual(price["missing_reason"], "")

        self.assertEqual(volume["schema_version"], 1)
        self.assertEqual(volume["chart_type"], "volume")
        self.assertEqual(volume["x_field"], "time")
        self.assertEqual(volume["y_fields"], ["volume", "open_interest"])
        self.assertEqual(volume["units"]["volume"], "contracts")
        self.assertEqual(volume["points"][0]["volume"], 1000)

    def test_empty_payload_has_professional_missing_reason_not_blank_canvas(self) -> None:
        from sn_futures.services.chart_payload_service import build_price_chart_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_price_chart_payload()

        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["points"], [])
        self.assertEqual(payload["missing_reason"], "no_market_history_file")
        self.assertIn("暂无真实行情历史", payload["message_zh"])


if __name__ == "__main__":
    unittest.main()

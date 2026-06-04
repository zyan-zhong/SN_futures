from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")


class ResearchBacktestChartContractTest(unittest.TestCase):
    def test_equity_curve_payload_is_research_only_with_source_file(self) -> None:
        from sn_futures.services.chart_payload_service import build_equity_curve_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            folder = Path(tmp) / "outputs" / "research_backtests" / "v5"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "equity_curve_1d.csv").write_text("ts,value\n2026-01-01,1.0\n2026-01-02,1.02\n", encoding="utf-8")
            payload = build_equity_curve_payload(version="v5", horizon="1d")

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["chart_type"], "equity_curve")
        self.assertTrue(payload["research_only"])
        self.assertEqual(payload["x_field"], "ts")
        self.assertEqual(payload["y_fields"], ["value"])
        self.assertEqual(payload["units"]["equity"], "multiple")
        self.assertIn("equity_curve_1d.csv", payload["source_files"])
        self.assertEqual(payload["points"][1]["value"], 1.02)
        self.assertNotIn("active", payload.get("message_zh", "").lower())

    def test_missing_research_backtest_payload_has_empty_state_reason(self) -> None:
        from sn_futures.services.chart_payload_service import build_equity_curve_payload

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_equity_curve_payload(version="v5", horizon="1d")

        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["points"], [])
        self.assertEqual(payload["missing_reason"], "no_equity_curve_file")
        self.assertIn("研究回测", payload["message_zh"])


if __name__ == "__main__":
    unittest.main()

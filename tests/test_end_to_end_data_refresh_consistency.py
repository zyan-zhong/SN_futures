from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.data_consistency_audit_service import build_data_consistency_report
from sn_futures.services.data_watermark_service import update_data_watermark


def _write_market_history(output: Path, days: int = 30) -> str:
    start = date(2026, 5, 1)
    rows = []
    for index in range(days):
        current = start + timedelta(days=index)
        rows.append(
            {
                "time": current.isoformat(),
                "open": 240000 + index,
                "high": 241000 + index,
                "low": 239000 + index,
                "close": 240500 + index,
                "volume": 10000 + index,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")
    return rows[-1]["time"]


class EndToEndDataRefreshConsistencyTest(unittest.TestCase):
    def test_real_market_refresh_aligns_watermark_chart_and_analysis_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            latest = _write_market_history(output)
            update_data_watermark("market", source="unit-test-refresh")

            report = build_data_consistency_report()

        self.assertEqual(report["status"], "consistent")
        self.assertEqual(report["latest_dates"]["market_history"], latest)
        self.assertEqual(report["latest_dates"]["price_history"], latest)
        self.assertEqual(report["latest_dates"]["price_chart"], latest)
        self.assertEqual(report["latest_dates"]["market_analysis"], latest)
        self.assertFalse(report["sample_mode_active"])
        self.assertTrue(report["checks"]["watermark_updated"])
        self.assertTrue(report["checks"]["chart_matches_market_history"])
        self.assertTrue(report["checks"]["analysis_matches_market_history"])

    def test_data_consistency_api_returns_json_safe_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            latest = _write_market_history(output)
            update_data_watermark("market", source="api-test")
            status, payload = handle_terminal_api("/api/terminal/data-consistency-report")

        self.assertEqual(status, 200)
        self.assertEqual(payload["latest_dates"]["market_history"], latest)
        self.assertNotIn("NaN", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("fake prediction", json.dumps(payload, ensure_ascii=False).lower())


if __name__ == "__main__":
    unittest.main()

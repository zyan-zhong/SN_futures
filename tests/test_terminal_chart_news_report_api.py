from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalChartNewsReportApiTest(unittest.TestCase):
    def test_price_history_no_data_returns_empty_points_and_chinese_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.v2_api.get_price_forecast_chart",
            return_value={"history": []},
        ):
            status, payload = handle_terminal_api("/api/terminal/charts/price-history", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertTrue(payload["sample_mode"])
        self.assertGreater(len(payload["points"]), 0)
        self.assertIn("样例数据", payload["message_zh"])
        safe_json_dumps(payload)

    def test_forecast_path_no_prediction_returns_empty_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/charts/forecast-path", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertTrue(payload["sample_mode"])
        self.assertGreater(len(payload["points"]), 0)
        self.assertIn("样例数据", payload["message_zh"])
        safe_json_dumps(payload)

    def test_news_without_key_returns_empty_events_and_chinese_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""},
            clear=False,
        ):
            status, payload = handle_terminal_api("/api/terminal/events/news", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertTrue(payload["sample_mode"])
        self.assertGreater(len(payload["events"]), 0)
        self.assertTrue(all(item["title"].startswith("[样例]") for item in payload["events"]))
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("TEST_NEWS", text)

    def test_reports_full_returns_markdown_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report_dir = Path(tmp) / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "sn_daily_report.md").write_text("# 日报\n\n数据不足版报告", encoding="utf-8")
            status, payload = handle_terminal_api("/api/terminal/reports/full", "GET", {"type": ["daily"]}, None)
        self.assertEqual(status, 200)
        self.assertIn("markdown", payload)
        self.assertIn("日报", payload["markdown"])
        safe_json_dumps(payload)

    def test_factor_diagnostics_no_data_is_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/factors/diagnostics", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertEqual(payload["groups"], [])
        self.assertIn("暂无完整因子诊断数据", payload["message_zh"])
        safe_json_dumps(payload)

    def test_docs_include_new_display_apis(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        for path in (
            "/api/terminal/charts/price-history",
            "/api/terminal/charts/forecast-path",
            "/api/terminal/charts/equity-curve",
            "/api/terminal/charts/drawdown",
            "/api/terminal/events/news",
            "/api/terminal/events/source-quality-report",
            "/api/terminal/events/evidence",
            "/api/terminal/reports/full",
            "/api/terminal/factors/diagnostics",
        ):
            self.assertIn(path, paths)

    def test_all_new_display_apis_are_json_safe_and_do_not_leak_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_ALPHA_VANTAGE_KEY": "ALPHATEST1234567890",
                "SN_NEWSAPI_KEY": "",
            },
            clear=False,
        ), patch("sn_futures.v2_api.get_price_forecast_chart", return_value={"history": [], "forecast": []}):
            for path in (
                "/api/terminal/charts/price-history",
                "/api/terminal/charts/forecast-path",
                "/api/terminal/charts/equity-curve",
                "/api/terminal/charts/drawdown",
                "/api/terminal/events/news",
                "/api/terminal/events/source-quality-report",
                "/api/terminal/events/evidence",
                "/api/terminal/reports/full",
                "/api/terminal/factors/diagnostics",
            ):
                status, payload = handle_terminal_api(path, "GET", {}, None)
                self.assertEqual(status, 200, path)
                dumped = safe_json_dumps(payload)
                self.assertNotIn("ALPHATEST1234567890", dumped)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.runtime_diagnostics_service import build_runtime_data_diagnostics


class RuntimeDiagnosticsTest(unittest.TestCase):
    def test_runtime_diagnostics_endpoint_returns_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/runtime-diagnostics", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertIn("expected_output_files", payload)
        self.assertIn("data_gap_conclusion", payload)
        safe_json_dumps(payload)

    def test_empty_user_data_dir_reports_missing_predictions_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_runtime_data_diagnostics()
        conclusion = payload["data_gap_conclusion"]
        self.assertTrue(conclusion["no_predictions"])
        self.assertTrue(conclusion["no_reports"])
        self.assertTrue(conclusion["frontend_only_shell"])
        self.assertIn("运行数据刷新", " ".join(payload["next_actions_zh"]))

    def test_fake_forecast_cache_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "sn_unified_forecast.json").write_text(
                json.dumps(
                    {
                        "cards": {"h1d": {}, "h10d": {}},
                        "data_watermark": {"latest_price": 250000},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = build_runtime_data_diagnostics()
        unified = next(item for item in payload["expected_output_files"] if item["relative_name"] == "sn_unified_forecast.json")
        self.assertTrue(unified["exists"])
        self.assertTrue(unified["json_valid"])
        self.assertEqual(unified["card_count"], 2)
        self.assertTrue(unified["has_quote"])
        self.assertEqual(unified["latest_price"], 250000)

    def test_fake_report_markdown_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report_dir = Path(tmp) / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "sn_daily_report.md").write_text("# 日报\n\n仅供投研参考。", encoding="utf-8")
            payload = build_runtime_data_diagnostics()
        report = next(item for item in payload["expected_output_files"] if item["relative_name"] == "reports/sn_daily_report.md")
        self.assertTrue(report["exists"])
        self.assertGreater(report["report_length"], 0)
        self.assertFalse(payload["data_gap_conclusion"]["no_reports"])

    def test_runtime_diagnostics_does_not_leak_full_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_ALPHA_VANTAGE_KEY": "ALPHATEST1234567890",
                "SN_NEWSAPI_KEY": "NEWSTEST1234567890",
            },
            clear=False,
        ):
            payload = build_runtime_data_diagnostics()
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("ALPHATEST1234567890", text)
        self.assertNotIn("NEWSTEST1234567890", text)

    def test_terminal_docs_include_runtime_diagnostics(self) -> None:
        endpoints = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/runtime-diagnostics", endpoints)

    def test_frontend_runtime_diagnostics_entry_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        data_status_page = (root / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
        component = (root / "frontend" / "src" / "components" / "data" / "RuntimeDiagnosticsPanel.tsx").read_text(encoding="utf-8")
        terminal_api = (root / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("RuntimeDiagnosticsPanel", data_status_page)
        self.assertIn("运行期诊断", component)
        self.assertIn("/api/terminal/runtime-diagnostics", terminal_api)
        self.assertNotIn("ALPHATEST1234567890", component)


if __name__ == "__main__":
    unittest.main()

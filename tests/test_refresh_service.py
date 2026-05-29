from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.refresh_service import (
    get_refresh_history,
    get_refresh_status,
    refresh_news_data,
    refresh_predictions,
    refresh_reports,
    run_refresh_steps,
)


class RefreshServiceTest(unittest.TestCase):
    def test_news_step_skips_when_newsapi_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""},
            clear=False,
        ):
            result = refresh_news_data()
            status_path = Path(tmp) / "outputs" / "events" / "provider_status.json"
            status_exists = status_path.exists()

        self.assertEqual(result["status"], "skipped")
        self.assertIn("未配置 NewsAPI", result["message_zh"])
        self.assertTrue(status_exists)

    def test_refresh_status_and_history_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""},
            clear=False,
        ):
            result = run_refresh_steps(["news"], force=False)
            status = get_refresh_status()
            history = get_refresh_history()
            status_path = Path(tmp) / "outputs" / "refresh_status.json"
            history_path = Path(tmp) / "outputs" / "refresh_history.json"
            status_exists = status_path.exists()
            history_exists = history_path.exists()

        self.assertEqual(result["status"], "success")
        self.assertTrue(status_exists)
        self.assertTrue(history_exists)
        self.assertEqual(status["steps"][0]["status"], "skipped")
        self.assertGreaterEqual(history["count"], 1)

    def test_provider_failure_is_reported_without_crashing(self) -> None:
        failed = {
            "name": "newsapi",
            "enabled": True,
            "success": False,
            "from_cache": False,
            "message": "provider failed",
            "articles": [],
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "TEST_NEWS_1234567890"},
            clear=False,
        ), patch("sn_futures.services.refresh_service.NewsApiProvider.fetch_tin_news", return_value=failed):
            result = refresh_news_data()

        self.assertEqual(result["status"], "failed")
        self.assertIn("NewsAPI 刷新失败", result["message_zh"])

    def test_prediction_refresh_does_not_create_fake_cards_when_data_is_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.v2_api.get_live_predictions",
            return_value={"cards": {}},
        ), patch("sn_futures.v2_api.get_data_watermark", return_value={"quality_score": 0.0}):
            result = refresh_predictions()
            unified = json.loads((Path(tmp) / "outputs" / "sn_unified_forecast.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(unified["cards"], {})
        self.assertIn("数据不足，未生成预测", unified["message_zh"])

    def test_reports_generate_data_insufficient_markdown_without_nan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.v2_api.get_live_predictions",
            return_value={"cards": {}},
        ):
            result = refresh_reports()
            report = (Path(tmp) / "reports" / "sn_daily_report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "success")
        self.assertIn("数据不足版报告", report)
        self.assertNotIn("nan", report.lower())


if __name__ == "__main__":
    unittest.main()

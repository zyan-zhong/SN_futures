from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from test_market_analysis_service import _write_market_history
from sn_futures.services.market_analysis_service import build_market_analysis


class MarketAnalysisWithoutExternalFundamentalsTest(unittest.TestCase):
    def test_analysis_runs_without_tushare_token_or_managed_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market_history(tmp)
            analysis = build_market_analysis()

        self.assertEqual(analysis["status"], "success")
        self.assertFalse(analysis["data_sources"]["tushare_available"])
        self.assertFalse(analysis["data_sources"]["managed_proxy_available"])
        self.assertIn("basis", analysis["missing_fundamentals"])
        self.assertIn("inventory", analysis["missing_fundamentals"])
        self.assertIn("lme_tin", analysis["missing_fundamentals"])
        self.assertIn("warehouse_receipt", analysis["missing_fundamentals"])
        self.assertIn("当前不生成预测", " ".join(analysis["next_actions_zh"]))

    def test_insufficient_history_returns_chinese_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market_history(tmp, rows=10)
            analysis = build_market_analysis()

        self.assertEqual(analysis["status"], "insufficient_data")
        self.assertIn("真实历史行情不足", analysis["message_zh"])


if __name__ == "__main__":
    unittest.main()

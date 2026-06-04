from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from test_market_analysis_service import _write_market_history
from sn_futures.services.market_analysis_service import build_market_analysis


class MarketAnalysisNoPredictionPolicyTest(unittest.TestCase):
    def test_analysis_contains_no_trade_points_or_prediction_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market_history(tmp)
            analysis = build_market_analysis()

        dumped = json.dumps(analysis, ensure_ascii=False)
        self.assertTrue(analysis["not_prediction"])
        self.assertNotIn('"entry"', dumped)
        self.assertNotIn("stop_loss", dumped)
        self.assertNotIn("take_profit", dumped)
        self.assertNotIn("预测上涨", dumped)
        self.assertNotIn("预测下跌", dumped)
        self.assertNotIn("建议买入", dumped)
        self.assertNotIn("建议卖出", dumped)
        self.assertIn("行情分析不构成投资建议", analysis["disclaimer"])


if __name__ == "__main__":
    unittest.main()

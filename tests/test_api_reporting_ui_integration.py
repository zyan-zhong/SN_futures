from __future__ import annotations

import json
import math
import unittest
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, "src")

from sn_futures.services.payload_utils import sanitize_for_json
from sn_futures.v2_api import (
    evaluate_position_scenario_api,
    get_backtest_diagnostics,
    get_learning_status,
    get_live_predictions,
    get_models_health,
    get_report_content,
)


def _walk(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


class ApiReportingUiIntegrationTest(unittest.TestCase):
    def test_api_payloads_do_not_contain_json_nan(self) -> None:
        payloads = [
            get_live_predictions(),
            get_models_health(),
            get_learning_status(),
            get_backtest_diagnostics("tomorrow"),
            get_report_content("daily"),
        ]
        for payload in payloads:
            json.dumps(payload, ensure_ascii=False, allow_nan=False)
            for item in _walk(payload):
                self.assertFalse(isinstance(item, float) and math.isnan(item))

    def test_observe_signal_has_no_trade_points(self) -> None:
        live = get_live_predictions()
        for card in live.get("cards", {}).values():
            if isinstance(card, dict) and card.get("信号") == "观望":
                self.assertIsNone(card.get("entry"))
                self.assertIsNone(card.get("entry_price"))
                self.assertIsNone(card.get("stop_loss"))
                self.assertIsNone(card.get("take_profit"))
                self.assertEqual("暂无交易点位", card.get("trade_point_note"))

    def test_live_cards_expose_chinese_business_fields(self) -> None:
        live = get_live_predictions()
        self.assertIn("cards", live)
        for horizon, card in live["cards"].items():
            with self.subTest(horizon=horizon):
                for key in ["周期", "方向", "上涨概率", "校准后概率", "预测收益", "预测区间", "置信度", "信号", "决策说明", "核心因子", "事件依据", "风险提示", "数据质量", "模型状态", "回测摘要", "路径守门结果"]:
                    self.assertIn(key, card)

    def test_report_contains_no_nan_or_future_month_end_phrase(self) -> None:
        for report_type in ["daily", "weekly", "monthly", "event"]:
            report = get_report_content(report_type)
            text = json.dumps(report, ensure_ascii=False).lower()
            self.assertNotIn("nan", text)
            self.assertNotIn("month end", text)
            self.assertIn("数据截止时间", report["markdown"])
            self.assertIn("重要声明", report["markdown"])

    def test_degraded_or_missing_active_does_not_emit_trade_points(self) -> None:
        payload = sanitize_for_json(
            evaluate_position_scenario_api(
                {
                    "position_direction": "long",
                    "quantity": "1",
                    "avg_price": "420000",
                    "account_equity": "200000",
                    "max_loss": "5000",
                    "holding_horizon": "tomorrow",
                }
            )
        )
        text = json.dumps(payload, ensure_ascii=False)
        self.assertTrue(payload["ok"])
        self.assertIn("名义敞口", payload)
        self.assertIn("仅用于", payload["disclaimer"])
        for forbidden in ["必须买入", "必须卖出", "保证盈利", "保证上涨", "保证下跌"]:
            self.assertNotIn(forbidden, text)

    def test_frontend_contains_required_chinese_panels(self) -> None:
        html = Path("ui_web/index.html").read_text(encoding="utf-8")
        app = Path("ui_web/app.js").read_text(encoding="utf-8")
        for text in ["七周期方向矩阵", "学习与回测", "持仓情景", "风险提示"]:
            self.assertIn(text, html)
        self.assertNotIn("backend contract complete", app.lower())
        self.assertNotIn("fake probability", app.lower())


if __name__ == "__main__":
    unittest.main()

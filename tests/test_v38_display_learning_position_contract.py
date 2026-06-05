from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.v2_api import evaluate_position_scenario_api, get_backtest_diagnostics, get_learning_status, get_live_predictions


class V38DisplayLearningPositionContractTest(unittest.TestCase):
    def test_live_cards_include_chinese_display_contract(self) -> None:
        payload = get_live_predictions()
        cards = payload.get("cards", {})
        if payload.get("status") == "blocked":
            self.assertEqual({}, cards)
            self.assertIn("blocking_reasons", payload)
            self.assertIn("guarded_layer", payload)
            self.assertIn("display_layer", payload)
            self.assertFalse(payload["guarded_layer"]["allowed_for_prediction"])
            self.assertTrue(payload["display_layer"]["display_only"])
            return
        self.assertEqual(
            {
                "next_5m",
                "next_15m",
                "next_30m",
                "next_hour",
                "tomorrow",
                "one_to_two_weeks",
                "one_to_three_months",
            },
            set(cards),
        )
        for horizon, card in cards.items():
            with self.subTest(horizon=horizon):
                self.assertIsInstance(card.get("display_tags"), list)
                self.assertGreaterEqual(len(card["display_tags"]), 6)
                self.assertIn("decision_explanation", card)
                self.assertIn("technical_tags", card)
                self.assertIn("risk_notes", card)
                self.assertIn("learning_status", card)
                self.assertIn("backtest_summary", card)
                self.assertIn("path_guard_summary", card)
                self.assertIn("headline", card["decision_explanation"])

    def test_learning_and_backtest_contracts_are_visible(self) -> None:
        learning = get_learning_status()
        self.assertIn("last_training", learning)
        self.assertIn("last_walk_forward", learning)
        self.assertIn("last_event_ablation", learning)
        self.assertIn("per_horizon", learning)
        backtest = get_backtest_diagnostics("tomorrow")
        self.assertEqual("tomorrow", backtest["horizon"])
        self.assertIn("selected_horizon_metrics", backtest)
        self.assertIn("promotion_result", backtest)
        self.assertIn("baseline_comparison", backtest)

    def test_position_scenario_remains_non_prescriptive(self) -> None:
        payload = evaluate_position_scenario_api(
            {
                "position_direction": "long",
                "quantity": "1",
                "avg_price": "420000",
                "account_equity": "200000",
                "max_loss": "5000",
                "holding_horizon": "tomorrow",
            }
        )
        text = str(payload)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload.get("zones", [])), 5)
        for forbidden in ["必须买入", "必须卖出", "保证上涨", "保证下跌", "保证盈利"]:
            self.assertNotIn(forbidden, text)
        self.assertIn("仅用于", payload["disclaimer"])

    def test_web_ui_mounts_learning_and_position_panels(self) -> None:
        html = Path("ui_web/index.html").read_text(encoding="utf-8")
        app = Path("ui_web/app.js").read_text(encoding="utf-8")
        for dom_id in ["learningBox", "backtestBox", "positionForm", "positionScenarioBox", "walkForwardBtn", "eventAblationBtn"]:
            self.assertIn(f'id="{dom_id}"', html)
            self.assertIn(dom_id, app)
        self.assertNotIn("后端预测合同完整", app)
        self.assertNotIn("未使用前端假概率", app)


if __name__ == "__main__":
    unittest.main()

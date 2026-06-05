from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.json_utils import clean_trade_points, safe_json_dumps
from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.terminal_service import build_terminal_model_health


FAKE_LIVE = {
    "generated_at": "2026-05-19T10:00:00",
    "data_watermark": {"quality_score": 0.42},
    "cards": {
        "tomorrow": {
            "horizon_label": "下一交易日",
            "direction": "neutral",
            "signal": "观望",
            "prob_up": 0.47,
            "raw_prob_up": 0.49,
            "expected_return": 0.001,
            "range_low": 248000.0,
            "range_high": 252000.0,
            "confidence_score": 58.0,
            "top_factors": ["动量证据不足"],
            "risk_notes": ["数据质量不足，已降级为研究观察。"],
            "data_quality_score": 0.42,
            "model_status": "degraded",
            "entry": 250000.0,
            "stop_loss": 250000.0,
            "take_profit": 250000.0,
        }
    },
}

FAKE_HEALTH = {
    "validation_mode": "walk_forward_or_live_cache",
    "per_horizon": {
        "tomorrow": {
            "active_model": "active-h1d",
            "candidate_model": "candidate-h1d",
            "failure_reasons": ["样本外夏普低于阈值"],
            "degradation_gate_status": {"degraded": True, "reasons": ["最近窗口表现退化"]},
        }
    },
}

FAKE_WATERMARK = {
    "quality_score": 0.42,
    "active_contract": "sn2605",
    "latest_price": 250000.0,
    "fetch_timestamp": "2026-05-19T10:00:00",
    "source_mode": "cached_live_prediction",
    "using_fallback": True,
    "data_quality_report": {"stale_data_flag": True},
}

FAKE_LEARNING = {
    "last_market_refresh": "2026-05-19T10:00:00",
    "last_prediction": "2026-05-19T10:01:00",
    "last_walk_forward": "2026-05-18T15:20:00",
    "message": "暂无可用 active 模型",
    "failure_reasons": ["候选模型尚未通过晋级门槛"],
}

FAKE_BACKTEST = {
    "horizon": "tomorrow",
    "walk_forward_metrics": {"方向命中率": "数据暂缺"},
    "baseline_comparison": {"naive": "待验证"},
    "cost_sensitivity": {"1x": "待验证"},
    "promotion_gate_conclusion": "active retained",
    "failure_reasons": ["交易次数不足"],
}


def terminal_patches():
    return patch.multiple(
        "sn_futures.v2_api",
        get_live_predictions=lambda: FAKE_LIVE,
        get_models_health=lambda: FAKE_HEALTH,
        get_learning_status=lambda: FAKE_LEARNING,
        get_backtest_diagnostics=lambda horizon="": FAKE_BACKTEST,
        get_data_watermark=lambda: FAKE_WATERMARK,
        get_report_content=lambda report_type="daily": {
            "type": report_type,
            "title": "沪锡期货报告",
            "generated_at": "2026-05-19T10:00:00",
            "data_cutoff": "2026-05-19T09:00:00",
            "markdown": "报告正文",
        },
        get_events_provider_status=lambda: {"providers": []},
        get_system_truth_audit=lambda: {"status": "pass"},
        evaluate_position_scenario_api=lambda payload: {
            "名义敞口": 250000.0,
            "保证金占用": 30000.0,
            "VaR 95": 2000.0,
            "压力 VaR": 4400.0,
            "观察区": [{"名称": "仅观望区"}],
            "风险区": [{"名称": "止损失效区"}],
            "周期共振": "周期共振待验证",
            "事件依据": ["暂无高权重事件"],
        },
    )


class TerminalApiTest(unittest.TestCase):
    def test_docs_endpoint_lists_terminal_routes(self) -> None:
        status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertIn("/api/terminal/summary", {row["path"] for row in payload["endpoints"]})

    def test_terminal_endpoints_are_json_safe(self) -> None:
        with terminal_patches():
            for path in (
                "/api/terminal/summary",
                "/api/terminal/snapshot",
                "/api/terminal/predictions",
                "/api/terminal/model-health",
                "/api/terminal/learning-status",
                "/api/terminal/backtest-diagnostics",
                "/api/terminal/reports",
                "/api/terminal/data-status",
                "/api/terminal/system-health",
            ):
                status, payload = handle_terminal_api(path, "GET", {"horizon": ["tomorrow"]}, None)
                self.assertEqual(status, 200, path)
                safe_json_dumps(payload)

    def test_predictions_are_list_and_trade_points_removed(self) -> None:
        with terminal_patches():
            status, payload = handle_terminal_api("/api/terminal/predictions", "GET", {}, None)
        self.assertEqual(status, 200)
        predictions = payload["predictions"]
        self.assertIsInstance(predictions, list)
        self.assertEqual(predictions[0]["entry"], None)
        self.assertEqual(predictions[0]["stop_loss"], None)
        self.assertEqual(predictions[0]["take_profit"], None)
        self.assertEqual(predictions[0]["trade_point_note"], "暂无交易点位")

    def test_predictions_without_keys_or_real_data_are_blocked_empty(self) -> None:
        env = {
            "SN_ALPHA_VANTAGE_KEY": "",
            "SN_NEWSAPI_KEY": "",
            "SN_TUSHARE_TOKEN": "",
            "SN_LOCAL_API_PROVIDER_ENABLED": "0",
            "SN_LOCAL_API_PROVIDER_TOKEN": "",
            "SN_MANAGED_PROXY_TOKEN": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {**env, "SN_DATA_DIR": tmp, "SN_INSIGHT_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/predictions", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertEqual(payload["predictions"], [])
        self.assertEqual(payload.get("status"), "blocked")
        self.assertFalse(payload.get("baseline_used"))
        self.assertFalse(payload.get("customer_prediction_generated"))
        self.assertTrue(payload.get("blocking_reasons"))
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('"sample": true', text)
        self.assertNotIn('"sample_mode": true', text)

    def test_clean_trade_points_for_degraded_low_quality_and_edge(self) -> None:
        payload = {
            "signal": "多头研究观察",
            "model_status": "degraded",
            "data_quality_score": 0.9,
            "trade_edge": 1.0,
            "entry": 1,
            "stop_loss": 1,
            "take_profit": 1,
        }
        cleaned = clean_trade_points(payload)
        self.assertIsNone(cleaned["entry"])
        self.assertIsNone(cleaned["stop_loss"])
        self.assertIsNone(cleaned["take_profit"])

        low_quality = {"signal": "多头研究观察", "data_quality_score": 0.1, "entry": 1}
        self.assertIsNone(clean_trade_points(low_quality)["entry"])

        no_edge = {"signal": "多头研究观察", "trade_edge": 0, "entry": 1}
        self.assertIsNone(clean_trade_points(no_edge)["entry"])

    def test_data_status_does_not_leak_key_values(self) -> None:
        with terminal_patches():
            status, payload = handle_terminal_api("/api/terminal/data-status", "GET", {}, None)
        self.assertEqual(status, 200)
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("REAL_ALPHA_KEY_SHOULD_NOT_APPEAR", text)
        self.assertNotIn("REAL_NEWS_KEY_SHOULD_NOT_APPEAR", text)

    def test_no_active_model_is_graceful(self) -> None:
        with patch("sn_futures.v2_api.get_models_health", return_value={"per_horizon": {}}):
            payload = build_terminal_model_health()
        self.assertEqual(payload["active_model"], "暂无可用 active 模型")

    def test_position_scenario_bad_json_returns_400(self) -> None:
        status, payload = handle_terminal_api("/api/terminal/position-scenario", "POST", {}, "{bad")
        self.assertEqual(status, 400)
        self.assertIn("请求体不是有效 JSON", payload["message"])

    def test_position_scenario_post_returns_observation_payload(self) -> None:
        with terminal_patches():
            status, payload = handle_terminal_api(
                "/api/terminal/position-scenario",
                "POST",
                {},
                '{"direction":"long","contracts":1,"entry_price":250000}',
            )
        self.assertEqual(status, 200)
        self.assertIn("仅供沪锡期货量化投研参考", payload["disclaimer"])
        safe_json_dumps(payload)


if __name__ == "__main__":
    unittest.main()

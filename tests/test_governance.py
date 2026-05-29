from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.governance import (
    ModelRegistry,
    apply_degradation_gate,
    build_learning_status,
    build_model_health,
    evaluate_promotion_gate,
    guard_degraded_prediction,
    make_model_record,
)


def passing_metrics() -> dict[str, object]:
    return {
        "metrics": {
            "sharpe": 1.25,
            "net_profit_after_cost": 120000.0,
            "max_drawdown": -0.09,
            "trade_count": 140,
            "high_conf_hit_rate": 0.62,
            "profit_factor": 1.42,
            "break_even_cost": 12000.0,
            "recent_window_not_degraded": True,
            "data_quality_score": 0.96,
            "calibration_error": 0.055,
            "no_leakage_check_passed": True,
            "directional_accuracy": 0.58,
            "return_mae": 0.003,
        }
    }


def failing_metrics() -> dict[str, object]:
    return {
        "metrics": {
            "sharpe": 0.1,
            "net_profit_after_cost": -1000.0,
            "max_drawdown": -0.28,
            "trade_count": 12,
            "high_conf_hit_rate": 0.42,
            "profit_factor": 0.82,
            "break_even_cost": 5.0,
            "recent_window_not_degraded": False,
            "data_quality_score": 0.71,
            "calibration_error": 0.30,
            "no_leakage_check_passed": False,
        }
    }


class GovernanceTests(unittest.TestCase):
    def test_candidate_cannot_promote_when_metrics_fail(self) -> None:
        decision = evaluate_promotion_gate(failing_metrics(), baseline_metrics={"high_conf_hit_rate": 0.50}, assumed_cost=10.0)
        self.assertFalse(decision.passed)
        self.assertEqual(decision.result, "candidate_failed_active_retained")
        self.assertIn("样本外夏普低于阈值", decision.failure_reasons)
        self.assertIn("成本后收益为负", decision.failure_reasons)

    def test_candidate_can_promote_when_metrics_pass(self) -> None:
        decision = evaluate_promotion_gate(passing_metrics(), baseline_metrics={"high_conf_hit_rate": 0.52}, assumed_cost=100.0)
        self.assertTrue(decision.passed)
        self.assertEqual(decision.result, "candidate_promoted")
        self.assertEqual(decision.failure_reasons, [])

    def test_registry_can_write_read_and_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            registry = ModelRegistry(path)
            record = make_model_record(model_id="m_candidate", horizon="h1d", metrics=passing_metrics()["metrics"], artifact_path="models/h1d/m_candidate.pkl")
            registry.register_candidate(record)
            loaded = ModelRegistry(path)
            self.assertEqual(len(loaded.list_candidates("h1d")), 1)
            loaded.promote_model("m_candidate", promotion_result={"passed": True})
            active = loaded.get_active_model("h1d")
            self.assertIsNotNone(active)
            self.assertEqual(active.model_id, "m_candidate")

    def test_degradation_changes_active_to_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp) / "registry.json")
            record = make_model_record(
                model_id="m_active",
                horizon="h1d",
                metrics=passing_metrics()["metrics"],
                status="active",
            )
            registry._records[record.model_id] = record
            registry.save_model_metadata()
            decision = apply_degradation_gate(
                registry,
                "m_active",
                {
                    "recent_30_expectancy": -20.0,
                    "recent_60d_high_conf_hit_rate": 0.43,
                    "calibration_error": 0.22,
                    "data_quality_score": 0.88,
                    "max_drawdown": -0.31,
                    "critical_provider_consecutive_failure": True,
                    "recent_walk_forward_failed": True,
                },
            )
            self.assertTrue(decision.degraded)
            self.assertGreater(len(decision.reasons), 0)
            reloaded = ModelRegistry(Path(tmp) / "registry.json")
            self.assertEqual(reloaded._records["m_active"].status, "degraded")
            self.assertIn("最近30笔期望收益为负", reloaded._records["m_active"].failure_reasons)

    def test_failure_reasons_are_chinese_and_non_empty(self) -> None:
        decision = evaluate_promotion_gate(failing_metrics(), baseline_metrics={"high_conf_hit_rate": 0.50}, assumed_cost=10.0)
        self.assertTrue(decision.failure_reasons)
        self.assertTrue(all(any("\u4e00" <= ch <= "\u9fff" for ch in reason) for reason in decision.failure_reasons))

    def test_promotion_gate_reads_real_backtest_result_fields(self) -> None:
        result = {
            "backtest": {
                "metrics": {
                    "sharpe": 1.1,
                    "net_profit_after_cost": 50000.0,
                    "max_drawdown": -0.08,
                    "trade_count": 100,
                    "high_conf_hit_rate": 0.61,
                    "profit_factor": 1.25,
                    "break_even_cost": 5000.0,
                    "recent_window_not_degraded": True,
                    "data_quality_score": 0.94,
                    "calibration_error": 0.08,
                    "no_leakage_check_passed": True,
                }
            }
        }
        decision = evaluate_promotion_gate(result, baseline_metrics={"high_conf_hit_rate": 0.50}, assumed_cost=100.0)
        self.assertTrue(decision.passed)
        self.assertEqual(decision.metrics_used["trade_count"], 100)

    def test_degraded_model_cannot_output_trade_points(self) -> None:
        record = make_model_record(model_id="m", horizon="h1d", metrics={}, status="degraded")
        record.failure_reasons = ["最近 walk-forward 验证失败"]
        guarded = guard_degraded_prediction(
            record,
            {
                "signal": "多头研究观察",
                "direction": "up",
                "price_center": 420000,
                "range_low": 410000,
                "range_high": 430000,
                "entry_price": 421000,
            },
        )
        self.assertEqual(guarded["signal"], "观望")
        self.assertEqual(guarded["direction"], "neutral")
        self.assertNotIn("entry_price", guarded)
        self.assertNotIn("price_center", guarded)

    def test_no_active_model_is_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp) / "registry.json")
            self.assertIsNone(registry.get_active_model("h1d"))
            status = build_learning_status(registry)
            self.assertEqual(status["message"], "暂无可用 active 模型")
            health = build_model_health(registry, horizons=["h1d"])
            self.assertEqual(health["horizons"][0]["degradation_gate_status"]["reasons"], ["暂无可用 active 模型"])


if __name__ == "__main__":
    unittest.main()

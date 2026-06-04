from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_v8_diagnostics_fixture(root: Path) -> Path:
    out = root / "outputs"
    write_json(
        out / "institutional_validation" / "institutional_validation_report_v8.json",
        {
            "status": "failed",
            "passed": False,
            "candidate_version": "v8",
            "dry_run": True,
            "promotion_eligibility": {
                "eligible": False,
                "checks": [
                    {"name": "Deflated Sharpe Ratio", "passed": True, "value": 3.0184, "threshold": "> 0.0", "failure_reason_zh": "DSR 未超过阈值"},
                    {"name": "PBO", "passed": False, "value": 0.6, "threshold": "< 0.2", "failure_reason_zh": "PBO 过高，存在过拟合风险"},
                    {"name": "Reality Check", "passed": False, "value": 0.0575, "threshold": "< 0.05", "failure_reason_zh": "Reality Check 未通过"},
                    {"name": "2x cost stress", "passed": True, "value": 0.0075, "threshold": ">= 0", "failure_reason_zh": "2x 成本压力下期望为负"},
                    {"name": "no single regime dominates", "passed": False, "value": 1.0, "threshold": "<= 0.7", "failure_reason_zh": "单一 regime 贡献过高"},
                ],
                "failure_reasons": ["PBO 过高，存在过拟合风险", "Reality Check 未通过", "单一 regime 贡献过高"],
            },
            "probability_of_backtest_overfitting": {"pbo": 0.6, "fold_count": 3, "strategy_count": 3, "overfit_splits": 2},
            "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 3.0184, "sample_count": 9},
            "reality_check": {"passed": False, "p_value": 0.0575, "observed_mean": 0.0077, "bootstrap_samples": 400, "sample_count": 9},
            "dominance_checks": {"single_fold_contribution": 0.44, "single_fold_dominates": False, "single_regime_contribution": 1.0, "single_regime_dominates": True},
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    write_json(
        out / "institutional_validation" / "stress_tests_v8.json",
        {
            "candidate_version": "v8",
            "cost_stress": {
                "2x_cost": {"expectancy": 0.0075, "max_drawdown": -0.002},
                "3x_cost": {"expectancy": 0.0073, "max_drawdown": -0.004},
            },
            "regime_stress": {
                "high_volatility": {"sample_count": 800, "fold_count": 6, "expectancy": 0.0192, "max_drawdown": 0.0},
                "low_volatility": {"sample_count": 700, "fold_count": 6, "expectancy": 0.0, "max_drawdown": 0.0},
                "range": {"sample_count": 350, "fold_count": 3, "expectancy": 0.0, "max_drawdown": 0.0},
            },
        },
    )
    write_json(
        out / "model_research" / "candidate_v8" / "candidate_v8_gated_research_report.json",
        {
            "status": "success",
            "candidate_version": "v8",
            "disabled_horizons": ["1d"],
            "no_trade_reasons": ["drawdown_proxy_high", "weak_direction_or_brier"],
            "v7_vs_v8": {
                "v7": {"PBO": 1.0, "DSR": 0.0, "Reality Check p-value": 1.0, "max_drawdown": -0.8, "turnover": 0.2, "trade_count": 1453},
                "v8": {"PBO": 0.6, "DSR": 3.0184, "Reality Check p-value": 0.0575, "max_drawdown": -0.017, "turnover": 0.0123, "trade_count": 87},
            },
            "stable_policy_application": {
                "metrics_by_horizon": {
                    "1d": {"trade_count": 0, "turnover": 0.0},
                    "10d": {"trade_count": 16, "turnover": 0.011},
                    "20d": {"trade_count": 71, "turnover": 0.051},
                }
            },
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    write_json(
        out / "model_research" / "candidate_v8" / "stable_strategy_policy_v8.json",
        {"disabled_horizons": ["1d"], "no_trade_reasons": ["drawdown_proxy_high", "weak_direction_or_brier"]},
    )
    for horizon, values in {
        "1d": [0.0, 0.0, 0.0],
        "10d": [0.04, -0.01, 0.03],
        "20d": [0.03, 0.02, -0.02],
    }.items():
        folds = []
        for idx, expectancy in enumerate(values, start=1):
            year = 2020 + idx
            folds.append(
                {
                    "fold": idx,
                    "validation_start": f"{year}-01-01T00:00:00",
                    "validation_end": f"{year}-12-31T00:00:00",
                    "validation_samples": 100,
                    "metrics": {
                        "directional_accuracy": 0.5 + max(expectancy, 0.0),
                        "cost_adjusted_expectancy": expectancy,
                        "trade_count": 10 if expectancy > 0 else 0,
                        "turnover": 0.01 if expectancy > 0 else 0.0,
                    },
                    "threshold_optimization": {
                        "by_coverage": {
                            "top_20pct": {
                                "expectancy_at_coverage": expectancy,
                                "accuracy_at_coverage": 0.5 + max(expectancy, 0.0),
                                "sample_count": 10 if expectancy > 0 else 0,
                            }
                        }
                    },
                }
            )
        write_json(
            out / "walk_forward" / "v8" / f"wf_{horizon}.json",
            {"candidate_version": "v8", "horizon": horizon, "status": "success", "folds": folds, "metrics": {"trade_count": sum(1 for v in values if v > 0) * 10}},
        )
        write_json(
            out / "research_backtests" / "v8" / f"metrics_{horizon}.json",
            {
                "horizon": horizon,
                "trade_count": sum(1 for v in values if v > 0) * 10,
                "turnover": sum(1 for v in values if v > 0) / 100,
                "cost_stress": {
                    "2x_cost": {"expectancy": max(values)},
                    "3x_cost": {"expectancy": max(values) - 0.0002},
                },
            },
        )
    return out

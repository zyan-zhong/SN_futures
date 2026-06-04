from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_blocked_candidate_fixture(root: str) -> Path:
    output = Path(root) / "outputs"
    write_json(
        output / "model_registry" / "promotion_report_v5.json",
        {
            "candidate_version": "v5",
            "status": "failed",
            "promotion_gate_passed": False,
            "blocking_reasons": [
                "PBO above threshold",
                "worst fold below threshold",
                "2x cost stress negative",
            ],
            "gate_results": [
                {"name": "PBO", "passed": False, "value": 0.61, "threshold": 0.2},
                {"name": "worst_fold_accuracy", "passed": False, "value": 0.48, "threshold": 0.52},
                {"name": "2x_cost_expectancy", "passed": False, "value": -0.002, "threshold": 0.0},
            ],
        },
    )
    write_json(
        output / "institutional_validation" / "institutional_validation_report_v5.json",
        {
            "candidate_version": "v5",
            "status": "failed",
            "metrics": {
                "pbo": 0.61,
                "deflated_sharpe_ratio": -0.18,
                "reality_check_pass": False,
                "worst_fold_accuracy": 0.48,
                "worst_year_accuracy": 0.49,
                "worst_regime_accuracy": 0.47,
                "cost_stress": {
                    "2x": {"expectancy": -0.002},
                    "3x": {"expectancy": -0.006},
                },
                "max_drawdown": 0.24,
                "turnover": 3.8,
            },
            "feature_stability": {"passed": False, "stability_score": 0.42},
        },
    )
    write_json(
        output / "feature_store" / "v5" / "feature_store_manifest.json",
        {
            "version": "v5",
            "group_coverage": {
                "raw_market": 0.95,
                "technical": 0.92,
                "basis": 0.0,
                "inventory": 0.0,
                "lme_tin": 0.0,
                "cross_market": 0.0,
                "event": 0.0,
            },
            "usable_fields": ["close", "volume", "rsi_14"],
            "excluded_fields": ["spot_futures_basis", "lme_tin_close", "event_shock_score"],
            "sample_data_used": False,
            "mock_data_used": False,
        },
    )
    write_json(
        output / "research_backtests" / "v5" / "metrics_1d.json",
        {
            "candidate_version": "v5",
            "research_only": True,
            "total_return": -0.012,
            "max_drawdown": 0.24,
            "sharpe": -0.3,
            "trade_count": 42,
            "cost_stress": {"2x": {"expectancy": -0.002}, "3x": {"expectancy": -0.006}},
        },
    )
    write_json(
        output / "oof_integrity" / "v5" / "oof_integrity_report.json",
        {
            "horizons": {
                "1d": {
                    "confidence_subset": {
                        "top_20": {
                            "sample_count": 80,
                            "coverage": 0.2,
                            "direction_accuracy": 0.56,
                            "worst_fold_accuracy": 0.48,
                        }
                    }
                }
            }
        },
    )
    write_json(
        output / "fundamentals" / "tushare_provider_status.json",
        {
            "provider": "tushare",
            "status": "token_missing",
            "configured": False,
            "last_success_time": None,
            "message_zh": "未配置 Tushare token，期货基础数据不可用。",
        },
    )
    write_json(
        output / "fundamentals" / "managed_proxy_status.json",
        {
            "provider": "managed_proxy",
            "status": "disabled",
            "enabled": False,
            "last_success_time": None,
            "message_zh": "托管数据服务未启用。",
        },
    )
    write_json(
        output / "fundamentals" / "fx_macro_provider_status.json",
        {
            "provider": "alpha_vantage",
            "status": "rate_limited",
            "configured": True,
            "last_success_time": "2026-05-30T09:00:00",
            "message_zh": "Alpha Vantage 当前限流，使用最近成功缓存。",
        },
    )
    write_json(
        output / "events" / "news_provider_status.json",
        {
            "provider": "newsapi",
            "status": "success",
            "configured": True,
            "last_success_time": "2026-05-30T09:05:00",
            "returned_count": 12,
        },
    )
    return output

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def coverage(groups: dict[str, float]) -> dict[str, object]:
    return {
        "sample_count": 120,
        "groups": [
            {"group": group, "coverage_rate": rate, "feature_count": 10, "available_feature_count": int(rate * 10)}
            for group, rate in groups.items()
        ],
        "usable_feature_cols": [],
    }


def write_feature_stability(output: Path, *, passed: bool = True) -> None:
    write_json(
        output / "model_registry" / "feature_stability_report_v5.json",
        {
            "candidate_version": "v5",
            "evidence_status": "success" if passed else "missing",
            "stability_score": 0.72 if passed else 0.0,
            "threshold": 0.55,
            "passed": passed,
            "stable_features": ["open_interest", "settlement"] if passed else [],
            "unstable_features": [] if passed else ["open_interest"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


def write_ready_v6_inputs(output: Path) -> None:
    feature_store = {
        "version": "v6",
        "status": "success",
        "generated_at": "2026-06-01T09:00:00",
        "row_count": 120,
        "usable_fields": ["open_interest", "settlement"],
        "tushare_used": True,
        "tushare_fields": ["open_interest", "settlement"],
        "leakage_check_pass": True,
        "no_lookahead_pass": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
    }
    feature_store_dir = output / "feature_store" / "v6"
    feature_store_dir.mkdir(parents=True, exist_ok=True)
    (feature_store_dir / "feature_store.csv").write_text(
        "trade_date,close,open_interest,settlement\n2026-05-29,210000,12000,210100\n",
        encoding="utf-8",
    )
    write_json(feature_store_dir / "feature_store_manifest.json", feature_store)
    write_json(
        output / "diagnostics" / "data_source_coverage_improvement.json",
        {
            "status": "success",
            "feature_coverage_delta": {
                "raw_market": {"before": 0.833333, "after": 1.0, "delta": 0.166667},
            },
            "feature_store_v6": feature_store,
        },
    )
    write_json(
        output / "diagnostics" / "real_data_coverage_validation.json",
        {
            "generated_at": "2026-06-01T09:00:00",
            "feature_coverage_before": coverage({"raw_market": 0.833333}),
            "feature_coverage_after": coverage({"raw_market": 1.0}),
            "feature_store_v5": feature_store,
            "feature_store_v6": feature_store,
        },
    )
    write_feature_stability(output, passed=True)


def write_blocked_v6_inputs(output: Path) -> None:
    feature_store = {
        "version": "v6",
        "status": "success",
        "usable_fields": [],
        "leakage_check_pass": True,
        "no_lookahead_pass": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
    }
    write_json(
        output / "diagnostics" / "data_source_coverage_improvement.json",
        {
            "status": "success",
            "feature_coverage_delta": {"raw_market": {"before": 0.833333, "after": 0.833333, "delta": 0.0}},
            "feature_store_v6": feature_store,
        },
    )
    write_json(
        output / "diagnostics" / "real_data_coverage_validation.json",
        {
            "feature_coverage_before": coverage({"raw_market": 0.833333}),
            "feature_coverage_after": coverage({"raw_market": 0.833333}),
            "feature_store_v5": feature_store,
            "feature_store_v6": feature_store,
        },
    )
    write_feature_stability(output, passed=True)


def successful_dataset() -> dict[str, Any]:
    return {
        "status": "success",
        "dataset_version": "v6",
        "feature_store_version": "v6",
        "feature_set": "institutional_tushare_enhanced",
        "leakage_check_pass": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
        "feature_cols": ["open_interest", "settlement"],
    }


def successful_candidate(output: Path) -> dict[str, Any]:
    return {
        "status": "success",
        "candidate_version": "v6",
        "dataset_version": "v6",
        "feature_set": "institutional_tushare_enhanced",
        "metrics_by_horizon": {"1d": {"directional_accuracy": 0.56, "fold_count": 3, "sample_count": 120}},
        "oof_trace_paths": {"1d": str(output / "walk_forward" / "v6" / "oof_trace_1d.csv")},
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
    }

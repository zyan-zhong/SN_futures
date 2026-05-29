from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.oof_integrity_service import build_oof_integrity_report


def _write_manifest(root: str, *, sample: bool = False, baseline: bool = False) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    (output / "training_dataset_manifest.json").write_text(
        json.dumps(
            {
                "sample_data_used": sample,
                "baseline_used": baseline,
                "leakage_check_pass": True,
                "feature_cols": ["close", "rsi_14"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_wf(root: str, horizon: str = "1d", folds: int = 5) -> None:
    wf_dir = Path(root) / "outputs" / "walk_forward"
    wf_dir.mkdir(parents=True, exist_ok=True)
    payload = {"horizon": horizon, "folds": []}
    for fold in range(folds):
        start = pd.Timestamp("2024-01-01") + pd.Timedelta(days=fold * 30)
        end = start + pd.Timedelta(days=29)
        payload["folds"].append(
            {
                "fold": fold,
                "train_start": "2023-01-01",
                "train_end": (start - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                "validation_start": start.strftime("%Y-%m-%d"),
                "validation_end": end.strftime("%Y-%m-%d"),
                "train_samples": 80,
                "validation_samples": 30,
                "purged_samples": 3,
                "embargo_samples": 1,
            }
        )
    (wf_dir / f"wf_{horizon}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_trace(
    root: str,
    horizon: str = "1d",
    *,
    rows_per_fold: int = 30,
    dominant_fold: bool = False,
    negative_expectancy: bool = False,
) -> None:
    wf_dir = Path(root) / "outputs" / "walk_forward"
    wf_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for fold in range(5):
        start = pd.Timestamp("2024-01-01") + pd.Timedelta(days=fold * 30)
        count = rows_per_fold * (5 if dominant_fold and fold == 0 else 1)
        for idx in range(count):
            ts = start + pd.Timedelta(days=idx % 30)
            confidence = 0.98 if (dominant_fold and fold == 0) or idx < max(3, rows_per_fold // 4) else 0.55
            realized_direction = 1 if idx % 3 else -1
            predicted_direction = realized_direction if idx % 5 else -realized_direction
            realized_return = (0.001 if predicted_direction == realized_direction else -0.0015)
            if negative_expectancy:
                realized_return = -0.001
            rows.append(
                {
                    "horizon": horizon,
                    "fold_id": fold,
                    "timestamp": ts.strftime("%Y-%m-%d"),
                    "label_start_time": ts.strftime("%Y-%m-%d"),
                    "label_end_time": (ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    "close": 210000 + idx,
                    "realized_direction": realized_direction,
                    "realized_return": realized_return,
                    "realized_vol": 0.02,
                    "raw_prob_up": 0.65,
                    "calibrated_prob_up": 0.62,
                    "predicted_direction": predicted_direction,
                    "expected_return": 0.0008,
                    "confidence": confidence,
                    "trade_edge": 0.0004,
                    "selected_signal": "research",
                    "no_trade_reason": "",
                    "regime_label": "TREND_UP" if fold < 4 else "RANGE",
                    "regime_volatility_score": 0.2,
                    "regime_trend_score": 0.7,
                    "data_quality_score": 0.85,
                    "feature_coverage_score": 0.8,
                    "model_family": "HistGradientBoosting",
                    "model_id": f"m_{fold}",
                    "calibration_method": "sigmoid",
                    "cost_assumption": 0.0001,
                    "sample_weight": 1.0,
                    "is_high_confidence_top_10": confidence >= 0.98,
                    "is_high_confidence_top_20": confidence >= 0.90,
                    "error_type": "",
                    "drawdown_contribution": min(0.0, realized_return),
                }
            )
    pd.DataFrame(rows).to_csv(wf_dir / f"oof_trace_{horizon}.csv", index=False)


def test_oof_integrity_report_runs_and_contains_preview_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp)

        report = build_oof_integrity_report()
        horizon = report["horizons"]["1d"]

        assert horizon["trace_rows"] > 0
        assert horizon["fold_count"] == 5
        assert "top_10pct" in horizon["confidence_subset"]
        assert "dsr_preview" in horizon["preview"]
        assert "pbo_preview" in horizon["preview"]
        assert "reality_check_preview" in horizon["preview"]
        assert report["active_updated"] is False
        assert report["customer_prediction_generated"] is False
        assert not (Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists()


def test_oof_integrity_blocks_sample_or_baseline_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp, sample=True, baseline=True)
        _write_wf(tmp)
        _write_trace(tmp)

        report = build_oof_integrity_report()
        reasons = " ".join(report["horizons"]["1d"]["blocking_reasons"])

        assert "sample_data_used" in reasons
        assert "baseline_used" in reasons

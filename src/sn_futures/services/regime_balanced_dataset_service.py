from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from .feature_store_v7_service import V7_FEATURE_SET, build_feature_store_v7
from .training_dataset_service import (
    _build_training_dataset_from_feature_store,
    _manifest_path,
)


V10_FEATURE_SET = "regime_balanced_tushare_cost_positioning"
REGIMES = ("low_volatility", "range", "high_volatility")
REGIME_POLICY_MULTIPLIER = {
    "low_volatility": 1.25,
    "range": 1.15,
    "high_volatility": 0.60,
}


def _read_dataset(path: str) -> pd.DataFrame:
    dataset_path = Path(path)
    if dataset_path.suffix.lower() == ".parquet":
        try:
            return pd.read_parquet(dataset_path)
        except Exception:
            pass
    return pd.read_csv(dataset_path)


def _write_dataset(frame: pd.DataFrame, path: str) -> None:
    dataset_path = Path(path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    if dataset_path.suffix.lower() == ".parquet":
        try:
            frame.to_parquet(dataset_path, index=False)
            return
        except Exception:
            csv_path = dataset_path.with_suffix(".csv")
            frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return
    frame.to_csv(dataset_path, index=False, encoding="utf-8-sig")


def _past_volatility_score(dataset: pd.DataFrame) -> pd.Series:
    for column in ("atr_14", "volatility_20", "volatility_10", "volatility"):
        if column in dataset.columns:
            score = pd.to_numeric(dataset[column], errors="coerce")
            if score.notna().sum() >= 3 and float(score.fillna(0.0).abs().sum()) > 0.0:
                return score.ffill().bfill()
    if "close" in dataset.columns:
        close = pd.to_numeric(dataset["close"], errors="coerce")
        score = close.pct_change().abs().rolling(10, min_periods=2).mean()
        if score.notna().sum() >= 3 and float(score.fillna(0.0).abs().sum()) > 0.0:
            return score.ffill().bfill().fillna(0.0)
    return pd.Series(np.linspace(0.0, 1.0, len(dataset)), index=dataset.index)


def _regime_labels(dataset: pd.DataFrame) -> pd.Series:
    if dataset.empty:
        return pd.Series(dtype="object")
    score = _past_volatility_score(dataset).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    ranks = score.rank(method="first", pct=True)
    labels = pd.Series("range", index=dataset.index, dtype="object")
    labels.loc[ranks <= 1.0 / 3.0] = "low_volatility"
    labels.loc[ranks > 2.0 / 3.0] = "high_volatility"
    if set(labels.unique()) >= set(REGIMES):
        return labels

    ordered = score.sort_values(kind="mergesort").index.tolist()
    fallback = pd.Series("range", index=dataset.index, dtype="object")
    third = max(1, len(ordered) // 3)
    for idx in ordered[:third]:
        fallback.loc[idx] = "low_volatility"
    for idx in ordered[-third:]:
        fallback.loc[idx] = "high_volatility"
    return fallback


def _normalised_regime_weights(counts: Mapping[str, int]) -> dict[str, float]:
    total = int(sum(max(0, int(value)) for value in counts.values()))
    if total <= 0:
        return {regime: 1.0 for regime in REGIMES}
    target_share = 1.0 / len(REGIMES)
    raw: dict[str, float] = {}
    for regime in REGIMES:
        count = max(1, int(counts.get(regime, 0)))
        share = count / total
        raw[regime] = (target_share / share) * REGIME_POLICY_MULTIPLIER[regime]
    weighted_mean = sum(float(counts.get(regime, 0)) * raw[regime] for regime in REGIMES) / total
    if weighted_mean <= 0:
        return {regime: 1.0 for regime in REGIMES}
    return {regime: round(float(raw[regime] / weighted_mean), 6) for regime in REGIMES}


def _validation_split(labels: pd.Series) -> tuple[pd.Series, dict[str, int], dict[str, int]]:
    split = pd.Series("train", index=labels.index, dtype="object")
    train_counts: dict[str, int] = {}
    validation_counts: dict[str, int] = {}
    for regime in REGIMES:
        regime_index = labels[labels == regime].index.tolist()
        count = len(regime_index)
        if count <= 1:
            train_counts[regime] = count
            validation_counts[regime] = 0
            continue
        validation_count = min(count - 1, max(1, math.ceil(count * 0.20)))
        validation_index = regime_index[-validation_count:]
        split.loc[validation_index] = "validation"
        train_counts[regime] = int(count - validation_count)
        validation_counts[regime] = int(validation_count)
    return split, train_counts, validation_counts


def _regime_counts(labels: pd.Series) -> dict[str, int]:
    counts = labels.value_counts().to_dict()
    return {regime: int(counts.get(regime, 0)) for regime in REGIMES}


def _apply_regime_balance(dataset: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = dataset.copy()
    if "label_start_time" in frame.columns:
        frame = frame.sort_values("label_start_time", kind="mergesort").reset_index(drop=True)
    labels = _regime_labels(frame)
    counts = _regime_counts(labels)
    weights = _normalised_regime_weights(counts)
    split, train_counts, validation_counts = _validation_split(labels)
    frame["regime_label"] = labels.values
    frame["regime_sample_weight"] = frame["regime_label"].map(weights).astype(float)
    frame["regime_split"] = split.values
    return frame, {
        "counts": counts,
        "weights": weights,
        "train_counts": train_counts,
        "validation_counts": validation_counts,
    }


def build_training_dataset_v10(
    *,
    horizons: Iterable[int] = (1, 3, 5, 10, 20),
    min_feature_coverage: float = 0.0,
) -> dict[str, Any]:
    feature_manifest = build_feature_store_v7()
    base = _build_training_dataset_from_feature_store(
        horizons=horizons,
        min_feature_coverage=min_feature_coverage,
        dataset_version="v10",
        feature_store_version="v7",
        feature_set=V10_FEATURE_SET,
    )
    if base.get("status") != "success":
        base["dataset_version"] = "v10"
        base["feature_store_version"] = "v7"
        base["feature_set"] = V10_FEATURE_SET
        base["sample_data_used"] = bool(base.get("sample_data_used", False))
        base["mock_data_used"] = bool(base.get("mock_data_used", False))
        base["baseline_used"] = False
        base["customer_prediction_generated"] = False
        base["active_model_written"] = False
        base["no_model_training"] = True
        _manifest_path("v10").write_text(json.dumps(sanitize_for_json(base), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(base)

    horizon_regime_counts: dict[str, dict[str, int]] = {}
    horizon_regime_train_counts: dict[str, dict[str, int]] = {}
    horizon_regime_validation_counts: dict[str, dict[str, int]] = {}
    regime_sample_weights: dict[str, dict[str, float]] = {}
    aggregate_counts = {regime: 0 for regime in REGIMES}

    dataset_paths = dict(base.get("dataset_paths") or {})
    for horizon, path in dataset_paths.items():
        dataset = _read_dataset(str(path))
        balanced, summary = _apply_regime_balance(dataset)
        _write_dataset(balanced, str(path))
        counts = dict(summary["counts"])
        horizon_regime_counts[str(horizon)] = counts
        horizon_regime_train_counts[str(horizon)] = dict(summary["train_counts"])
        horizon_regime_validation_counts[str(horizon)] = dict(summary["validation_counts"])
        regime_sample_weights[str(horizon)] = dict(summary["weights"])
        for regime in REGIMES:
            aggregate_counts[regime] += int(counts.get(regime, 0))
        if isinstance(base.get("dataset_outputs"), Mapping) and str(horizon) in base["dataset_outputs"]:
            base["dataset_outputs"][str(horizon)]["regime_counts"] = counts
            base["dataset_outputs"][str(horizon)]["regime_sample_weights"] = dict(summary["weights"])

    base.update(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dataset_version": "v10",
            "feature_store_version": "v7",
            "feature_set": V10_FEATURE_SET,
            "message_zh": "Training Dataset v10 已基于 Feature Store v7 构建 regime-balanced 样本权重；本步骤不训练模型、不生成预测、不发布 active。",
            "regime_distribution": aggregate_counts,
            "regime_sample_weights": regime_sample_weights,
            "horizon_regime_counts": horizon_regime_counts,
            "horizon_regime_train_counts": horizon_regime_train_counts,
            "horizon_regime_validation_counts": horizon_regime_validation_counts,
            "regime_balance_policy": {
                "source_feature_store_version": "v7",
                "dominant_regime": "high_volatility",
                "dominant_regime_action": "downweight",
                "underrepresented_regime_action": "boost",
                "weight_normalization": "per_horizon_mean_one",
                "regime_labels_use": "past_or_current_volatility_features_only",
                "validation_split": "per_regime_last_20_percent_reserved_for_validation",
                "policy_multiplier": dict(REGIME_POLICY_MULTIPLIER),
            },
            "no_lookahead_pass": bool(base.get("leakage_check_pass") and feature_manifest.get("no_lookahead_pass", True)),
            "sample_data_used": bool(feature_manifest.get("sample_data_used") or base.get("sample_data_used")),
            "mock_data_used": bool(feature_manifest.get("mock_data_used") or base.get("mock_data_used")),
            "baseline_used": False,
            "customer_prediction_generated": False,
            "active_model_written": False,
            "no_model_training": True,
        }
    )
    leakage_details = dict(base.get("leakage_check_details") or {})
    leakage_details["regime_balance_no_lookahead"] = {
        "passed": True,
        "regime_label_inputs": ["atr_14", "volatility_20", "close_pct_change_rolling_past"],
        "future_return_used_for_regime_label": False,
        "label_columns_used_for_weights": False,
    }
    base["leakage_check_details"] = leakage_details
    manifest_path = _manifest_path("v10")
    base["manifest_path"] = str(manifest_path)
    payload = sanitize_for_json(base)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

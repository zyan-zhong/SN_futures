from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..labels.leakage_guard import check_feature_label_leakage
from .baselines import BaselineModelBundle, train_baseline_models
from .calibration import ProbabilityCalibrator, fit_probability_calibrator
from .regime_models import RegimeEnsembleBundle, fit_regime_ensemble, predict_regime_ensemble


@dataclass
class HorizonModelBundle:
    horizon: str
    feature_cols: list[str]
    feature_set_version: str
    baseline: BaselineModelBundle
    regime_ensemble: RegimeEnsembleBundle
    calibrator: ProbabilityCalibrator
    metrics: dict[str, float]


def _feature_set_version(feature_cols: list[str], horizon: str) -> str:
    raw = horizon + "|" + "|".join(feature_cols)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _time_split(frame: pd.DataFrame, validation_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        raise ValueError("Cannot train on an empty frame.")
    work = frame.sort_index().copy()
    split = max(1, min(len(work) - 1, int(len(work) * (1.0 - validation_fraction))))
    return work.iloc[:split].copy(), work.iloc[split:].copy()


def train_horizon_models(
    frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    horizon: str,
    direction_col: str,
    return_col: str,
    regime_col: str = "regime_label",
    validation_fraction: float = 0.25,
    random_state: int = 42,
) -> HorizonModelBundle:
    leakage = check_feature_label_leakage(feature_cols)
    if not leakage["ok"]:
        raise ValueError(leakage["message"] + " " + ", ".join(leakage["leaked_columns"]))

    required = list(feature_cols) + [direction_col, return_col]
    work = frame.dropna(subset=required).copy()
    if len(work) < 10:
        raise ValueError("Insufficient rows to train horizon models.")
    train, validation = _time_split(work, validation_fraction)
    feature_version = _feature_set_version(feature_cols, horizon)

    baseline = train_baseline_models(
        train,
        feature_cols,
        horizon=horizon,
        direction_col=direction_col,
        return_col=return_col,
        random_state=random_state,
    )
    regime_ensemble = fit_regime_ensemble(
        train,
        validation,
        feature_cols,
        horizon=horizon,
        direction_col=direction_col,
        return_col=return_col,
        feature_set_version=feature_version,
        regime_col=regime_col,
        random_state=random_state,
    )

    raw_probs: list[float] = []
    actual: list[int] = []
    pred_returns: list[float] = []
    for _, row in validation.iterrows():
        pred = predict_regime_ensemble(regime_ensemble, row)
        raw_probs.append(float(pred["ensemble_prediction"]["prob_up"]))
        pred_returns.append(float(pred["ensemble_prediction"]["expected_return"]))
        actual.append(1 if float(row[direction_col]) > 0 else 0)
    calibrator = fit_probability_calibrator(raw_probs, actual, method="sigmoid")
    calibrated = calibrator.transform(raw_probs)
    pred_dir = (calibrated >= 0.5).astype(int)
    y_ret = pd.to_numeric(validation[return_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    pred_ret = np.asarray(pred_returns, dtype=float)
    metrics = {
        "directional_accuracy": float((pred_dir == np.asarray(actual)).mean()) if actual else 0.0,
        "brier_score": float(calibrator.brier_score) if np.isfinite(calibrator.brier_score) else 0.0,
        "calibration_error": float(calibrator.calibration_error) if np.isfinite(calibrator.calibration_error) else 0.0,
        "return_mae": float(np.mean(np.abs(pred_ret - y_ret))) if len(y_ret) else 0.0,
        "return_rmse": float(np.sqrt(np.mean((pred_ret - y_ret) ** 2))) if len(y_ret) else 0.0,
        "validation_sample_count": float(len(validation)),
    }
    return HorizonModelBundle(
        horizon=horizon,
        feature_cols=list(feature_cols),
        feature_set_version=feature_version,
        baseline=baseline,
        regime_ensemble=regime_ensemble,
        calibrator=calibrator,
        metrics=metrics,
    )


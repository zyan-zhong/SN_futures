from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


def _clip_prob(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    arr[~np.isfinite(arr)] = 0.5
    return np.clip(arr, 1e-5, 1.0 - 1e-5)


def brier_score(y_true, prob) -> float:
    y = np.asarray(y_true, dtype=float).reshape(-1)
    p = _clip_prob(prob)
    if len(y) == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(y_true, prob, *, bins: int = 10) -> float:
    y = np.asarray(y_true, dtype=float).reshape(-1)
    p = _clip_prob(prob)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (p >= left) & (p < right if right < 1.0 else p <= right)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


@dataclass
class ProbabilityCalibrator:
    method: str
    model: Any | None
    brier_score: float
    calibration_error: float

    def transform(self, raw_prob) -> np.ndarray:
        p = _clip_prob(raw_prob)
        if self.model is None:
            return p
        if self.method == "isotonic":
            return np.clip(self.model.predict(p), 0.0, 1.0)
        if self.method == "sigmoid":
            logits = np.log(p / (1.0 - p)).reshape(-1, 1)
            return np.clip(self.model.predict_proba(logits)[:, 1], 0.0, 1.0)
        return p

    def transform_one(self, raw_prob: float) -> float:
        return float(self.transform([raw_prob])[0])


def fit_probability_calibrator(
    raw_prob,
    y_true,
    *,
    method: str = "sigmoid",
    min_samples: int = 12,
) -> ProbabilityCalibrator:
    p = _clip_prob(raw_prob)
    y = np.asarray(y_true, dtype=int).reshape(-1)
    valid = np.isfinite(p) & np.isfinite(y)
    p = p[valid]
    y = y[valid]
    if len(y) < min_samples or len(np.unique(y)) < 2:
        return ProbabilityCalibrator(
            method="identity_insufficient_samples",
            model=None,
            brier_score=brier_score(y, p) if len(y) else float("nan"),
            calibration_error=expected_calibration_error(y, p) if len(y) else float("nan"),
        )

    if method == "isotonic":
        from sklearn.isotonic import IsotonicRegression

        model = IsotonicRegression(out_of_bounds="clip")
        model.fit(p, y)
        calibrated = model.predict(p)
        actual_method = "isotonic"
    else:
        from sklearn.linear_model import LogisticRegression

        logits = np.log(p / (1.0 - p)).reshape(-1, 1)
        model = LogisticRegression(max_iter=500)
        model.fit(logits, y)
        calibrated = model.predict_proba(logits)[:, 1]
        actual_method = "sigmoid"

    return ProbabilityCalibrator(
        method=actual_method,
        model=model,
        brier_score=brier_score(y, calibrated),
        calibration_error=expected_calibration_error(y, calibrated),
    )


def calibration_output(raw_prob: float, y_true=None, calibrator: ProbabilityCalibrator | None = None) -> dict[str, float | str]:
    calibrated = calibrator.transform_one(raw_prob) if calibrator is not None else float(_clip_prob([raw_prob])[0])
    return {
        "raw_prob_up": float(_clip_prob([raw_prob])[0]),
        "calibrated_prob_up": float(calibrated),
        "calibration_method": calibrator.method if calibrator is not None else "identity",
        "brier_score": float(calibrator.brier_score) if calibrator is not None else float("nan"),
        "calibration_error": float(calibrator.calibration_error) if calibrator is not None else float("nan"),
    }


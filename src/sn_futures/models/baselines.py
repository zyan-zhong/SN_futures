from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def _sklearn():
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return DummyClassifier, DummyRegressor, ElasticNet, LogisticRegression, Ridge, make_pipeline, StandardScaler


@dataclass
class BaselineModelBundle:
    horizon: str
    feature_cols: list[str]
    direction_model: Any
    return_model: Any
    dummy_classifier: Any
    dummy_regressor: Any
    metrics: dict[str, float]


def _clean_xy(frame: pd.DataFrame, feature_cols: list[str], target_col: str) -> tuple[pd.DataFrame, pd.Series]:
    required = feature_cols + [target_col]
    clean = frame.dropna(subset=required).copy()
    return clean[feature_cols], clean[target_col]


def _binary_direction(series: pd.Series) -> pd.Series:
    return (pd.to_numeric(series, errors="coerce") > 0).astype(int)


def train_baseline_models(
    frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    horizon: str,
    direction_col: str,
    return_col: str,
    random_state: int = 42,
) -> BaselineModelBundle:
    """Train lightweight direction and return baselines for a single horizon."""

    DummyClassifier, DummyRegressor, ElasticNet, LogisticRegression, Ridge, make_pipeline, StandardScaler = _sklearn()
    x_dir, y_dir_raw = _clean_xy(frame, feature_cols, direction_col)
    x_ret, y_ret = _clean_xy(frame, feature_cols, return_col)
    if x_dir.empty or x_ret.empty:
        raise ValueError("Insufficient rows to train baseline models.")

    y_dir = _binary_direction(y_dir_raw)
    if y_dir.nunique() >= 2:
        direction_model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=500, class_weight="balanced", random_state=random_state),
        )
    else:
        direction_model = DummyClassifier(strategy="most_frequent")
    direction_model.fit(x_dir, y_dir)

    if len(x_ret) >= 8 and float(pd.to_numeric(y_ret, errors="coerce").std() or 0.0) > 1e-12:
        return_model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    else:
        return_model = DummyRegressor(strategy="mean")
    return_model.fit(x_ret, pd.to_numeric(y_ret, errors="coerce").fillna(0.0))

    dummy_classifier = DummyClassifier(strategy="most_frequent")
    dummy_classifier.fit(x_dir, y_dir)
    dummy_regressor = DummyRegressor(strategy="mean")
    dummy_regressor.fit(x_ret, pd.to_numeric(y_ret, errors="coerce").fillna(0.0))

    pred_dir = direction_model.predict(x_dir)
    pred_ret = return_model.predict(x_ret)
    y_ret_arr = pd.to_numeric(y_ret, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    metrics = {
        "directional_accuracy": float((pred_dir == y_dir.to_numpy()).mean()),
        "return_mae": float(np.mean(np.abs(pred_ret - y_ret_arr))),
        "return_rmse": float(np.sqrt(np.mean((pred_ret - y_ret_arr) ** 2))),
        "sample_count": float(len(frame)),
    }
    return BaselineModelBundle(
        horizon=horizon,
        feature_cols=list(feature_cols),
        direction_model=direction_model,
        return_model=return_model,
        dummy_classifier=dummy_classifier,
        dummy_regressor=dummy_regressor,
        metrics=metrics,
    )


def predict_baseline(bundle: BaselineModelBundle, rows: pd.DataFrame) -> dict[str, np.ndarray]:
    x = rows[bundle.feature_cols]
    proba = bundle.direction_model.predict_proba(x)[:, 1] if hasattr(bundle.direction_model, "predict_proba") else bundle.direction_model.predict(x)
    return {
        "prob_up": np.asarray(proba, dtype=float),
        "expected_return": np.asarray(bundle.return_model.predict(x), dtype=float),
    }


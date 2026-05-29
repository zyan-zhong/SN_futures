from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class TreeModelBundle:
    model_id: str
    horizon: str
    feature_set_version: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    feature_cols: list[str]
    direction_model: Any
    return_model: Any
    backend: str
    feature_importance: list[dict[str, float | str]]
    metrics: dict[str, float]


def _binary_direction(values: pd.Series) -> pd.Series:
    return (pd.to_numeric(values, errors="coerce") > 0).astype(int)


def _backend_models(random_state: int = 42):
    try:
        lgb = importlib.import_module("lightgbm")
        return (
            "lightgbm",
            lgb.LGBMClassifier(n_estimators=120, learning_rate=0.04, max_depth=3, random_state=random_state, verbose=-1),
            lgb.LGBMRegressor(n_estimators=140, learning_rate=0.04, max_depth=3, random_state=random_state, verbose=-1),
        )
    except Exception:
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

        return (
            "sklearn_hist_gradient",
            HistGradientBoostingClassifier(max_iter=120, learning_rate=0.04, max_leaf_nodes=15, random_state=random_state),
            HistGradientBoostingRegressor(max_iter=140, learning_rate=0.04, max_leaf_nodes=15, random_state=random_state),
        )


def _feature_importance(model: Any, feature_cols: list[str]) -> list[dict[str, float | str]]:
    values = getattr(model, "feature_importances_", None)
    if values is None:
        return [{"feature": col, "importance": 0.0} for col in feature_cols]
    arr = np.asarray(values, dtype=float)
    total = float(np.abs(arr).sum())
    if total <= 0:
        return [{"feature": col, "importance": 0.0} for col in feature_cols]
    return [
        {"feature": col, "importance": float(abs(val) / total)}
        for col, val in sorted(zip(feature_cols, arr), key=lambda item: abs(float(item[1])), reverse=True)
    ]


def _date_bounds(frame: pd.DataFrame) -> tuple[str, str]:
    if frame.empty:
        return "", ""
    idx = pd.to_datetime(frame.index, errors="coerce")
    if idx.notna().any():
        return str(idx.min()), str(idx.max())
    return str(frame.index[0]), str(frame.index[-1])


def train_tree_model_bundle(
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    horizon: str,
    direction_col: str,
    return_col: str,
    feature_set_version: str,
    random_state: int = 42,
) -> TreeModelBundle:
    required = feature_cols + [direction_col, return_col]
    train = train_frame.dropna(subset=required).copy()
    validation = validation_frame.dropna(subset=required).copy()
    if train.empty:
        raise ValueError("Insufficient training rows for tree model.")
    if validation.empty:
        validation = train.tail(max(1, min(20, len(train)))).copy()

    backend, direction_model, return_model = _backend_models(random_state=random_state)
    x_train = train[feature_cols]
    y_dir = _binary_direction(train[direction_col])
    y_ret = pd.to_numeric(train[return_col], errors="coerce").fillna(0.0)
    if y_dir.nunique() < 2:
        from sklearn.dummy import DummyClassifier

        direction_model = DummyClassifier(strategy="most_frequent")
    direction_model.fit(x_train, y_dir)
    return_model.fit(x_train, y_ret)

    x_val = validation[feature_cols]
    y_val_dir = _binary_direction(validation[direction_col]).to_numpy()
    y_val_ret = pd.to_numeric(validation[return_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    pred_dir = direction_model.predict(x_val)
    pred_ret = np.asarray(return_model.predict(x_val), dtype=float)
    metrics = {
        "directional_accuracy": float((pred_dir == y_val_dir).mean()),
        "return_mae": float(np.mean(np.abs(pred_ret - y_val_ret))),
        "return_rmse": float(np.sqrt(np.mean((pred_ret - y_val_ret) ** 2))),
        "validation_sample_count": float(len(validation)),
    }
    train_start, train_end = _date_bounds(train)
    validation_start, validation_end = _date_bounds(validation)
    seed = f"{horizon}|{feature_set_version}|{train_start}|{train_end}|{validation_start}|{validation_end}|{backend}"
    model_id = "tree_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14]
    return TreeModelBundle(
        model_id=model_id,
        horizon=horizon,
        feature_set_version=feature_set_version,
        train_start=train_start,
        train_end=train_end,
        validation_start=validation_start,
        validation_end=validation_end,
        feature_cols=list(feature_cols),
        direction_model=direction_model,
        return_model=return_model,
        backend=backend,
        feature_importance=_feature_importance(direction_model, feature_cols),
        metrics=metrics,
    )


def predict_tree_bundle(bundle: TreeModelBundle, rows: pd.DataFrame) -> dict[str, np.ndarray]:
    x = rows[bundle.feature_cols]
    if hasattr(bundle.direction_model, "predict_proba"):
        prob = bundle.direction_model.predict_proba(x)
        prob_up = prob[:, 1] if prob.shape[1] > 1 else prob[:, 0]
    else:
        prob_up = bundle.direction_model.predict(x)
    return {
        "prob_up": np.asarray(prob_up, dtype=float),
        "expected_return": np.asarray(bundle.return_model.predict(x), dtype=float),
    }


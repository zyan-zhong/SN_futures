from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .tree_models import TreeModelBundle, predict_tree_bundle, train_tree_model_bundle


@dataclass
class RegimeEnsembleBundle:
    horizon: str
    regime_col: str
    min_regime_samples: int
    global_model: TreeModelBundle
    regime_models: dict[str, TreeModelBundle]


def fit_regime_ensemble(
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    horizon: str,
    direction_col: str,
    return_col: str,
    feature_set_version: str,
    regime_col: str = "regime_label",
    min_regime_samples: int = 40,
    random_state: int = 42,
) -> RegimeEnsembleBundle:
    global_model = train_tree_model_bundle(
        train_frame,
        validation_frame,
        feature_cols,
        horizon=horizon,
        direction_col=direction_col,
        return_col=return_col,
        feature_set_version=feature_set_version,
        random_state=random_state,
    )
    regime_models: dict[str, TreeModelBundle] = {}
    if regime_col in train_frame.columns:
        for regime, subset in train_frame.groupby(regime_col):
            if len(subset) < min_regime_samples:
                continue
            val_subset = validation_frame[validation_frame.get(regime_col) == regime] if regime_col in validation_frame.columns else validation_frame
            if val_subset.empty:
                val_subset = validation_frame
            regime_models[str(regime)] = train_tree_model_bundle(
                subset,
                val_subset,
                feature_cols,
                horizon=horizon,
                direction_col=direction_col,
                return_col=return_col,
                feature_set_version=f"{feature_set_version}_{regime}",
                random_state=random_state,
            )
    return RegimeEnsembleBundle(
        horizon=horizon,
        regime_col=regime_col,
        min_regime_samples=min_regime_samples,
        global_model=global_model,
        regime_models=regime_models,
    )


def predict_regime_ensemble(bundle: RegimeEnsembleBundle, row: pd.Series | pd.DataFrame) -> dict[str, Any]:
    frame = row.to_frame().T if isinstance(row, pd.Series) else row.copy()
    global_pred = predict_tree_bundle(bundle.global_model, frame)
    regime_value = str(frame.iloc[0].get(bundle.regime_col, ""))
    fallback_reason = ""
    regime_used = regime_value
    if regime_value and regime_value in bundle.regime_models:
        regime_model = bundle.regime_models[regime_value]
        regime_pred = predict_tree_bundle(regime_model, frame)
    else:
        regime_model = bundle.global_model
        regime_pred = global_pred
        regime_used = "global"
        fallback_reason = "该 regime 样本不足或缺失，已回退全局模型。"

    global_prob = float(global_pred["prob_up"][0])
    regime_prob = float(regime_pred["prob_up"][0])
    global_ret = float(global_pred["expected_return"][0])
    regime_ret = float(regime_pred["expected_return"][0])
    return {
        "global_prediction": {"prob_up": global_prob, "expected_return": global_ret},
        "regime_prediction": {"prob_up": regime_prob, "expected_return": regime_ret},
        "ensemble_prediction": {
            "prob_up": float(np.clip(0.45 * global_prob + 0.55 * regime_prob, 0.0, 1.0)),
            "expected_return": float(0.45 * global_ret + 0.55 * regime_ret),
        },
        "regime_used": regime_used,
        "fallback_reason": fallback_reason,
        "model_id": regime_model.model_id,
    }


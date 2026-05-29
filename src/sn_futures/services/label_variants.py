from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json


DEFAULT_COST = 0.0002


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _distribution(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts(dropna=False).to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def _noise_threshold(returns: pd.Series, cost: float, quantile: float = 0.25) -> float:
    abs_returns = returns.abs().dropna()
    if abs_returns.empty:
        return float(cost)
    threshold = float(abs_returns.quantile(float(quantile)))
    if not np.isfinite(threshold):
        threshold = 0.0
    return float(max(cost, threshold))


def add_label_variants(
    frame: pd.DataFrame,
    *,
    return_col: str = "y_return",
    direction_col: str = "y_direction",
    cost: float = DEFAULT_COST,
    noise_quantile: float = 0.25,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Add research-only label variants without changing customer predictions."""

    out = frame.copy()
    returns = _safe_numeric(out.get(return_col, pd.Series(index=out.index, dtype=float))).fillna(0.0)
    raw_direction = _safe_numeric(out.get(direction_col, pd.Series(index=out.index, dtype=float))).fillna(0).astype(int)
    threshold = _noise_threshold(returns, cost=float(cost), quantile=float(noise_quantile))

    thresholded = pd.Series(0, index=out.index, dtype=int)
    thresholded.loc[returns > threshold] = 1
    thresholded.loc[returns < -threshold] = -1

    volatility = returns.rolling(20, min_periods=5).std()
    fallback_vol = float(returns.std()) if float(returns.std() or 0.0) > 1e-12 else 1.0
    volatility = volatility.replace([np.inf, -np.inf], np.nan).fillna(fallback_vol)
    volatility = volatility.where(volatility.abs() > 1e-12, fallback_vol)

    high_conf_meta = (thresholded != 0).astype(int)
    if "tb_label" in out.columns:
        triple_barrier = _safe_numeric(out["tb_label"]).fillna(0).astype(int)
    else:
        tb_cols = [col for col in out.columns if str(col).startswith("tb_label_")]
        triple_barrier = _safe_numeric(out[tb_cols[0]]).fillna(0).astype(int) if tb_cols else pd.Series(0, index=out.index, dtype=int)

    out["direction_raw"] = raw_direction
    out["direction_thresholded"] = thresholded
    out["triple_barrier_atr"] = triple_barrier
    out["volatility_adjusted_return"] = returns / volatility
    out["high_confidence_meta_label"] = high_conf_meta

    report = {
        "label_variants": [
            "direction_raw",
            "direction_thresholded",
            "triple_barrier_atr",
            "volatility_adjusted_return",
            "high_confidence_meta_label",
        ],
        "cost": float(cost),
        "noise_quantile": float(noise_quantile),
        "noise_threshold": float(threshold),
        "sample_count": int(len(out)),
        "label_distribution": {
            "direction_raw": _distribution(out["direction_raw"]),
            "direction_thresholded": _distribution(out["direction_thresholded"]),
            "triple_barrier_atr": _distribution(out["triple_barrier_atr"]),
            "high_confidence_meta_label": _distribution(out["high_confidence_meta_label"]),
        },
        "message_zh": "已生成研究标签变体；no-trade 样本不会被强行分类。",
    }
    return out, sanitize_for_json(report)


def summarize_label_variants(frame: pd.DataFrame, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    _, report = add_label_variants(
        frame,
        cost=float(cfg.get("cost", DEFAULT_COST)),
        noise_quantile=float(cfg.get("noise_quantile", 0.25)),
    )
    return report

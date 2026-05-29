from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from .forecast_math import cohere_directional_forecast


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _candidate_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        "base_pred_momentum_prior",
        "base_pred_reversion_prior",
        "base_pred_fundamental_prior",
        "base_pred_cross_market_prior",
        "base_pred_dynamic_blend",
        "base_pred_lstm",
        "base_pred_lgbm",
        "base_pred_xgb",
        "base_pred_rf",
        "base_pred_gbr",
        "base_pred_ridge_ar",
    ]
    cols = [col for col in preferred if col in frame.columns]
    extras = [col for col in frame.columns if col.startswith("base_pred_") and col not in cols]
    return cols + extras


def _rolling_candidate_quality(prior: pd.DataFrame, candidate_cols: list[str]) -> dict[str, float]:
    if prior.empty or "actual_return" not in prior.columns:
        return {}
    actual = pd.to_numeric(prior["actual_return"], errors="coerce").fillna(0.0)
    actual_dir = np.where(actual >= 0, 1, -1)
    quality: dict[str, float] = {}
    for col in candidate_cols:
        pred = pd.to_numeric(prior.get(col), errors="coerce").fillna(0.0)
        if pred.abs().sum() <= 0:
            continue
        pred_dir = np.where(pred >= 0, 1, -1)
        hit = float((pred_dir == actual_dir).mean())
        quality[col] = hit
    return quality


def _prob_from_return(expected_return: float, annualized_vol: float) -> float:
    daily_vol = max(_safe_float(annualized_vol, 0.18) / np.sqrt(252), 0.001)
    return float(np.clip(0.5 + 0.5 * np.tanh(expected_return / max(daily_vol * 1.25, 1e-4)), 0.02, 0.98))


def _direction_label(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "偏多"
    if prob_up <= 0.40:
        return "偏空"
    return "中性"


def apply_direction_first_calibration(
    predictions: pd.DataFrame,
    *,
    lookback: int = 80,
    min_samples: int = 35,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Make probability, direction and price center agree before signal generation.

    This layer is intentionally conservative. It does not promise higher returns;
    it prevents the terminal from showing a bearish probability with a bullish
    price center, and it marks ambiguous situations as neutral research output.
    """
    if not isinstance(predictions, pd.DataFrame) or predictions.empty:
        return predictions.copy(), {"version": "direction_first_v2", "enabled": False}

    work = predictions.copy()
    prob_col = "prob_up_multimodal" if "prob_up_multimodal" in work.columns else "prob_up"
    conf_col = "confidence_multimodal" if "confidence_multimodal" in work.columns else "confidence"
    candidate_cols = _candidate_columns(work)
    work["direction_v2_state"] = "未校准"
    work["direction_v2_edge"] = 0.0
    work["direction_v2_candidate"] = ""
    work["direction_v2_candidate_hit"] = np.nan
    work["direction_v2_note"] = ""

    for pos in range(len(work)):
        row = work.iloc[pos]
        old_return = _safe_float(row.get("predicted_return", 0.0))
        old_prob = _safe_float(row.get(prob_col, row.get("prob_up", 0.5)), 0.5)
        annualized_vol = max(_safe_float(row.get("ewma_vol_20", 0.18), 0.18), 0.04)
        close = max(_safe_float(row.get("close", 0.0)), 0.0)
        prior = work.iloc[max(0, pos - lookback):pos].copy()
        quality = _rolling_candidate_quality(prior, candidate_cols) if len(prior) >= min_samples else {}
        if len(prior) >= min_samples:
            prior_prob = pd.to_numeric(prior.get(prob_col, prior.get("prob_up", 0.5)), errors="coerce").fillna(0.5)
            prior_actual = pd.to_numeric(prior.get("actual_return", 0.0), errors="coerce").fillna(0.0)
            base_hit = float((np.where(prior_prob >= 0.5, 1, -1) == np.where(prior_actual >= 0, 1, -1)).mean())
        else:
            base_hit = 0.50

        candidate_probs: list[tuple[str, float, float]] = []
        for col in candidate_cols:
            current_return = _safe_float(row.get(col, 0.0))
            if abs(current_return) < 1e-9:
                continue
            hit = quality.get(col, 0.50)
            # Down-weight candidates that have not recently learned direction.
            reliability = float(np.clip(0.35 + max(hit - 0.50, -0.08) * 2.4, 0.10, 1.20))
            candidate_probs.append((col, _prob_from_return(current_return, annualized_vol), reliability))

        if candidate_probs:
            total_w = sum(item[2] for item in candidate_probs)
            candidate_prob = sum(prob * weight for _, prob, weight in candidate_probs) / max(total_w, 1e-8)
            best_name, _, _ = max(candidate_probs, key=lambda item: quality.get(item[0], 0.50))
            best_hit = quality.get(best_name, 0.50)
            best_return = _safe_float(row.get(best_name, 0.0))
            if best_hit >= 0.62 and best_hit >= base_hit + 0.055 and abs(best_return) > 1e-9:
                # A recently validated tin-specific candidate may temporarily
                # take over direction, but only after causal rolling evidence.
                takeover_prob = _prob_from_return(best_return, annualized_vol)
                candidate_prob = float(np.clip(0.72 * takeover_prob + 0.28 * candidate_prob, 0.02, 0.98))
        else:
            candidate_prob = 0.50
            best_name = ""
            best_hit = np.nan

        # The base stacker still leads. Candidate priors act as a consistency check.
        if len(prior) >= min_samples and np.isfinite(best_hit) and best_hit >= 0.62 and best_hit >= base_hit + 0.055:
            sample_weight = 0.58
        else:
            sample_weight = 0.35 if len(prior) >= min_samples else 0.18
        blended_prob = float(np.clip((1.0 - sample_weight) * old_prob + sample_weight * candidate_prob, 0.02, 0.98))
        edge = blended_prob - 0.5

        state = "方向优势不足"
        note = "概率优势较弱，价格中枢自动靠近当前价。"
        if edge >= 0.10:
            state = "偏多一致"
            note = "方向概率、候选因子和价格中枢已做一致性校准。"
        elif edge <= -0.10:
            state = "偏空一致"
            note = "方向概率、候选因子和价格中枢已做一致性校准。"

        daily_vol = annualized_vol / np.sqrt(252)
        implied_return = np.tanh(edge * 2.4) * max(daily_vol * 1.15, 0.001)
        if abs(edge) < 0.055:
            new_return = 0.20 * old_return + 0.80 * implied_return
            blended_prob = float(np.clip(0.5 + edge * 0.55, 0.45, 0.55))
            conf_shift = -12.0
        else:
            new_return = 0.55 * old_return + 0.45 * implied_return
            conf_shift = 3.0 if abs(edge) >= 0.16 else -2.0

        new_return, new_prob = cohere_directional_forecast(new_return, blended_prob, max(daily_vol, 1e-4))
        # Final hard gate: bearish probability cannot keep a bullish center, and vice versa.
        if new_prob <= 0.45 and new_return > 0:
            new_return = -abs(new_return) * 0.35
        elif new_prob >= 0.55 and new_return < 0:
            new_return = abs(new_return) * 0.35
        if 0.45 < new_prob < 0.55:
            new_return = float(np.clip(new_return, -daily_vol * 0.25, daily_vol * 0.25))

        work.iat[pos, work.columns.get_loc("predicted_return")] = new_return
        if "prob_up" in work.columns:
            work.iat[pos, work.columns.get_loc("prob_up")] = new_prob
        if "prob_up_multimodal" in work.columns:
            work.iat[pos, work.columns.get_loc("prob_up_multimodal")] = new_prob
        if conf_col in work.columns:
            old_conf = _safe_float(row.get(conf_col, row.get("confidence", 60.0)), 60.0)
            work.iat[pos, work.columns.get_loc(conf_col)] = float(np.clip(old_conf + conf_shift, 5.0, 99.0))
        if close > 0:
            center = close * (1.0 + new_return)
            half_width = max(close * daily_vol * (1.15 if abs(new_prob - 0.5) >= 0.12 else 1.55), close * 0.004)
            work.iat[pos, work.columns.get_loc("pred_center")] = center
            work.iat[pos, work.columns.get_loc("pred_low")] = max(0.0, center - half_width)
            work.iat[pos, work.columns.get_loc("pred_high")] = center + half_width

        work.iat[pos, work.columns.get_loc("direction_v2_state")] = state
        work.iat[pos, work.columns.get_loc("direction_v2_edge")] = edge
        work.iat[pos, work.columns.get_loc("direction_v2_candidate")] = best_name.replace("base_pred_", "")
        work.iat[pos, work.columns.get_loc("direction_v2_candidate_hit")] = best_hit
        work.iat[pos, work.columns.get_loc("direction_v2_note")] = note

    latest = work.iloc[-1]
    summary = {
        "version": "direction_first_v2",
        "enabled": True,
        "candidate_columns": candidate_cols,
        "latest_state": str(latest.get("direction_v2_state", "")),
        "latest_edge": _safe_float(latest.get("direction_v2_edge", 0.0)),
        "latest_label": _direction_label(_safe_float(latest.get(prob_col, latest.get("prob_up", 0.5)), 0.5)),
        "latest_candidate": str(latest.get("direction_v2_candidate", "")),
        "latest_candidate_hit": _safe_float(latest.get("direction_v2_candidate_hit", np.nan), np.nan),
        "neutral_count": int((work["direction_v2_state"] == "方向优势不足").sum()),
        "state_counts": {str(k): int(v) for k, v in work["direction_v2_state"].value_counts().to_dict().items()},
    }
    try:
        json.dumps(summary, ensure_ascii=False, allow_nan=False)
    except ValueError:
        summary["latest_candidate_hit"] = None
    return work, summary

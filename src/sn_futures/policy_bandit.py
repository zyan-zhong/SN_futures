from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import RiskConfig


@dataclass(frozen=True)
class PolicyAction:
    key: str
    label: str
    confidence_delta: float
    prob_up_delta: float
    prob_down_delta: float
    position_scale: float
    reward_risk_scale: float
    prior_bias: float = 0.0


ACTIONS: tuple[PolicyAction, ...] = (
    PolicyAction(
        key="defensive",
        label="防守",
        confidence_delta=6.0,
        prob_up_delta=0.04,
        prob_down_delta=-0.04,
        position_scale=0.60,
        reward_risk_scale=0.95,
        prior_bias=0.02,
    ),
    PolicyAction(
        key="balanced",
        label="平衡",
        confidence_delta=0.0,
        prob_up_delta=0.0,
        prob_down_delta=0.0,
        position_scale=1.00,
        reward_risk_scale=1.00,
        prior_bias=0.04,
    ),
    PolicyAction(
        key="offensive",
        label="进取",
        confidence_delta=-6.0,
        prob_up_delta=-0.03,
        prob_down_delta=0.03,
        position_scale=1.22,
        reward_risk_scale=1.08,
        prior_bias=0.01,
    ),
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
        if np.isfinite(numeric):
            return numeric
    except Exception:
        pass
    return default


def _current_confidence(row: pd.Series) -> float:
    return _safe_float(row.get("confidence_multimodal", row.get("confidence", 0.0)))


def _current_prob(row: pd.Series) -> float:
    return _safe_float(row.get("prob_up_multimodal", row.get("prob_up", 0.5)), 0.5)


def _build_context(predictions: pd.DataFrame) -> pd.DataFrame:
    work = predictions.copy()
    context = pd.DataFrame(index=work.index)
    confidence = work.get("confidence_multimodal", work.get("confidence", pd.Series(70.0, index=work.index)))
    prob_up = work.get("prob_up_multimodal", work.get("prob_up", pd.Series(0.5, index=work.index)))
    agreement = work.get("model_agreement", pd.Series(55.0, index=work.index))
    technical = work.get("technical_score", pd.Series(50.0, index=work.index))
    fundamental = work.get("fundamental_score", pd.Series(50.0, index=work.index))
    event = work.get("event_score", pd.Series(50.0, index=work.index))
    vol = work.get("ewma_vol_20", pd.Series(0.22, index=work.index))
    predicted_return = work.get("predicted_return", pd.Series(0.0, index=work.index))

    context["bias"] = 1.0
    context["confidence_edge"] = ((pd.to_numeric(confidence, errors="coerce").fillna(70.0) - 75.0) / 15.0).clip(-2.0, 2.0)
    context["prob_edge"] = ((pd.to_numeric(prob_up, errors="coerce").fillna(0.5) - 0.5) / 0.18).clip(-2.0, 2.0)
    context["pred_return_edge"] = (pd.to_numeric(predicted_return, errors="coerce").fillna(0.0) / 0.03).clip(-2.0, 2.0)
    context["vol_regime"] = ((pd.to_numeric(vol, errors="coerce").fillna(0.22) - 0.22) / 0.12).clip(-2.0, 2.0)
    context["agreement_edge"] = ((pd.to_numeric(agreement, errors="coerce").fillna(55.0) - 55.0) / 20.0).clip(-2.0, 2.0)
    context["technical_edge"] = ((pd.to_numeric(technical, errors="coerce").fillna(50.0) - 50.0) / 25.0).clip(-2.0, 2.0)
    context["fundamental_edge"] = ((pd.to_numeric(fundamental, errors="coerce").fillna(50.0) - 50.0) / 25.0).clip(-2.0, 2.0)
    context["event_edge"] = ((pd.to_numeric(event, errors="coerce").fillna(50.0) - 50.0) / 25.0).clip(-2.0, 2.0)

    regime = work.get("regime", pd.Series("NARROW_RANGE", index=work.index)).astype(str)
    context["trend_up"] = (regime == "UPTREND").astype(float)
    context["trend_down"] = (regime == "DOWNTREND").astype(float)
    context["wide_range"] = (regime == "WIDE_RANGE").astype(float)
    context["narrow_range"] = (regime == "NARROW_RANGE").astype(float)
    return context.fillna(0.0)


def _heuristic_bias(row: pd.Series) -> dict[str, float]:
    confidence = _current_confidence(row)
    prob_up = _current_prob(row)
    predicted_return = _safe_float(row.get("predicted_return", 0.0))
    annualized_vol = _safe_float(row.get("ewma_vol_20", 0.22), 0.22)
    regime = str(row.get("regime", "NARROW_RANGE"))
    signal_conviction = abs(prob_up - 0.5) + min(abs(predicted_return) / 0.02, 1.0)

    bias = {"defensive": 0.0, "balanced": 0.0, "offensive": 0.0}
    if annualized_vol >= 0.32:
        bias["defensive"] += 0.14
        bias["balanced"] += 0.04
    if regime in ("UPTREND", "DOWNTREND") and confidence >= 82 and signal_conviction >= 0.22:
        bias["offensive"] += 0.12
    if regime in ("WIDE_RANGE", "NARROW_RANGE"):
        bias["balanced"] += 0.10
    if confidence < 74:
        bias["defensive"] += 0.08
    if confidence >= 88 and signal_conviction >= 0.30:
        bias["offensive"] += 0.08
    return bias


def _threshold_bundle(row: pd.Series, risk: RiskConfig, action: PolicyAction) -> dict[str, float]:
    vol = _safe_float(row.get("ewma_vol_20", 0.22), 0.22)
    confidence_boost = 2.0 if vol >= 0.30 else 0.0
    confidence_threshold = float(np.clip(risk.confidence_threshold + action.confidence_delta + confidence_boost, 60.0, 98.0))
    prob_up_threshold = float(np.clip(risk.prob_up_threshold + action.prob_up_delta, 0.52, 0.90))
    prob_down_threshold = float(np.clip(risk.prob_down_threshold + action.prob_down_delta, 0.10, 0.48))
    position_scale = action.position_scale * (0.90 if vol >= 0.30 else 1.00)
    if _current_confidence(row) >= 90:
        position_scale *= 1.05
    position_scale = float(np.clip(position_scale, 0.35, 1.35))
    reward_risk_ratio = float(np.clip(risk.reward_risk_ratio * action.reward_risk_scale, 1.8, 3.5))
    return {
        "policy_confidence_threshold": confidence_threshold,
        "policy_prob_up_threshold": prob_up_threshold,
        "policy_prob_down_threshold": prob_down_threshold,
        "bandit_position_scale": position_scale,
        "policy_reward_risk_ratio": reward_risk_ratio,
    }


def _reward_for_action(row: pd.Series, thresholds: dict[str, float]) -> float:
    confidence = _current_confidence(row)
    prob_up = _current_prob(row)
    predicted_return = _safe_float(row.get("predicted_return", 0.0))
    actual_return = _safe_float(row.get("actual_return", 0.0))
    close = max(_safe_float(row.get("close", 1.0), 1.0), 1.0)
    atr = max(_safe_float(row.get("atr_14", close * 0.012), close * 0.012), close * 0.004)
    stop_return = max(atr / close, 0.004)
    take_return = stop_return * thresholds["policy_reward_risk_ratio"]

    if confidence >= thresholds["policy_confidence_threshold"] and prob_up >= thresholds["policy_prob_up_threshold"] and predicted_return > 0:
        signal = 1
    elif confidence >= thresholds["policy_confidence_threshold"] and prob_up <= thresholds["policy_prob_down_threshold"] and predicted_return < 0:
        signal = -1
    else:
        signal = 0

    if signal == 0:
        return -0.00015

    raw_return = signal * actual_return
    clipped = float(np.clip(raw_return, -stop_return, take_return))
    annualized_vol = _safe_float(row.get("ewma_vol_20", 0.22), 0.22)
    volatility_penalty = max(annualized_vol - 0.32, 0.0) * 0.015
    turnover_penalty = 0.0008 * thresholds["bandit_position_scale"]
    reward = thresholds["bandit_position_scale"] * clipped - turnover_penalty - volatility_penalty
    return float(reward)


def apply_contextual_bandit(
    predictions: pd.DataFrame,
    risk: RiskConfig | None = None,
    exploration: float = 0.18,
    ridge_penalty: float = 1.5,
) -> tuple[pd.DataFrame, dict[str, object]]:
    risk = risk or RiskConfig()
    if predictions.empty:
        return predictions.copy(), {"policy_version": "linucb_sn_v1", "available_actions": [action.label for action in ACTIONS]}

    work = predictions.copy()
    context = _build_context(work)
    feature_count = context.shape[1]
    state: dict[str, dict[str, object]] = {
        action.key: {
            "action": action,
            "A": np.eye(feature_count, dtype=float) * ridge_penalty,
            "b": np.zeros(feature_count, dtype=float),
            "count": 0,
            "reward_sum": 0.0,
        }
        for action in ACTIONS
    }

    policy_rows: list[dict[str, object]] = []
    for idx, row in work.iterrows():
        x = context.loc[idx].to_numpy(dtype=float)
        heuristic = _heuristic_bias(row)
        best_action = ACTIONS[1]
        best_score = float("-inf")
        action_scores: dict[str, float] = {}

        for action in ACTIONS:
            bundle = state[action.key]
            A = bundle["A"]  # type: ignore[assignment]
            b = bundle["b"]  # type: ignore[assignment]
            A_inv = np.linalg.pinv(A)
            theta = A_inv @ b
            mean_reward = float(x @ theta)
            uncertainty = float(np.sqrt(max(x @ A_inv @ x, 0.0)))
            score = mean_reward + exploration * uncertainty + heuristic.get(action.key, 0.0) + action.prior_bias
            action_scores[action.key] = score
            if score > best_score:
                best_score = score
                best_action = action

        thresholds = _threshold_bundle(row, risk, best_action)
        realized_reward = _reward_for_action(row, thresholds)
        bundle = state[best_action.key]
        bundle["A"] = bundle["A"] + np.outer(x, x)  # type: ignore[operator]
        bundle["b"] = bundle["b"] + realized_reward * x  # type: ignore[operator]
        bundle["count"] = int(bundle["count"]) + 1
        bundle["reward_sum"] = float(bundle["reward_sum"]) + realized_reward

        policy_rows.append(
            {
                "bandit_action": best_action.key,
                "bandit_action_label": best_action.label,
                "bandit_score": best_score,
                "bandit_reward_proxy": realized_reward,
                "bandit_defensive_score": action_scores.get("defensive", 0.0),
                "bandit_balanced_score": action_scores.get("balanced", 0.0),
                "bandit_offensive_score": action_scores.get("offensive", 0.0),
                **thresholds,
            }
        )

    policy_frame = pd.DataFrame(policy_rows, index=work.index)
    work = pd.concat([work, policy_frame], axis=1)
    action_counts = work["bandit_action_label"].value_counts().to_dict()
    action_reward = work.groupby("bandit_action_label")["bandit_reward_proxy"].mean().to_dict()
    latest_row = work.iloc[-1]
    summary = {
        "policy_version": "linucb_sn_v1",
        "available_actions": [action.label for action in ACTIONS],
        "action_counts": action_counts,
        "action_mean_reward": {str(key): float(value) for key, value in action_reward.items()},
        "latest_action": str(latest_row.get("bandit_action_label", "平衡")),
        "latest_position_scale": float(latest_row.get("bandit_position_scale", 1.0) or 1.0),
        "latest_confidence_threshold": float(latest_row.get("policy_confidence_threshold", risk.confidence_threshold) or risk.confidence_threshold),
        "latest_prob_up_threshold": float(latest_row.get("policy_prob_up_threshold", risk.prob_up_threshold) or risk.prob_up_threshold),
        "latest_prob_down_threshold": float(latest_row.get("policy_prob_down_threshold", risk.prob_down_threshold) or risk.prob_down_threshold),
    }
    return work, summary

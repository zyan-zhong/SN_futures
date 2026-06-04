from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, MutableMapping

from ..api.json_utils import sanitize_for_json


SCHEMA_VERSION = 1
DISPLAY_INPUT_PURPOSES = {"feature_store", "training", "prediction", "backtest"}
DISCLAIMER = "研究参考，不构成投资建议。"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if math.isfinite(parsed) else default


def _probability(card: Mapping[str, Any], *names: str, default: float | None = None) -> float | None:
    for name in names:
        if name in card:
            parsed = _safe_float(card.get(name), default=None)
            if parsed is not None:
                return max(0.0, min(1.0, parsed))
    return default


def _return_value(card: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        if name in card:
            parsed = _safe_float(card.get(name), default=None)
            if parsed is not None:
                return parsed
    return None


def build_raw_model_prediction(*, horizon: str, source_card: Mapping[str, Any]) -> dict[str, Any]:
    raw = {
        "schema_version": SCHEMA_VERSION,
        "layer": "RawModelPrediction",
        "model_id": str(source_card.get("model_id") or source_card.get("model_version") or ""),
        "horizon": str(horizon),
        "raw_prob_up": _probability(source_card, "raw_prob_up", "p_up", "prob_up", default=None),
        "raw_prob_down": _probability(source_card, "raw_prob_down", "p_down", "prob_down", default=None),
        "raw_prob_neutral": _probability(source_card, "raw_prob_neutral", "p_neutral", "prob_neutral", default=None),
        "raw_expected_return": _return_value(source_card, "raw_expected_return", "expected_return", "predicted_return"),
        "feature_manifest_hash": str(
            source_card.get("feature_manifest_hash")
            or source_card.get("feature_store_manifest_hash")
            or source_card.get("feature_manifest_sha256")
            or ""
        ),
    }
    return sanitize_for_json(raw)


def capture_raw_prediction_layers(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload or {})
    cards = out.get("cards") if isinstance(out.get("cards"), Mapping) else {}
    for horizon, card in cards.items():
        if isinstance(card, MutableMapping) and not isinstance(card.get("raw_layer"), Mapping):
            card["raw_layer"] = build_raw_model_prediction(horizon=str(horizon), source_card=card)
    out["prediction_layers_schema_version"] = SCHEMA_VERSION
    return sanitize_for_json(out)


def _calibration_metric(source: Mapping[str, Any], profile: Mapping[str, Any] | None, *names: str) -> float | None:
    for name in names:
        parsed = _safe_float(source.get(name), default=None)
        if parsed is not None:
            return parsed
    if isinstance(profile, Mapping):
        for name in names:
            parsed = _safe_float(profile.get(name), default=None)
            if parsed is not None:
                return parsed
    return None


def build_calibrated_prediction(
    *,
    raw_layer: Mapping[str, Any],
    source_card: Mapping[str, Any],
    calibration_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    calibration = source_card.get("calibration") if isinstance(source_card.get("calibration"), Mapping) else {}
    profile = calibration_profile if isinstance(calibration_profile, Mapping) else {}
    explicit_model = str(
        source_card.get("calibration_model_id")
        or calibration.get("model_id")
        or profile.get("calibration_model_id")
        or ""
    )
    brier = _calibration_metric(source_card, profile, "brier", "brier_score")
    ece = _calibration_metric(source_card, profile, "ece", "expected_calibration_error")
    applied = bool(explicit_model or calibration.get("enabled") or source_card.get("calibrated_prob_up") is not None)
    if not applied and brier is None and ece is None:
        status = "uncalibrated"
        model_id = ""
    else:
        status = "calibrated" if explicit_model else "calibrated_metrics_only"
        model_id = explicit_model
    calibrated = {
        "schema_version": SCHEMA_VERSION,
        "layer": "CalibratedPrediction",
        "horizon": str(raw_layer.get("horizon") or source_card.get("horizon") or ""),
        "calibrated_prob_up": _probability(source_card, "calibrated_prob_up", "p_up", "prob_up", default=raw_layer.get("raw_prob_up")),
        "calibrated_prob_down": _probability(source_card, "calibrated_prob_down", "p_down", "prob_down", default=raw_layer.get("raw_prob_down")),
        "calibrated_prob_neutral": _probability(source_card, "calibrated_prob_neutral", "p_neutral", "prob_neutral", default=raw_layer.get("raw_prob_neutral")),
        "calibrated_expected_return": _return_value(source_card, "calibrated_expected_return", "expected_return", "predicted_return"),
        "calibration_model_id": model_id,
        "calibration_status": status,
        "calibration_applied": status == "calibrated",
        "brier": brier,
        "ece": ece,
    }
    return sanitize_for_json(calibrated)


def build_guarded_research_signal(
    *,
    horizon: str,
    calibrated_layer: Mapping[str, Any],
    source_card: Mapping[str, Any],
    data_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gate = dict(data_gate or {})
    if "allowed" not in gate:
        gate["allowed"] = True
    blocking_reasons = gate.get("blocking_reasons") if isinstance(gate.get("blocking_reasons"), list) else []
    abstain_reasons: list[str] = [str(item) for item in blocking_reasons if item]
    event_gate = source_card.get("event_gate") if isinstance(source_card.get("event_gate"), Mapping) else {}
    price_gate = source_card.get("price_path_sanity_gate") if isinstance(source_card.get("price_path_sanity_gate"), Mapping) else {}
    if source_card.get("direction_price_conflict"):
        abstain_reasons.append("direction_price_conflict")
    allowed = bool(gate.get("allowed")) and not abstain_reasons
    signal = str(source_card.get("signal") or source_card.get("direction_key") or source_card.get("direction_label") or "neutral")
    guarded = {
        "schema_version": SCHEMA_VERSION,
        "layer": "GuardedResearchSignal",
        "horizon": str(horizon),
        "data_gate": gate,
        "event_gate": event_gate or {"status": "not_evaluated"},
        "price_path_sanity_gate": price_gate or {"status": source_card.get("path_sanity_status") or "not_evaluated"},
        "abstain": not allowed,
        "neutralized": not allowed,
        "signal": signal if allowed else "neutral",
        "abstain_reasons": abstain_reasons,
        "neutralization_reasons": abstain_reasons,
        "allowed_for_customer_display": bool(gate.get("allowed")),
        "allowed_for_feature_store": False,
        "allowed_for_training": False,
        "allowed_for_prediction": False,
        "allowed_for_backtest": False,
        "calibrated_prob_up": calibrated_layer.get("calibrated_prob_up"),
        "calibrated_prob_down": calibrated_layer.get("calibrated_prob_down"),
        "calibrated_prob_neutral": calibrated_layer.get("calibrated_prob_neutral"),
    }
    return sanitize_for_json(guarded)


def build_terminal_display_card(
    *,
    horizon: str,
    guarded_signal: Mapping[str, Any],
    source_card: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(source_card or {})
    reasons = guarded_signal.get("abstain_reasons") or guarded_signal.get("neutralization_reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)] if reasons else []
    card = {
        "schema_version": SCHEMA_VERSION,
        "layer": "TerminalDisplayCard",
        "horizon": str(horizon),
        "generated_at": _now(),
        "display_only": True,
        "allowed_for_customer_display": bool(guarded_signal.get("allowed_for_customer_display", False)),
        "allowed_for_feature_store": False,
        "allowed_for_training": False,
        "allowed_for_prediction": False,
        "allowed_for_backtest": False,
        "direction_label": source.get("direction_label") or guarded_signal.get("signal") or "neutral",
        "abstain": bool(guarded_signal.get("abstain", False)),
        "abstain_reasons": [str(item) for item in reasons if item],
        "explanation_zh": source.get("decision_explanation") or source.get("鍐崇瓥璇存槑") or "当前仅展示研究解释，不作为模型、特征或回测输入。",
        "risk_notes": source.get("risk_notes") or source.get("椋庨櫓鎻愮ず") or ["研究参考，不构成投资建议。"],
        "charts": source.get("charts") or source.get("chart_payload") or {},
        "disclaimer": source.get("disclaimer") or DISCLAIMER,
    }
    return sanitize_for_json(card)


def is_terminal_display_card_allowed_as_input(card: Mapping[str, Any], *, purpose: str) -> bool:
    if str(card.get("layer") or "") == "TerminalDisplayCard":
        return False
    if bool(card.get("display_only")):
        return False
    key = f"allowed_for_{str(purpose).strip().lower()}"
    if key in card:
        return bool(card.get(key))
    return str(purpose).strip().lower() not in DISPLAY_INPUT_PURPOSES


def attach_prediction_layers(
    payload: Mapping[str, Any],
    *,
    data_gate: Mapping[str, Any] | None = None,
    calibration_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = capture_raw_prediction_layers(payload)
    cards = out.get("cards") if isinstance(out.get("cards"), Mapping) else {}
    for horizon, card in cards.items():
        if not isinstance(card, MutableMapping):
            continue
        raw = card.get("raw_layer") if isinstance(card.get("raw_layer"), Mapping) else build_raw_model_prediction(horizon=str(horizon), source_card=card)
        calibrated = build_calibrated_prediction(raw_layer=raw, source_card=card, calibration_profile=calibration_profile)
        guarded = build_guarded_research_signal(horizon=str(horizon), calibrated_layer=calibrated, source_card=card, data_gate=data_gate)
        display = build_terminal_display_card(horizon=str(horizon), guarded_signal=guarded, source_card=card)
        card["raw_layer"] = raw
        card["calibrated_layer"] = calibrated
        card["guarded_layer"] = guarded
        card["display_layer"] = display
    out["prediction_layers_schema_version"] = SCHEMA_VERSION
    return sanitize_for_json(out)


def build_blocked_prediction_payload(
    *,
    blocking_reasons: list[str],
    data_gate: Mapping[str, Any],
    data_watermark: Mapping[str, Any],
) -> dict[str, Any]:
    guarded = {
        "layer": "GuardedResearchSignal",
        "data_gate": dict(data_gate),
        "event_gate": {"status": "not_evaluated"},
        "price_path_sanity_gate": {"status": "not_evaluated"},
        "abstain": True,
        "neutralized": True,
        "signal": "neutral",
        "abstain_reasons": [str(item) for item in blocking_reasons if item],
        "neutralization_reasons": [str(item) for item in blocking_reasons if item],
        "allowed_for_customer_display": True,
        "allowed_for_feature_store": False,
        "allowed_for_training": False,
        "allowed_for_prediction": False,
        "allowed_for_backtest": False,
    }
    return sanitize_for_json(
        {
            "prediction_layers_schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "cards": {},
            "raw_layer": None,
            "calibrated_layer": None,
            "guarded_layer": guarded,
            "display_layer": build_terminal_display_card(horizon="blocked", guarded_signal=guarded, source_card={}),
            "blocking_reasons": guarded["abstain_reasons"],
            "data_watermark": dict(data_watermark),
            "disclaimer": DISCLAIMER,
        }
    )


def build_no_active_model_prediction_payload(*, data_watermark: Mapping[str, Any] | None = None) -> dict[str, Any]:
    gate = {
        "allowed": False,
        "blocking_reasons": ["no_active_model"],
        "gate": "active_model",
    }
    return build_blocked_prediction_payload(
        blocking_reasons=["no_active_model"],
        data_gate=gate,
        data_watermark=data_watermark or {},
    )

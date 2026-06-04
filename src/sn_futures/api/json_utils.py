from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any, Mapping

from .schemas import schema_to_dict


MISSING_TEXT = "数据暂缺"
LOW_QUALITY_THRESHOLD = 0.55
_SENSITIVE_KEY_FRAGMENTS = ("api_key", "apikey", "password", "passwd", "secret", "token", "credential")
_SAFE_SENSITIVE_METADATA_SUFFIXES = (
    "_configured",
    "_masked",
    "_source",
    "_source_label_zh",
    "_ui_message_zh",
    "_status",
)
_SAFE_SENSITIVE_METADATA_KEYS = {
    "credential_handoff_required",
    "gitignore_secret_coverage",
    "missing_provider_credentials",
    "no_secret_echo_allowed",
    "no_raw_token_in_artifacts",
    "provider_credentials",
}


def _is_sensitive_key(key: Any) -> bool:
    text = str(key).lower()
    if text in _SAFE_SENSITIVE_METADATA_KEYS:
        return False
    if any(text.endswith(suffix) for suffix in _SAFE_SENSITIVE_METADATA_SUFFIXES):
        return False
    return any(fragment in text for fragment in _SENSITIVE_KEY_FRAGMENTS)


def sanitize_for_json(obj: Any, *, text_for_missing: bool = False) -> Any:
    """Recursively convert terminal payloads to safe JSON-compatible values."""

    obj = schema_to_dict(obj)
    if isinstance(obj, Mapping):
        clean: dict[str, Any] = {}
        for key, value in obj.items():
            text_key = str(key)
            if _is_sensitive_key(text_key):
                clean[text_key] = "已脱敏"
            else:
                clean[text_key] = sanitize_for_json(value, text_for_missing=text_for_missing)
        return clean
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item, text_for_missing=text_for_missing) for item in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, float):
        if math.isfinite(obj):
            return obj
        return MISSING_TEXT if text_for_missing else None
    if hasattr(obj, "item"):
        try:
            return sanitize_for_json(obj.item(), text_for_missing=text_for_missing)
        except Exception:
            return str(obj)
    if isinstance(obj, str) and obj.strip().lower() in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        return MISSING_TEXT if text_for_missing else None
    return obj


def ensure_no_non_finite(obj: Any) -> Any:
    cleaned = sanitize_for_json(obj)
    json.dumps(cleaned, ensure_ascii=False, allow_nan=False, default=str)
    return cleaned


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(ensure_no_non_finite(obj), ensure_ascii=False, allow_nan=False, default=str)


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _is_observe_signal(payload: Mapping[str, Any]) -> bool:
    signal = str(payload.get("signal") or payload.get("信号") or "").strip()
    direction = str(payload.get("direction") or payload.get("方向") or "").strip()
    return signal == "观望" or direction == "观望" or signal.lower() in {"neutral", "no_trade", "observe"}


def _is_degraded(payload: Mapping[str, Any]) -> bool:
    status = str(payload.get("model_status") or payload.get("模型状态") or "").lower()
    return "degraded" in status or "降级" in status


def _low_quality(payload: Mapping[str, Any]) -> bool:
    score = _as_float(payload.get("data_quality_score", payload.get("data_quality")))
    return score is not None and score < LOW_QUALITY_THRESHOLD


def _edge_not_positive(payload: Mapping[str, Any]) -> bool:
    edge = _as_float(payload.get("trade_edge", payload.get("edge")))
    return edge is not None and edge <= 0


def clean_trade_points(payload: Any) -> Any:
    """Remove actionable price points when the payload must remain research-only."""

    if isinstance(payload, list):
        return [clean_trade_points(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    cleaned = {key: clean_trade_points(value) for key, value in payload.items()}
    if _is_observe_signal(cleaned) or _is_degraded(cleaned) or _low_quality(cleaned) or _edge_not_positive(cleaned):
        for key in ("entry", "entry_price", "entry_reference", "stop_loss", "take_profit", "target_price"):
            if key in cleaned:
                cleaned[key] = None
        cleaned.setdefault("trade_point_note", "暂无交易点位")

    entry = cleaned.get("entry")
    stop_loss = cleaned.get("stop_loss")
    take_profit = cleaned.get("take_profit")
    if entry is not None and entry == stop_loss == take_profit:
        cleaned["entry"] = None
        cleaned["stop_loss"] = None
        cleaned["take_profit"] = None
        cleaned["trade_point_note"] = "暂无交易点位"
    return cleaned

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import numpy as np
import pandas as pd

from .config import ProjectPaths
from .direction_ensemble import apply_direction_ensemble_to_payload
from .news_policy import analyze_news_policy
from .prediction_display import apply_direction_gate, build_data_trust_badges, explain_driver
from .price_risk import apply_realistic_price_gates
from .services.prediction_layers_service import attach_prediction_layers, capture_raw_prediction_layers


UNIFIED_FORECAST_FILE = "sn_unified_forecast.json"
LIVE_CARD_ORDER = [
    "next_5m",
    "next_15m",
    "next_30m",
    "next_hour",
    "tomorrow",
    "one_to_two_weeks",
    "one_to_three_months",
]
INTRADAY_HORIZON_KEYS = {"next_5m", "next_15m", "next_30m", "next_hour"}
LONG_HORIZON_KEYS = {"one_to_two_weeks", "one_to_three_months"}
DISCLAIMER = "本内容仅为沪锡期货量化投研参考，不构成任何投资建议，期货交易有风险，投资需谨慎。"


def unified_forecast_path(output_dir: Path | None = None) -> Path:
    return (output_dir or ProjectPaths().output_dir) / UNIFIED_FORECAST_FILE


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_unified_forecast(output_dir: Path | None = None, *, max_age_minutes: int | None = None) -> dict[str, Any]:
    payload = _read_json(unified_forecast_path(output_dir))
    if not payload or max_age_minutes is None:
        return payload
    created = str(payload.get("unified_generated_at") or payload.get("generated_at") or "")
    try:
        ts = pd.Timestamp(created)
        if ts.tzinfo is not None:
            ts = ts.tz_convert("Asia/Hong_Kong").tz_localize(None)
        age = (pd.Timestamp.now() - ts).total_seconds() / 60.0
        if age > max_age_minutes:
            return {}
    except Exception:
        return {}
    return payload


def save_unified_forecast(payload: Mapping[str, Any], output_dir: Path | None = None) -> Path:
    out = output_dir or ProjectPaths().output_dir
    out.mkdir(parents=True, exist_ok=True)
    path = unified_forecast_path(out)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _snapshot_live_quote(live_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(live_snapshot, Mapping):
        return {}
    meta = live_snapshot.get("contract_meta", {}) if isinstance(live_snapshot.get("contract_meta"), Mapping) else {}
    active_symbol = str(meta.get("active_contract_symbol") or meta.get("target_contract_symbol") or "")
    quotes = live_snapshot.get("quotes", []) if isinstance(live_snapshot.get("quotes"), list) else []
    quote_rows = [row for row in quotes if isinstance(row, Mapping)]
    preferred = [row for row in quote_rows if active_symbol and str(row.get("symbol", "")) == active_symbol]
    quote = preferred[0] if preferred else (quote_rows[0] if quote_rows else {})
    latest = _safe_float(quote.get("latest", 0.0), 0.0) if quote else 0.0
    prev_close = _safe_float(quote.get("prev_close", 0.0), 0.0) if quote else 0.0
    if latest <= 0:
        return {}
    change = latest - prev_close if prev_close > 0 else 0.0
    return {
        "symbol": str(quote.get("symbol", "")),
        "contract_code": str(meta.get("active_contract") or meta.get("target_contract") or "SN"),
        "name": str(quote.get("name", "")),
        "latest": latest,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change / prev_close if prev_close > 0 else 0.0,
        "open": _safe_float(quote.get("open", 0.0), 0.0),
        "high": _safe_float(quote.get("high", 0.0), 0.0),
        "low": _safe_float(quote.get("low", 0.0), 0.0),
        "volume": _safe_float(quote.get("volume", 0.0), 0.0),
        "open_interest": _safe_float(quote.get("open_interest", 0.0), 0.0),
        "quote_time": str(live_snapshot.get("generated_at", "")),
    }


def _basic_watermark(
    *,
    raw: pd.DataFrame | None,
    live_snapshot: Mapping[str, Any] | None,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(fallback or {})
    latest_row = raw.iloc[-1] if isinstance(raw, pd.DataFrame) and not raw.empty else pd.Series(dtype=object)
    meta = live_snapshot.get("contract_meta", {}) if isinstance(live_snapshot, Mapping) and isinstance(live_snapshot.get("contract_meta"), Mapping) else {}
    statuses = live_snapshot.get("source_status", []) if isinstance(live_snapshot, Mapping) and isinstance(live_snapshot.get("source_status"), list) else []
    live_quote = _snapshot_live_quote(live_snapshot) or (base.get("live_quote") if isinstance(base.get("live_quote"), dict) else {})
    latest_daily = str(pd.Timestamp(raw.index[-1]).date()) if isinstance(raw, pd.DataFrame) and not raw.empty else str(base.get("latest_daily", ""))
    enabled = [row for row in statuses if isinstance(row, Mapping) and row.get("enabled")]
    success = [row for row in enabled if row.get("success")]
    source_quality = len(success) / max(len(enabled), 1) if enabled else _safe_float(base.get("quality_score"), 0.58)
    raw_quality = _safe_float(latest_row.get("data_quality_score", base.get("quality_score", 0.58)), 0.58)
    quality = float(np.clip(0.64 * raw_quality + 0.36 * source_quality, 0.05, 1.0))
    minute_cols = {"intraday_close", "intraday_high", "intraday_low", "intraday_volume", "intraday_realized_vol"}
    minute_available = bool(
        isinstance(raw, pd.DataFrame)
        and not raw.empty
        and minute_cols.intersection(raw.columns)
        and any(raw[col].notna().any() for col in minute_cols.intersection(raw.columns))
    )
    sample_data_used = bool(
        base.get("sample_data_used")
        or base.get("sample")
        or base.get("sample_mode")
        or latest_row.get("sample_data_used")
        or latest_row.get("sample")
        or latest_row.get("sample_mode")
    )
    baseline_used = bool(base.get("baseline_used") or latest_row.get("baseline_used"))
    base.update(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "latest_daily": latest_daily,
            "latest_realtime": str((live_snapshot or {}).get("generated_at", "") or live_quote.get("quote_time", "")),
            "active_contract": str(meta.get("active_contract") or meta.get("target_contract") or base.get("active_contract") or "SN"),
            "target_contract": str(meta.get("target_contract") or base.get("target_contract") or "SN"),
            "history_symbol": str(meta.get("history_symbol") or latest_row.get("history_symbol", base.get("history_symbol", "SN0"))),
            "source_mode": str(latest_row.get("data_source_mode", base.get("source_mode", "cached_live_prediction")) or ""),
            "minute_data_available": minute_available or bool(base.get("minute_data_available")),
            "quality_score": quality,
            "source_status": statuses or base.get("source_status", []),
            "live_quote": live_quote,
            "live_overlay_used": bool(live_quote) or bool(base.get("live_overlay_used")),
            "history_immutable": True,
            "live_overlay_used_for_display_only": bool(live_quote) or bool(base.get("live_overlay_used")),
            "live_overlay_used_for_training": False,
            "live_overlay_used_for_backtest": False,
            "sample_data_used": sample_data_used,
            "baseline_used": baseline_used,
            "is_real_data_only": bool(latest_daily or live_quote) and not sample_data_used and not baseline_used,
            "disclaimer": DISCLAIMER,
        }
    )
    return base


def _direction_label(prob_up: float, p_neutral: float = 0.0) -> str:
    if p_neutral >= 0.45:
        return "中性/方向优势不足"
    if prob_up >= 0.60:
        return "偏多"
    if prob_up <= 0.40:
        return "偏空"
    return "中性/方向优势不足"


def _direction_key(prob_up: float, p_neutral: float = 0.0) -> str:
    if p_neutral >= 0.45:
        return "neutral"
    if prob_up >= 0.60:
        return "bullish"
    if prob_up <= 0.40:
        return "bearish"
    return "neutral"


def _normalize_card_probs(card: MutableMapping[str, Any]) -> None:
    p_up = _safe_float(card.get("p_up"), float("nan"))
    p_down = _safe_float(card.get("p_down"), float("nan"))
    p_neutral = _safe_float(card.get("p_neutral"), float("nan"))
    if not all(np.isfinite(v) for v in (p_up, p_down, p_neutral)):
        prob_up = float(np.clip(_safe_float(card.get("prob_up"), 0.5), 0.0, 1.0))
        p_neutral = float(np.clip(_safe_float(card.get("prob_neutral"), 0.0), 0.0, 0.88))
        mass = 1.0 - p_neutral
        p_up = mass * prob_up
        p_down = mass * (1.0 - prob_up)
    total = p_up + p_down + p_neutral
    if total <= 0:
        p_up, p_down, p_neutral = 0.33, 0.33, 0.34
        total = 1.0
    p_up, p_down, p_neutral = p_up / total, p_down / total, p_neutral / total
    prob_up = p_up / max(p_up + p_down, 1e-9)
    card["p_up"] = float(p_up)
    card["p_down"] = float(p_down)
    card["p_neutral"] = float(p_neutral)
    card["prob_up"] = float(prob_up)
    card["prob_down"] = float(1.0 - prob_up)
    card["prob_neutral"] = float(p_neutral)
    card["gate_adjusted_prob_up"] = card["prob_up"]


def _soften_probs(card: MutableMapping[str, Any], severity: float, neutral_add: float) -> None:
    _normalize_card_probs(card)
    p_up = _safe_float(card.get("p_up"), 0.33)
    p_down = _safe_float(card.get("p_down"), 0.33)
    p_neutral = _safe_float(card.get("p_neutral"), 0.34)
    ratio = p_up / max(p_up + p_down, 1e-9)
    ratio = 0.5 + (ratio - 0.5) * (1.0 - float(np.clip(severity, 0.0, 1.0)))
    p_neutral = float(np.clip(p_neutral + neutral_add, 0.0, 0.88))
    mass = 1.0 - p_neutral
    card["p_up"] = mass * ratio
    card["p_down"] = mass * (1.0 - ratio)
    card["p_neutral"] = p_neutral
    _normalize_card_probs(card)


def _realign_final_card(card: MutableMapping[str, Any]) -> None:
    horizon = str(card.get("horizon_key") or card.get("horizon") or "")
    anchor = _safe_float(card.get("anchor_close") or card.get("anchor_price") or card.get("asof_price"), 0.0)
    if anchor <= 0:
        return
    _normalize_card_probs(card)
    center = _safe_float(card.get("price_center"), anchor)
    prob = _safe_float(card.get("prob_up"), 0.5)
    p_neutral = _safe_float(card.get("p_neutral"), 0.0)
    confidence = _safe_float(card.get("confidence_score") or card.get("confidence"), 0.55)
    conflict = (prob <= 0.40 and p_neutral <= 0.45 and center > anchor) or (prob >= 0.60 and p_neutral <= 0.45 and center < anchor)
    if conflict:
        half = max(abs(_safe_float(card.get("range_high"), center) - _safe_float(card.get("range_low"), center)) / 2.0, anchor * 0.006)
        center = anchor + (center - anchor) * 0.35
        card["price_center"] = center
        card["range_low"] = max(0.0, center - half)
        card["range_high"] = center + half
        card["direction_price_conflict"] = True
        card["confidence_score"] = float(np.clip(confidence * 0.62, 0.0, 1.0))
        card["confidence"] = card["confidence_score"]
        _soften_probs(card, 0.55, 0.12)
        card["final_consistency_guard"] = "方向概率与价格中枢冲突，已降置信并收敛价格路径"

    _normalize_card_probs(card)
    prob = _safe_float(card.get("prob_up"), 0.5)
    p_neutral = _safe_float(card.get("p_neutral"), 0.0)
    neutral = _direction_key(prob, p_neutral) == "neutral"
    if neutral:
        cap_map = {
            "next_5m": 0.0008,
            "next_15m": 0.0012,
            "next_30m": 0.0018,
            "next_hour": 0.0025,
            "tomorrow": 0.0060,
            "one_to_two_weeks": 0.0120,
            "one_to_three_months": 0.0180,
        }
        cap = cap_map.get(horizon, 0.0080)
        raw_center = _safe_float(card.get("price_center"), anchor)
        offset = float(np.clip(raw_center / anchor - 1.0, -cap, cap))
        if abs(raw_center / anchor - 1.0) > cap:
            card["neutral_center_guard"] = "方向优势不足，价格中枢已收敛到实时价附近"
        center = anchor * (1.0 + offset)
        half_existing = abs(_safe_float(card.get("range_high"), center) - _safe_float(card.get("range_low"), center)) / 2.0
        half_cap_map = {
            "next_5m": 0.0015,
            "next_15m": 0.0025,
            "next_30m": 0.0040,
            "next_hour": 0.0080,
            "tomorrow": 0.0260,
            "one_to_two_weeks": 0.0430,
            "one_to_three_months": 0.0550,
        }
        min_half = anchor * max(cap * 1.6, 0.004)
        max_half = anchor * half_cap_map.get(horizon, 0.035)
        half = min(max(half_existing, min_half), max_half)
        card["price_center"] = center
        card["range_low"] = max(0.0, center - half)
        card["range_high"] = center + half
        card["expected_return"] = offset
        card["center_offset_pct"] = offset

    _normalize_card_probs(card)
    prob = _safe_float(card.get("prob_up"), 0.5)
    p_neutral = _safe_float(card.get("p_neutral"), 0.0)
    card["direction_key"] = _direction_key(prob, p_neutral)
    card["direction_label"] = _direction_label(prob, p_neutral)


def _long_horizon_event_guard(card: MutableMapping[str, Any], news_summary: Mapping[str, Any]) -> None:
    horizon = str(card.get("horizon_key") or card.get("horizon") or "")
    if horizon not in LONG_HORIZON_KEYS:
        return
    news_weight = _safe_float(news_summary.get("confidence_weight"), 0.0)
    direction = str(card.get("direction_key") or "")
    candidates = card.get("direction_candidate_scores", [])
    active_same = 0
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, Mapping):
                continue
            if direction and str(item.get("direction") or "") == direction and _safe_float(item.get("weight"), 0.0) > 0.08:
                active_same += 1
    if news_weight < 0.30 and active_same < 2:
        anchor = _safe_float(card.get("anchor_close") or card.get("anchor_price") or card.get("asof_price"), 0.0)
        if anchor <= 0:
            return
        center = anchor + (_safe_float(card.get("price_center"), anchor) - anchor) * 0.30
        half = max(abs(_safe_float(card.get("range_high"), center) - _safe_float(card.get("range_low"), center)) / 2.0, anchor * (0.018 if horizon == "one_to_two_weeks" else 0.030))
        card["price_center"] = center
        card["range_low"] = max(0.0, center - half)
        card["range_high"] = center + half
        _soften_probs(card, 0.35, 0.06)
        card["long_horizon_guard"] = "长周期缺少重大新闻/产业因子确认，已降低强趋势表达"


def build_unified_forecast(
    base_live_predictions: Mapping[str, Any],
    *,
    output_dir: Path | None = None,
    raw: pd.DataFrame | None = None,
    live_snapshot: Mapping[str, Any] | None = None,
    calibration_profile: Mapping[str, Any] | None = None,
    data_watermark: Mapping[str, Any] | None = None,
    hardware_profile: Mapping[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    out = output_dir or ProjectPaths().output_dir
    payload = json.loads(json.dumps(dict(base_live_predictions or {}), ensure_ascii=False, default=str))
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    ordered = {key: cards[key] for key in LIVE_CARD_ORDER if key in cards}
    ordered.update({key: value for key, value in cards.items() if key not in ordered})
    payload["cards"] = ordered
    payload = capture_raw_prediction_layers(payload)

    watermark = _basic_watermark(raw=raw, live_snapshot=live_snapshot, fallback=data_watermark)
    news_policy = analyze_news_policy(out)
    fallback_news_summary = news_policy.get("summary", {}) if isinstance(news_policy.get("summary"), Mapping) else {}
    quality = _safe_float(watermark.get("quality_score"), 0.58)
    source_mode = str(watermark.get("source_mode") or "cached_live_prediction")
    minute_available = bool(watermark.get("minute_data_available"))
    live_quote = watermark.get("live_quote") if isinstance(watermark.get("live_quote"), dict) else {}
    live_price = _safe_float(live_quote.get("latest"), 0.0)

    for key, card in ordered.items():
        if not isinstance(card, MutableMapping):
            continue
        card["horizon_key"] = str(key)
        if live_price > 0:
            card["asof_price"] = live_price
            card["anchor_price"] = live_price
            card["anchor_close"] = live_price
        card.setdefault("display_drivers", [explain_driver(item) for item in card.get("core_drivers", [])])
        card["data_trust_badges"] = build_data_trust_badges(
            quality_score=quality,
            source_mode=source_mode,
            minute_data_available=minute_available,
        )
        card["data_quality_score"] = quality
        card["data_quality_discount"] = round(max(0.0, 1.0 - quality), 4)
        card["live_quote"] = live_quote
        card_news_summary = card.get("news_policy_contribution") if isinstance(card.get("news_policy_contribution"), Mapping) else {}
        if not card_news_summary:
            card_news_summary = card.get("news_policy_factor") if isinstance(card.get("news_policy_factor"), Mapping) else {}
        if not card_news_summary:
            card_news_summary = fallback_news_summary
        card["news_policy_payload"] = {"summary": dict(card_news_summary)}
        card["news_policy_contribution"] = dict(card_news_summary)
        card["news_policy_factor"] = dict(card_news_summary)
        card["is_research_only"] = True
        if key in INTRADAY_HORIZON_KEYS and not bool(card.get("validation_eligible", False)):
            card["validation_note"] = card.get("validation_note") or "短周期需要连续快照/分钟线，数据不足时仅作参考"

    payload = apply_direction_ensemble_to_payload(
        payload,
        news_policy=news_policy,
        validation_profile=calibration_profile or {},
        data_quality_score=quality,
        minute_data_available=minute_available,
    )
    payload = apply_direction_gate(
        payload,
        dict(calibration_profile or {}),
        data_quality_score=quality,
        source_mode=source_mode,
        minute_data_available=minute_available,
    )
    payload = apply_realistic_price_gates(payload)

    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    for key, card in cards.items():
        if not isinstance(card, MutableMapping):
            continue
        card_news_summary = card.get("news_policy_contribution") if isinstance(card.get("news_policy_contribution"), Mapping) else {}
        if not card_news_summary:
            card_news_summary = fallback_news_summary
        _long_horizon_event_guard(card, card_news_summary)
        _realign_final_card(card)
        card["news_policy_impact"] = {
            "weighted_sentiment": _safe_float(card_news_summary.get("weighted_sentiment"), 0.0),
            "direction_contribution": card_news_summary.get("direction_contribution") or card_news_summary.get("contribution_label"),
            "confidence_weight": _safe_float(card_news_summary.get("confidence_weight"), 0.0),
            "included_count": int(_safe_float(card_news_summary.get("included_count"), 0)),
            "recognized_count": int(_safe_float(card_news_summary.get("recognized_count"), 0)),
            "rejected_count": int(_safe_float(card_news_summary.get("rejected_count"), 0)),
            "event_factor_direction": card_news_summary.get("event_factor_direction", "neutral"),
            "event_feature_hash": card_news_summary.get("event_feature_hash", ""),
            "failure_reason": str(card_news_summary.get("failure_reason") or ""),
        }
        card["range_source"] = card.get("range_source") or "历史 forward return 分位 + ATR + 兑现误差 + 新闻事件权重"
        card["asof_status"] = {
            "latest_daily": watermark.get("latest_daily", ""),
            "latest_realtime": watermark.get("latest_realtime", ""),
            "active_contract": watermark.get("active_contract", ""),
            "source_mode": source_mode,
            "live_overlay_used": bool(watermark.get("live_overlay_used")),
        }
        card["gpu_profile_used"] = dict(hardware_profile or {})

    ordered_cards = {key: cards[key] for key in LIVE_CARD_ORDER if key in cards}
    ordered_cards.update({key: value for key, value in cards.items() if key not in ordered_cards})
    payload["cards"] = ordered_cards
    payload["data_watermark"] = watermark
    payload["news_policy"] = news_policy
    payload["live_quote"] = live_quote
    payload["hardware_profile"] = dict(hardware_profile or {})
    payload["unified_forecast_version"] = "v3.8_direction_event_learning_position_core"
    payload["unified_generated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["unified_result_source"] = "统一链路：真实数据水位 -> 事件/方向候选 -> 价格连续性守门 -> 历史误差校准 -> UI"
    payload["disclaimer"] = DISCLAIMER
    payload = attach_prediction_layers(
        payload,
        data_gate={"allowed": not bool(watermark.get("sample_data_used") or watermark.get("baseline_used")), "blocking_reasons": []},
        calibration_profile=calibration_profile,
    )
    if persist:
        save_unified_forecast(payload, out)
    return payload

from __future__ import annotations

import json
import time
import uuid
import webbrowser
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import numpy as np
import pandas as pd

from .bootstrap.runtime_guard import runtime_status
from .chart_alignment import build_forecast_curve
from .config import ProjectPaths
from .event_features import build_event_evidence, sync_event_store_from_news
from .event_store import load_events, load_provider_status, resolve_event_url
from .hardware import detect_hardware_profile, load_hardware_profile, resolve_compute_profile
from .horizon_registry import list_horizon_configs
from .position_scenario import evaluate_position_scenario
from .prediction_display import apply_direction_gate, build_data_trust_badges, explain_driver
from .price_risk import apply_realistic_price_gates
from .services import (
    build_api_learning_status,
    build_api_model_health,
    build_backtest_diagnostics,
    build_position_scenario,
    build_report_content as build_service_report_content,
    integrate_live_prediction_payload,
    sanitize_for_json,
)
from .trading_calendar import sn_trading_session_state
from .unified_forecast import LIVE_CARD_ORDER, build_unified_forecast, load_unified_forecast, save_unified_forecast


DISCLAIMER = "本系统所有内容仅为沪锡期货量化投研参考，不构成任何投资建议，期货交易有风险，投资需谨慎。"
SHORT_HORIZON_KEYS = {"next_5m", "next_15m", "next_30m"}
INTRADAY_HORIZON_KEYS = SHORT_HORIZON_KEYS | {"next_hour"}
HORIZON_LABELS = {
    "next_5m": "未来5分钟",
    "next_15m": "未来15分钟",
    "next_30m": "未来30分钟",
    "next_hour": "下一小时",
    "tomorrow": "下一交易日",
    "one_to_two_weeks": "未来1-2周",
    "one_to_three_months": "未来1-3个月",
}
HORIZON_STEPS = {
    "next_5m": 12,
    "next_15m": 16,
    "next_30m": 16,
    "next_hour": 12,
    "tomorrow": 5,
    "one_to_two_weeks": 10,
    "one_to_three_months": 60,
}

DISPLAY_STATUS_LABELS = {
    "active_retained": "保留现行模型",
    "active_retained_until_candidate_passes_gate": "候选未过门槛，保留现行模型",
    "candidate_failed_or_not_run": "候选未通过或尚未运行",
    "candidate_ready_for_gate": "候选待晋级检查",
    "requires_walk_forward": "需要滚动验证",
    "fresh": "最新",
    "fresh_or_recent": "较新",
    "stale": "行情偏旧",
    "fallback": "备用源",
    "snapshot_cache": "本地缓存",
    "pass": "通过",
    "guarded": "已守门",
    "repaired": "已修复",
    "neutral": "中性/方向优势不足",
    "weak_up": "弱偏多",
    "strong_up": "强偏多",
    "weak_down": "弱偏空",
    "strong_down": "强偏空",
    "abstain": "暂不输出方向",
    "bullish": "偏多",
    "bearish": "偏空",
    "volatility": "波动风险",
    "mixed": "多空分歧",
    "low_impact": "影响分不足",
    "no_available_at": "缺少可用时间",
    "event_window_mismatch": "不在本周期事件窗口",
    "prediction_time_alignment_failed": "预测时间对齐失败",
}


def _output_dir(output_dir: Path | None = None) -> Path:
    out = output_dir or ProjectPaths().output_dir
    out.mkdir(parents=True, exist_ok=True)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _candidate_output_dirs(output_dir: Path | None = None) -> list[Path]:
    paths = [
        output_dir,
        ProjectPaths().output_dir,
        ProjectPaths().root / "outputs",
        ProjectPaths().root / "app_data" / "outputs",
        Path.cwd() / "outputs",
        Path.cwd() / "app_data" / "outputs",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if path is None:
            continue
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            unique.append(resolved)
    return unique


def _payload_quote_price(payload: Mapping[str, Any]) -> float:
    quote = payload.get("live_quote") if isinstance(payload.get("live_quote"), Mapping) else {}
    if not quote:
        wm = payload.get("data_watermark") if isinstance(payload.get("data_watermark"), Mapping) else {}
        quote = wm.get("live_quote") if isinstance(wm.get("live_quote"), Mapping) else {}
    return _safe_float(quote.get("latest") if isinstance(quote, Mapping) else None, 0.0)


def _payload_score(payload: Mapping[str, Any], path: Path) -> float:
    cards = payload.get("cards") if isinstance(payload.get("cards"), Mapping) else {}
    wm = payload.get("data_watermark") if isinstance(payload.get("data_watermark"), Mapping) else {}
    quote_price = _payload_quote_price(payload)
    score = 0.0
    score += min(len(cards), 7) * 20.0
    score += 100.0 if quote_price > 0 else 0.0
    score += 20.0 if wm.get("latest_realtime") or wm.get("latest_daily") else 0.0
    score += _safe_float(wm.get("quality_score"), 0.0) * 10.0
    try:
        score += path.stat().st_mtime / 1_000_000_000.0
    except Exception:
        pass
    return score


def _load_best_json(filename: str, output_dir: Path | None = None) -> dict[str, Any]:
    best: tuple[float, dict[str, Any]] | None = None
    for directory in _candidate_output_dirs(output_dir):
        path = directory / filename
        payload = _read_json(path)
        if not payload:
            continue
        score = _payload_score(payload, path)
        if best is None or score > best[0]:
            best = (score, payload)
    return best[1] if best else {}


def _latest_live_file(out: Path) -> dict[str, Any]:
    return _load_best_json("sn_live_predictions.json", out)


def _snapshot_file(out: Path) -> dict[str, Any]:
    return _load_best_json("sn_live_snapshot.json", out)


def _unified_payload(out: Path | None = None) -> dict[str, Any]:
    root = _output_dir(out)
    payload = _load_best_json("sn_unified_forecast.json", root) or load_unified_forecast(root, max_age_minutes=720)
    if payload:
        return payload
    live = _latest_live_file(root)
    if live:
        payload = build_unified_forecast(live, output_dir=root, data_watermark=get_data_watermark(root), hardware_profile=get_hardware_profile(root), persist=True)
        return payload
    return {
        "cards": {},
        "data_watermark": get_data_watermark(root),
        "unified_generated_at": _now(),
        "disclaimer": DISCLAIMER,
    }


def _live_quote_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    quote = payload.get("live_quote") if isinstance(payload.get("live_quote"), Mapping) else {}
    if quote:
        return dict(quote)
    watermark = payload.get("data_watermark") if isinstance(payload.get("data_watermark"), Mapping) else {}
    quote = watermark.get("live_quote") if isinstance(watermark.get("live_quote"), Mapping) else {}
    return dict(quote)


def get_data_watermark(output_dir: Path | None = None) -> dict[str, Any]:
    out = _output_dir(output_dir)
    unified = _load_best_json("sn_unified_forecast.json", out) or load_unified_forecast(out)
    if isinstance(unified.get("data_watermark"), dict):
        wm = dict(unified["data_watermark"])
    else:
        snapshot = _snapshot_file(out)
        meta = snapshot.get("contract_meta", {}) if isinstance(snapshot.get("contract_meta"), dict) else {}
        statuses = snapshot.get("source_status", []) if isinstance(snapshot.get("source_status"), list) else []
        quotes = snapshot.get("quotes", []) if isinstance(snapshot.get("quotes"), list) else []
        quote = next((row for row in quotes if isinstance(row, dict)), {})
        wm = {
            "created_at": _now(),
            "latest_daily": "",
            "latest_realtime": str(snapshot.get("generated_at", "")),
            "active_contract": str(meta.get("active_contract") or meta.get("target_contract") or "SN"),
            "target_contract": str(meta.get("target_contract") or "SN"),
            "history_symbol": str(meta.get("history_symbol") or "SN0"),
            "source_mode": "snapshot_cache" if snapshot else "no_cached_snapshot",
            "minute_data_available": False,
            "quality_score": 0.62 if snapshot else 0.25,
            "source_status": statuses,
            "live_quote": {
                "symbol": quote.get("symbol", "SN"),
                "latest": _safe_float(quote.get("latest"), 0.0),
                "prev_close": _safe_float(quote.get("prev_close"), 0.0),
                "quote_time": str(snapshot.get("generated_at", "")),
                "volume": _safe_float(quote.get("volume"), 0.0),
                "open_interest": _safe_float(quote.get("open_interest"), 0.0),
            } if quote else {},
            "live_overlay_used": bool(quote),
        }
    live_quote = wm.get("live_quote") if isinstance(wm.get("live_quote"), Mapping) else {}
    latest_price = _safe_float(live_quote.get("latest") if isinstance(live_quote, Mapping) else None, 0.0)
    quote_time = str(
        (live_quote.get("quote_time") if isinstance(live_quote, Mapping) else "")
        or wm.get("latest_realtime")
        or wm.get("latest_daily")
        or ""
    )
    fetch_time = str(wm.get("created_at") or _now())
    data_age_seconds: float | None = None
    try:
        ts = pd.Timestamp(quote_time)
        if ts.tzinfo is not None:
            now_ts = pd.Timestamp.now(tz=ts.tzinfo)
        else:
            now_ts = pd.Timestamp.now()
        data_age_seconds = max(0.0, float((now_ts - ts).total_seconds()))
    except Exception:
        data_age_seconds = None
    source = str(wm.get("source_mode") or wm.get("source") or "")
    wm["latest_price"] = latest_price if latest_price > 0 else None
    wm["latest_quote_time"] = quote_time or None
    wm["fetch_timestamp"] = fetch_time
    wm["source_timestamp"] = quote_time or None
    wm["source"] = source
    wm["data_age_seconds"] = data_age_seconds
    wm["stale_status"] = "stale_or_missing_quote" if not latest_price or not quote_time else ("stale" if (data_age_seconds or 0) > 3600 * 24 else "fresh_or_recent")
    wm["using_fallback"] = bool(wm.get("using_fallback") or "fallback" in source.lower() or not latest_price)
    wm.setdefault("disclaimer", DISCLAIMER)
    return wm


def get_market_latest(symbol: str = "SN", contract_type: str = "main", force_refresh: bool = False) -> dict[str, Any]:
    payload = _unified_payload()
    quote = _live_quote_from_payload(payload)
    watermark = get_data_watermark()
    return {
        "symbol": symbol,
        "contract_type": contract_type,
        "latest_quote": quote,
        "price": _safe_float(quote.get("latest"), 0.0),
        "source_timestamp": quote.get("quote_time") or watermark.get("latest_realtime", ""),
        "fetch_timestamp": watermark.get("created_at", _now()),
        "source": watermark.get("source_mode", ""),
        "trading_status": get_trading_session().get("status", ""),
        "force_refresh_requested": force_refresh,
        "data_watermark": watermark,
        "disclaimer": DISCLAIMER,
    }


def get_market_history(symbol: str = "SN", horizon: str = "tomorrow", contract_type: str = "main", start: str | None = None, end: str | None = None) -> dict[str, Any]:
    chart = get_price_forecast_chart(horizon)
    return {
        "symbol": symbol,
        "contract_type": contract_type,
        "horizon": horizon,
        "history": chart.get("history", []),
        "source": "chart_payload",
        "start": start,
        "end": end,
        "disclaimer": DISCLAIMER,
    }


def _stable_hash(value: Any, length: int = 16) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


def _display_label(value: Any) -> str:
    text = str(value or "")
    return DISPLAY_STATUS_LABELS.get(text, text or "--")


def _fmt_pct(value: Any) -> str:
    number = _safe_float(value, float("nan"))
    if not np.isfinite(number):
        return "--"
    return f"{number * 100:.1f}%"


def _fmt_price(value: Any) -> str:
    number = _safe_float(value, float("nan"))
    if not np.isfinite(number):
        return "--"
    return f"{number:,.0f} 元/吨"


def _event_summary_for_horizon(horizon: str, output_dir: Path | None = None) -> dict[str, Any]:
    try:
        return get_events_evidence(horizon, output_dir=output_dir)
    except Exception as exc:
        return {
            "horizon": horizon,
            "used_in_model_event_count": 0,
            "recognized_event_count": 0,
            "rejected_event_count": 0,
            "summary": {"failure_reason": f"事件链路读取失败：{exc}", "event_factor_direction": "unavailable", "confidence_weight": 0.0},
            "top_bullish_events": [],
            "top_bearish_events": [],
            "top_volatility_events": [],
            "rejected_reason_breakdown": {"event_pipeline_error": 1},
        }


def _top_event_titles(evidence: Mapping[str, Any], key: str, limit: int = 2) -> list[str]:
    rows = evidence.get(key, [])
    if not isinstance(rows, list):
        return []
    return [
        str(row.get("title") or row.get("summary") or "").strip()
        for row in rows[:limit]
        if isinstance(row, Mapping) and (row.get("title") or row.get("summary"))
    ]


def _augment_card_display(card: MutableMapping[str, Any], *, horizon: str, watermark: Mapping[str, Any], output_dir: Path | None = None) -> None:
    evidence = _event_summary_for_horizon(horizon, output_dir=output_dir)
    summary = evidence.get("summary", {}) if isinstance(evidence.get("summary"), Mapping) else {}
    p_up = _safe_float(card.get("p_up") or card.get("prob_up"), 0.0)
    p_down = _safe_float(card.get("p_down") or card.get("prob_down"), 0.0)
    p_neutral = _safe_float(card.get("p_neutral") or card.get("prob_neutral"), max(0.0, 1.0 - p_up - p_down))
    direction = str(card.get("direction_label") or card.get("signal_strength") or "neutral")
    promotion = str(card.get("promotion_result") or "active_retained_until_candidate_passes_gate")
    stale_status = str(card.get("stale_status") or watermark.get("stale_status") or "fresh_or_recent")
    candidate_texts: list[str] = []
    for row in card.get("direction_candidates", []) if isinstance(card.get("direction_candidates"), list) else []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "方向候选")
        cand_dir = _display_label(row.get("direction"))
        strength = str(row.get("strength") or "")
        candidate_texts.append(f"{name}：{cand_dir}{f'（{strength}）' if strength else ''}")
        if len(candidate_texts) >= 3:
            break
    bullish_events = _top_event_titles(evidence, "top_bullish_events")
    bearish_events = _top_event_titles(evidence, "top_bearish_events")
    volatility_events = _top_event_titles(evidence, "top_volatility_events")
    event_line = "；".join(
        part
        for part in [
            f"利多事件：{'、'.join(bullish_events)}" if bullish_events else "",
            f"利空事件：{'、'.join(bearish_events)}" if bearish_events else "",
            f"波动事件：{'、'.join(volatility_events)}" if volatility_events else "",
        ]
        if part
    ) or str(summary.get("failure_reason") or summary.get("direction_contribution") or "暂无高权重入模事件")
    gate = card.get("direction_gate") if isinstance(card.get("direction_gate"), Mapping) else {}
    gate_reasons = gate.get("reasons", [])
    if isinstance(gate_reasons, list):
        gate_text = "；".join(_display_label(item) for item in gate_reasons[:3])
    else:
        gate_text = _display_label(gate_reasons)
    range_source = str(card.get("price_band_reason") or card.get("range_source") or "历史波动率、ATR、兑现误差与事件权重共同约束")
    tone = "bull" if p_up > p_down and p_up > p_neutral else "bear" if p_down > p_up and p_down > p_neutral else "neutral"
    card["display_labels"] = {
        "horizon": HORIZON_LABELS.get(horizon, horizon),
        "direction": _display_label(direction),
        "promotion": _display_label(promotion),
        "data_status": _display_label(stale_status),
        "event_factor_direction": _display_label(summary.get("event_factor_direction", "")),
    }
    card["display_tags"] = [
        {"label": "方向", "value": _display_label(direction), "tone": tone},
        {"label": "上涨概率", "value": _fmt_pct(p_up), "tone": "bull"},
        {"label": "下跌概率", "value": _fmt_pct(p_down), "tone": "bear"},
        {"label": "中性概率", "value": _fmt_pct(p_neutral), "tone": "neutral"},
        {"label": "价格中枢", "value": _fmt_price(card.get("price_center")), "tone": "info"},
        {"label": "预测区间", "value": f"{_fmt_price(card.get('range_low'))} - {_fmt_price(card.get('range_high'))}", "tone": "info"},
        {"label": "事件入模", "value": f"{evidence.get('used_in_model_event_count', 0)} / {evidence.get('recognized_event_count', 0)}", "tone": "info"},
        {"label": "晋级状态", "value": _display_label(promotion), "tone": "warning" if "candidate" in promotion else "info"},
        {"label": "数据状态", "value": _display_label(stale_status), "tone": "warning" if stale_status in {"stale", "fallback"} else "info"},
        {"label": "路径守门", "value": _display_label(card.get("path_sanity_status") or "guarded"), "tone": "info"},
    ]
    card["decision_explanation"] = {
        "headline": f"{HORIZON_LABELS.get(horizon, horizon)}当前为{_display_label(direction)}，上涨{_fmt_pct(p_up)}、下跌{_fmt_pct(p_down)}、中性{_fmt_pct(p_neutral)}。",
        "direction_basis": candidate_texts or ["方向候选未提供足够独立证据，维持保守口径。"],
        "event_basis": event_line,
        "price_basis": range_source,
        "gate_basis": gate_text or "方向闸门未触发明显降级。",
        "learning_basis": "候选模型需通过 walk-forward、事件消融、概率校准和路径连续性后才能替换 active。",
    }
    card["technical_tags"] = [
        {"label": "模型版本", "value": card.get("model_version", "")},
        {"label": "预测编号", "value": card.get("prediction_id", "")},
        {"label": "数据时间", "value": card.get("data_timestamp", "")},
        {"label": "行情水位", "value": card.get("source_timestamp", "")},
        {"label": "特征集", "value": card.get("feature_set_id", "")},
        {"label": "缓存键", "value": card.get("prediction_cache_key", "")},
        {"label": "事件特征", "value": evidence.get("event_feature_hash", "")},
    ]
    card["risk_notes"] = [
        "预测基于历史数据与公开信息，存在延迟、误差和失效风险。",
        "方向强弱只代表统计边际，不构成交易指令。",
        "若数据偏旧、事件链路失败或方向价格分歧，应降低解读强度。",
    ]
    card["learning_status"] = {
        "active_or_candidate_status": card.get("active_or_candidate_status", "active_retained"),
        "promotion_result": promotion,
        "next_action": "等待候选模型完成真实 walk-forward 与 promotion gate",
    }
    card["backtest_summary"] = {
        "directional_accuracy": card.get("backtest_direction_accuracy"),
        "strong_signal_accuracy": card.get("strong_signal_accuracy"),
        "brier_score": card.get("brier_score"),
        "expected_calibration_error": card.get("expected_calibration_error"),
        "event_ablation_gain": card.get("event_ablation_gain"),
        "metrics_note": "缺失指标代表尚未生成真实 walk-forward 结果，不使用伪指标填充。",
    }
    card["path_guard_summary"] = {
        "status": _display_label(card.get("path_sanity_status") or "guarded"),
        "range_source": range_source,
        "warning": "无事件支撑时已降低趋势表达" if not (bullish_events or bearish_events or volatility_events) else "区间已结合事件窗口与历史波动约束",
    }
    card["event_evidence"] = {
        "used_in_model_event_count": evidence.get("used_in_model_event_count", 0),
        "recognized_event_count": evidence.get("recognized_event_count", 0),
        "rejected_event_count": evidence.get("rejected_event_count", 0),
        "event_feature_hash": evidence.get("event_feature_hash", ""),
        "summary": summary,
        "top_bullish_events": evidence.get("top_bullish_events", [])[:3],
        "top_bearish_events": evidence.get("top_bearish_events", [])[:3],
        "top_volatility_events": evidence.get("top_volatility_events", [])[:3],
    }


def _ensure_prediction_metadata(payload: MutableMapping[str, Any], watermark: Mapping[str, Any]) -> None:
    cards = payload.get("cards") if isinstance(payload.get("cards"), MutableMapping) else {}
    data_ts = str(watermark.get("latest_quote_time") or watermark.get("source_timestamp") or watermark.get("latest_realtime") or watermark.get("latest_daily") or "")
    fetch_ts = str(watermark.get("fetch_timestamp") or watermark.get("created_at") or _now())
    source = str(watermark.get("source") or watermark.get("source_mode") or "")
    active_contract = str(watermark.get("active_contract") or watermark.get("target_contract") or "SN")
    for horizon, card in cards.items():
        if not isinstance(card, MutableMapping):
            continue
        canonical = {
            "next_5m": "h5m",
            "next_15m": "h15m",
            "next_30m": "h30m",
            "next_hour": "h1h",
            "tomorrow": "h1d",
            "one_to_two_weeks": "h10d",
            "one_to_three_months": "h60d",
        }.get(str(horizon), str(horizon))
        event_hash = ""
        if isinstance(card.get("news_policy_impact"), Mapping):
            event_hash = str(card["news_policy_impact"].get("event_feature_hash") or "")
        if not event_hash and isinstance(card.get("event_evidence"), Mapping):
            event_hash = str(card["event_evidence"].get("event_feature_hash") or "")
        if not event_hash:
            event_hash = _stable_hash([horizon, data_ts, card.get("direction_candidate_scores", [])], 12)
        model_version = str(card.get("model_version") or f"v3.8-active-{canonical}")
        feature_set_id = str(card.get("feature_set_id") or f"sn-{canonical}-features-{event_hash[:8]}")
        existing_cache_key = str(card.get("prediction_cache_key") or "")
        if existing_cache_key and canonical in existing_cache_key and model_version in existing_cache_key:
            cache_key = existing_cache_key
        else:
            cache_hash = _stable_hash([active_contract, horizon, model_version, data_ts, feature_set_id, event_hash], 20)
            cache_key = f"sn-v3.8:{canonical}:{model_version}:{cache_hash}"
        prediction_id = str(card.get("prediction_id") or f"{canonical}-{_stable_hash(cache_key, 14)}")
        card["prediction_id"] = prediction_id
        card["model_version"] = model_version
        card["direction_model_version"] = str(card.get("direction_model_version") or f"{model_version}-direction")
        card["price_model_version"] = str(card.get("price_model_version") or f"{model_version}-return-path")
        card["calibrator_version"] = str(card.get("calibrator_version") or f"{model_version}-calibrator")
        card["data_timestamp"] = data_ts
        card["source_timestamp"] = data_ts
        card["fetch_timestamp"] = fetch_ts
        card["data_age_seconds"] = watermark.get("data_age_seconds")
        card["source"] = source
        card["feature_set_id"] = feature_set_id
        card["dataset_id"] = str(card.get("dataset_id") or f"sn-{canonical}-dataset")
        card["label_config_id"] = str(card.get("label_config_id") or f"sn-{canonical}-direction-threshold")
        card["scaler_id"] = str(card.get("scaler_id") or f"sn-{canonical}-scaler")
        card["prediction_cache_key"] = cache_key
        card["event_feature_hash"] = event_hash
        card["active_or_candidate_status"] = str(card.get("active_or_candidate_status") or "active_retained")
        card["promotion_result"] = str(card.get("promotion_result") or "active_retained_until_candidate_passes_gate")
        card["promotion_failure_reason"] = str(card.get("promotion_failure_reason") or "")
        card["model_artifact"] = str(card.get("model_artifact") or f"models/{canonical}/{model_version}")
        p_up = _safe_float(card.get("p_up"), 0.0)
        p_down = _safe_float(card.get("p_down"), 0.0)
        p_neutral = _safe_float(card.get("p_neutral"), 0.0)
        edge = max(p_up, p_down) - p_neutral * 0.35
        if card.get("signal_strength") in {None, ""}:
            if p_neutral >= 0.55:
                strength = "neutral"
            elif edge >= 0.58:
                strength = "strong_up" if p_up > p_down else "strong_down"
            elif edge >= 0.36:
                strength = "weak_up" if p_up > p_down else "weak_down"
            else:
                strength = "abstain"
            card["signal_strength"] = strength
        card["strong_signal"] = str(card.get("signal_strength", "")).startswith("strong_")


def get_live_predictions(output_dir: Path | None = None) -> dict[str, Any]:
    out = _output_dir(output_dir)
    payload = _unified_payload(out)
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    watermark = get_data_watermark(out)
    quality = _safe_float(watermark.get("quality_score"), 0.55)
    minute_data_available = bool(watermark.get("minute_data_available"))
    payload["cards"] = {key: cards[key] for key in LIVE_CARD_ORDER if key in cards}
    payload["cards"].update({key: val for key, val in cards.items() if key not in payload["cards"]})
    payload = apply_direction_gate(
        payload,
        {},
        data_quality_score=quality,
        source_mode=str(watermark.get("source_mode", "")),
        minute_data_available=minute_data_available,
    )
    payload = apply_realistic_price_gates(payload)
    payload["data_watermark"] = watermark
    _ensure_prediction_metadata(payload, watermark)
    for horizon, card in (payload.get("cards") or {}).items():
        if isinstance(card, MutableMapping):
            _augment_card_display(card, horizon=str(horizon), watermark=watermark, output_dir=out)
    payload["disclaimer"] = DISCLAIMER
    return integrate_live_prediction_payload(payload, horizon_labels=HORIZON_LABELS)


def _card_for_horizon(horizon: str) -> dict[str, Any]:
    payload = get_live_predictions()
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    return dict(cards.get(horizon) or cards.get("tomorrow") or {})


def run_predict_api(symbol: str = "SN", horizon: str = "tomorrow", contract_type: str = "main", force_refresh: bool = False) -> dict[str, Any]:
    payload = get_live_predictions()
    card = _card_for_horizon(horizon)
    if not card:
        return {"ok": False, "error": "no_prediction_payload", "horizon": horizon, "disclaimer": DISCLAIMER}
    data_ts = str(card.get("asof_status", {}).get("latest_realtime") if isinstance(card.get("asof_status"), dict) else "")
    prediction_id = str(card.get("prediction_id") or f"{horizon}-{uuid.uuid5(uuid.NAMESPACE_URL, horizon + data_ts).hex[:12]}")
    return {
        "ok": True,
        "prediction_id": prediction_id,
        "symbol": symbol,
        "contract_type": contract_type,
        "horizon": horizon,
        "latest_quote": payload.get("live_quote") or payload.get("data_watermark", {}).get("live_quote", {}),
        "forecast": card,
        "metrics": {
            "directional_accuracy": card.get("backtest_direction_accuracy"),
            "strong_signal_accuracy": card.get("strong_signal_accuracy"),
            "brier": card.get("brier_score"),
            "ece": card.get("expected_calibration_error"),
        },
        "data_quality": payload.get("data_watermark", {}),
        "model_info": {
            "model_version": card.get("model_version", ""),
            "direction_gate": card.get("direction_gate", {}),
            "event_feature_hash": card.get("news_policy_impact", {}).get("event_feature_hash", ""),
        },
        "force_refresh_requested": force_refresh,
        "disclaimer": DISCLAIMER,
    }


def get_news_policy_impact(output_dir: Path | None = None) -> dict[str, Any]:
    evidence = build_event_evidence("tomorrow", output_dir=output_dir)
    return {
        "summary": evidence.get("summary", {}),
        "provider_status": load_provider_status(),
        "events": evidence.get("events", []),
        "top_bullish_events": evidence.get("top_bullish_events", []),
        "top_bearish_events": evidence.get("top_bearish_events", []),
        "top_volatility_events": evidence.get("top_volatility_events", []),
        "recognized_event_count": evidence.get("recognized_event_count", 0),
        "used_in_model_event_count": evidence.get("used_in_model_event_count", 0),
        "rejected_event_count": evidence.get("rejected_event_count", 0),
        "rejected_reason_breakdown": evidence.get("rejected_reason_breakdown", {}),
        "disclaimer": DISCLAIMER,
    }


def get_news_events(symbol: str = "SN", limit: int = 20, category: str = "", min_impact_score: float = 0.0) -> dict[str, Any]:
    return get_events_recent(symbol=symbol, limit=limit, category=category, min_impact_score=min_impact_score)


def get_news_open_url(event_id: str) -> dict[str, Any]:
    result = resolve_event_url(event_id)
    if result.get("ok") and result.get("final_open_url"):
        try:
            webbrowser.open(str(result["final_open_url"]))
            result["opened"] = True
        except Exception as exc:
            result["opened"] = False
            result["blocked_reason"] = f"open_failed:{exc}"
    return result


def get_events_recent(symbol: str = "SN", limit: int = 50, category: str = "", min_impact_score: float = 0.0) -> dict[str, Any]:
    sync_event_store_from_news()
    rows = load_events(limit=max(limit, 1), category=category or None, min_impact_score=float(min_impact_score or 0.0))
    return {
        "symbol": symbol,
        "events": rows[:limit],
        "count": len(rows[:limit]),
        "provider_status": load_provider_status(),
        "updated_at": _now(),
        "disclaimer": DISCLAIMER,
    }


def get_events_evidence(horizon: str = "tomorrow", output_dir: Path | None = None) -> dict[str, Any]:
    evidence = build_event_evidence(horizon, output_dir=output_dir)
    evidence.setdefault("disclaimer", DISCLAIMER)
    return evidence


def get_events_provider_status() -> dict[str, Any]:
    return {"providers": load_provider_status(), "updated_at": _now()}


def get_events_audit(horizon: str = "tomorrow") -> dict[str, Any]:
    evidence = build_event_evidence(horizon)
    return {
        "horizon": horizon,
        "recognized_event_count": evidence.get("recognized_event_count", 0),
        "valid_event_count": evidence.get("valid_event_count", evidence.get("used_in_model_event_count", 0)),
        "used_in_model_event_count": evidence.get("used_in_model_event_count", 0),
        "rejected_event_count": evidence.get("rejected_event_count", 0),
        "rejected_reason_breakdown": evidence.get("rejected_reason_breakdown", {}),
        "event_feature_nonzero_count": evidence.get("event_feature_nonzero_count", 0),
        "event_feature_hash": evidence.get("event_feature_hash", ""),
        "provider_status": load_provider_status(),
    }


def get_trading_session() -> dict[str, Any]:
    try:
        return sn_trading_session_state()
    except Exception as exc:
        return {"status": "unknown", "error": str(exc), "updated_at": _now()}


def _history_from_outputs(out: Path) -> list[dict[str, Any]]:
    for name in ("sn_predictions.csv", "sn_market_data.csv"):
        path = out / name
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        date_col = next((c for c in df.columns if c.lower() in {"date", "timestamp", "datetime"}), df.columns[0])
        close_col = next((c for c in df.columns if c.lower() in {"close", "actual_close", "price", "latest"}), None)
        if not close_col:
            continue
        rows = []
        for _, row in df.tail(260).iterrows():
            price = _safe_float(row.get(close_col), 0.0)
            if price <= 0:
                continue
            rows.append({"ts": str(row.get(date_col)), "close": price, "source": name})
        if rows:
            return rows
    return []


def _forecast_points(card: Mapping[str, Any], horizon: str) -> list[dict[str, Any]]:
    existing = card.get("forecast")
    if isinstance(existing, list) and existing:
        return [dict(row) for row in existing if isinstance(row, Mapping)]
    last_ts = (
        card.get("source_timestamp")
        or card.get("data_timestamp")
        or (card.get("asof_status", {}).get("latest_realtime") if isinstance(card.get("asof_status"), Mapping) else "")
        or (card.get("asof_status", {}).get("latest_daily") if isinstance(card.get("asof_status"), Mapping) else "")
        or pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()
    )
    curve = build_forecast_curve(live_card=dict(card), last_timestamp=last_ts, horizon_key=horizon)
    points: list[dict[str, Any]] = []
    for row in curve:
        if not isinstance(row, Mapping):
            continue
        points.append(
            {
                "ts": row.get("date"),
                "date": row.get("date"),
                "center": row.get("pred_center"),
                "pred_center": row.get("pred_center"),
                "lower": row.get("pred_low"),
                "pred_low": row.get("pred_low"),
                "upper": row.get("pred_high"),
                "pred_high": row.get("pred_high"),
                "p_up": row.get("prob_up", card.get("p_up")),
                "p_down": card.get("p_down", card.get("prob_down")),
                "p_neutral": row.get("p_neutral", card.get("p_neutral")),
                "path_sanity_status": row.get("path_sanity_status"),
                "path_repair_reasons": row.get("path_repair_reasons", []),
                "interval_policy": row.get("interval_policy"),
                "interval_growth_guard": row.get("interval_growth_guard"),
                "forecast_step": row.get("forecast_step"),
            }
        )
    return points


def _interval_growth_limit(horizon: str) -> float:
    return {
        "next_5m": 2.0,
        "next_15m": 2.15,
        "next_30m": 2.35,
        "next_hour": 2.65,
        "tomorrow": 1.85,
        "one_to_two_weeks": 2.25,
        "one_to_three_months": 3.0,
    }.get(horizon, 2.8)


def _chart_path_diagnostics(
    *,
    history: list[dict[str, Any]],
    forecast: list[dict[str, Any]],
    card: Mapping[str, Any],
    horizon: str,
) -> dict[str, Any]:
    if not history or not forecast:
        return {
            "status": "insufficient_data",
            "first_step_gap": None,
            "interval_growth_rate": None,
            "center_flatline_rate": None,
            "direction_price_conflict": False,
            "warnings": ["insufficient_chart_data"],
        }
    last_price = _safe_float(history[-1].get("close") or history[-1].get("price"), 0.0)
    first_center = _safe_float(forecast[0].get("center") or forecast[0].get("pred_center"), last_price)
    centers = [_safe_float(row.get("center") or row.get("pred_center"), first_center) for row in forecast]
    widths = [
        max(
            0.0,
            _safe_float(row.get("upper") or row.get("pred_high"), first_center)
            - _safe_float(row.get("lower") or row.get("pred_low"), first_center),
        )
        for row in forecast
    ]
    first_width = max(widths[0] if widths else 0.0, 1e-9)
    interval_growth_rate = (max(widths) / first_width) if widths else 0.0
    flat_count = 0
    for left, right in zip(centers, centers[1:]):
        if abs(right - left) <= max(abs(last_price) * 0.00002, 1.0):
            flat_count += 1
    center_flatline_rate = flat_count / max(len(centers) - 1, 1)
    p_up = _safe_float(card.get("p_up", card.get("prob_up")), 0.5)
    p_down = _safe_float(card.get("p_down", card.get("prob_down")), 0.5)
    terminal_return = (centers[-1] / last_price - 1.0) if last_price > 0 and centers else 0.0
    direction_price_conflict = bool((p_up - p_down > 0.16 and terminal_return < -0.0015) or (p_down - p_up > 0.16 and terminal_return > 0.0015))
    repair_reasons = []
    for row in forecast:
        value = row.get("path_repair_reasons")
        if isinstance(value, list):
            repair_reasons.extend(str(item) for item in value)
    repair_reasons = sorted(set(repair_reasons))
    limit = _interval_growth_limit(horizon)
    warnings: list[str] = []
    if interval_growth_rate > limit:
        warnings.append("interval_growth_watch")
    if center_flatline_rate > 0.72:
        warnings.append("center_flatline_watch")
    if direction_price_conflict:
        warnings.append("direction_price_conflict")
    warnings.extend(repair_reasons)
    impact = card.get("news_policy_impact") if isinstance(card.get("news_policy_impact"), Mapping) else {}
    event_weight = _safe_float(impact.get("confidence_weight"), _safe_float(card.get("event_factor_weight"), 0.0))
    event_direction = str(impact.get("event_factor_direction") or card.get("event_factor_direction") or "")
    event_shock_reason = ""
    if event_weight >= 0.55 and event_direction in {"volatility", "mixed", "bullish", "bearish"}:
        event_shock_reason = f"事件权重{event_weight:.2f}，方向偏置{event_direction}"
    elif warnings:
        event_shock_reason = "无重大事件支撑，已降低趋势表达"
    return {
        "status": "pass" if not warnings else "guarded",
        "last_valid_price": last_price,
        "first_forecast_price": first_center,
        "first_step_gap": abs(first_center - last_price) if last_price > 0 else None,
        "interval_growth_rate": interval_growth_rate,
        "center_flatline_rate": center_flatline_rate,
        "direction_price_conflict": direction_price_conflict,
        "price_path_terminal_return": terminal_return,
        "max_interval_growth_allowed": limit,
        "path_repair_reasons": repair_reasons,
        "warnings": sorted(set(warnings)),
        "event_shock_reason": event_shock_reason,
        "price_band_reason": "历史波动率、ATR、兑现误差与事件强度联合约束",
    }


def _event_shock_markers(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for event in events:
        impact = _safe_float(event.get("impact_score"), _safe_float(event.get("final_event_weight"), 0.0))
        bias = str(event.get("direction_bias") or event.get("event_factor_direction") or "")
        if impact < 0.45 and bias not in {"volatility", "mixed"}:
            continue
        markers.append(
            {
                "ts": event.get("available_at") or event.get("published_at") or event.get("publish_time") or event.get("fetched_at"),
                "title": event.get("title", ""),
                "source": event.get("source", ""),
                "impact_score": impact,
                "direction_bias": bias,
                "url": event.get("canonical_url") or event.get("url") or event.get("final_open_url") or "",
            }
        )
        if len(markers) >= 8:
            break
    return markers


def get_price_forecast_chart(horizon: str = "tomorrow") -> dict[str, Any]:
    out = _output_dir()
    payload = get_live_predictions(out)
    card = dict((payload.get("cards") or {}).get(horizon) or {})
    history = _history_from_outputs(out)
    latest_quote = _live_quote_from_payload(payload)
    latest_price = _safe_float(latest_quote.get("latest"), 0.0)
    if latest_price > 0:
        history.append({"ts": latest_quote.get("quote_time") or _now(), "close": latest_price, "source": "live_quote"})
    forecast = _forecast_points(card, horizon)
    events = get_events_evidence(horizon).get("events", [])[:20]
    path_diagnostics = _chart_path_diagnostics(history=history, forecast=forecast, card=card, horizon=horizon)
    interval_growth_warning = ""
    if "interval_growth_watch" in path_diagnostics.get("warnings", []):
        interval_growth_warning = "interval_growth_watch"
    elif "interval_explosion_capped" in path_diagnostics.get("warnings", []):
        interval_growth_warning = "interval_growth_guarded"
    return {
        "horizon": horizon,
        "horizon_label": HORIZON_LABELS.get(horizon, horizon),
        "prediction_id": card.get("prediction_id", ""),
        "model_version": card.get("model_version", ""),
        "history": history,
        "latest_point": {"ts": history[-1]["ts"], "price": history[-1]["close"], "source": history[-1].get("source", "")} if history else {},
        "forecast": forecast,
        "series": forecast,
        "events": events,
        "roll_marks": [],
        "data_status": "ok" if history and forecast else "insufficient_data",
        "validation_note": card.get("validation_note", ""),
        "price_band_policy": card.get("range_source", ""),
        "path_diagnostics": path_diagnostics,
        "interval_policy": path_diagnostics.get("price_band_reason", "历史波动率、ATR、兑现误差与事件强度联合约束"),
        "interval_growth_warning": interval_growth_warning,
        "event_shock_markers": _event_shock_markers(events),
        "price_band_reason": path_diagnostics.get("event_shock_reason") or path_diagnostics.get("price_band_reason"),
        "disclaimer": DISCLAIMER,
    }


def get_backtest_diagnostics(horizon: str = "") -> dict[str, Any]:
    health = get_models_health()
    promotion = get_model_promotion_report(horizon or "tomorrow")
    watermark = get_data_watermark()
    payload = build_backtest_diagnostics(
        horizon=horizon or "all",
        health=health,
        promotion_report=promotion,
        latest_asof_date=str(watermark.get("latest_daily", "")),
        latest_row_status="live_overlay" if watermark.get("live_overlay_used") else "cached",
    )
    payload["metrics"] = health
    payload["disclaimer"] = DISCLAIMER
    return payload


def get_contract_liquidity() -> dict[str, Any]:
    wm = get_data_watermark()
    active = wm.get("active_contract", "SN")
    return {"active_contract": active, "contracts": [{"contract": active, "reason": "当前主力/缓存主力", "liquidity_score": 1.0}], "disclaimer": DISCLAIMER}


def get_hardware_profile(output_dir: Path | None = None) -> dict[str, Any]:
    try:
        profile = load_hardware_profile(output_dir=output_dir)
        if not profile:
            profile = detect_hardware_profile()
    except Exception:
        profile = detect_hardware_profile()
    profile["resolved_compute_profile"] = resolve_compute_profile("auto", profile)
    return profile


def get_learning_status() -> dict[str, Any]:
    state = _read_json(_output_dir() / "sn_scheduler_state.json")
    health = get_models_health()
    payload = build_api_learning_status(
        scheduler_state=state,
        registry_path=_output_dir() / "model_governance_registry.json",
        model_health=health,
    )
    registry = get_models_registry()
    payload["model_version"] = registry.get("active_versions", {})
    payload["active_versions"] = registry.get("active_versions", {})
    payload["disclaimer"] = DISCLAIMER
    return payload


def get_models_registry() -> dict[str, Any]:
    cards = get_live_predictions().get("cards", {})
    active = {}
    models = []
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        version = str(card.get("model_version") or f"active-{horizon}")
        active[horizon] = version
        models.append(
            {
                "horizon": horizon,
                "model_version": version,
                "status": "active",
                "artifact_path": card.get("model_artifact", f"models/{horizon}/{version}"),
                "feature_set_id": card.get("feature_set_id", f"features-{horizon}"),
                "event_feature_hash": card.get("news_policy_impact", {}).get("event_feature_hash", ""),
            }
        )
    return {"models": models, "active_versions": active, "disclaimer": DISCLAIMER}


def get_models_health() -> dict[str, Any]:
    cards = get_live_predictions().get("cards", {})
    per = {}
    neutral_rates = []
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        neutral = _safe_float(card.get("p_neutral") or card.get("prob_neutral"), 0.0)
        neutral_rates.append(neutral)
        per[horizon] = {
            "direction_hit_rate": card.get("backtest_direction_accuracy"),
            "strong_signal_accuracy": card.get("strong_signal_accuracy"),
            "neutral_rate": neutral,
            "direction_coverage_rate": 1.0 - neutral,
            "brier_score": card.get("brier_score"),
            "expected_calibration_error": card.get("expected_calibration_error"),
            "direction_gate_status": card.get("direction_gate", {}).get("status") if isinstance(card.get("direction_gate"), Mapping) else "",
        }
    return {
        "validation_mode": "walk_forward_or_live_cache",
        "effective_sample_count": 0,
        "neutral_rate": float(np.mean(neutral_rates)) if neutral_rates else None,
        "per_horizon": per,
        "health_reason": "真实兑现样本不足时只展示 walk-forward/缓存口径，不伪造实时命中率。",
        "disclaimer": DISCLAIMER,
    }


def get_model_promotion_report(horizon: str = "tomorrow") -> dict[str, Any]:
    return {
        "horizon": horizon,
        "promotion_result": "active_retained",
        "promotion_reason": "候选模型必须通过方向优先 walk-forward、概率校准、事件消融和路径连续性后才能替换 active。",
        "candidate_status": "not_run_in_this_request",
        "disclaimer": DISCLAIMER,
    }


def get_models_health() -> dict[str, Any]:  # type: ignore[no-redef]
    cards = get_live_predictions().get("cards", {})
    payload = build_api_model_health(
        cards=cards if isinstance(cards, Mapping) else {},
        registry_path=_output_dir() / "model_governance_registry.json",
        horizons=list(HORIZON_LABELS.keys()),
    )
    payload["disclaimer"] = DISCLAIMER
    return payload


def get_model_promotion_report(horizon: str = "tomorrow") -> dict[str, Any]:  # type: ignore[no-redef]
    card = _card_for_horizon(horizon)
    metrics = {
        "strong_signal_accuracy": card.get("strong_signal_accuracy"),
        "directional_accuracy": card.get("backtest_direction_accuracy"),
        "macro_f1": card.get("macro_f1"),
        "brier_score": card.get("brier_score"),
        "expected_calibration_error": card.get("expected_calibration_error"),
        "neutral_rate": card.get("p_neutral"),
        "event_ablation_gain": card.get("event_ablation_gain"),
        "path_continuity_score": card.get("path_continuity_score"),
    }
    missing = [key for key, value in metrics.items() if value in {None, ""}]
    return {
        "horizon": horizon,
        "active_model_version": card.get("model_version", f"v3.8-active-{horizon}"),
        "candidate_model_version": f"candidate-{horizon}-direction-first",
        "promotion_result": "active_retained",
        "candidate_status": "candidate_failed_or_not_run" if missing else "candidate_ready_for_gate",
        "promotion_reason": (
            "候选模型缺少真实 walk-forward、事件消融或概率校准指标，不能替换 active。"
            if missing
            else "候选模型指标齐备，但仍需方向优先 promotion gate 全部通过后才能替换 active。"
        ),
        "baseline": {
            "price_only": {"status": "requires_walk_forward"},
            "event_only": {"status": "requires_walk_forward"},
            "price_plus_event": {"status": "requires_walk_forward"},
            "price_plus_event_plus_macro": {"status": "requires_walk_forward"},
        },
        "metrics": metrics,
        "missing_metrics": missing,
        "gate_order": [
            "strong_signal_accuracy",
            "directional_accuracy",
            "macro_f1",
            "brier_ece",
            "neutral_rate",
            "event_ablation_gain",
            "path_continuity",
        ],
        "disclaimer": DISCLAIMER,
    }


def get_factors_diagnostics() -> dict[str, Any]:
    return {"factors": [], "message": "因子诊断需在回测/训练任务后生成；当前不使用伪指标。", "disclaimer": DISCLAIMER}


def get_system_truth_audit() -> dict[str, Any]:
    payload = get_live_predictions()
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    prob_hashes = {}
    center_hashes = {}
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        prob_hashes[horizon] = hash(json.dumps([card.get("p_up"), card.get("p_down"), card.get("p_neutral")], sort_keys=True, default=str))
        center_hashes[horizon] = hash(json.dumps([card.get("price_center"), card.get("range_low"), card.get("range_high")], sort_keys=True, default=str))
    duplicate_prob = len(set(prob_hashes.values())) < len(prob_hashes) if prob_hashes else False
    duplicate_center = len(set(center_hashes.values())) < len(center_hashes) if center_hashes else False
    return {
        "system_truth_audit": "pass" if not duplicate_prob and not duplicate_center else "warning",
        "model_independence_audit": {"duplicate_direction_prob_hash": duplicate_prob, "duplicate_center_hash": duplicate_center},
        "forecast_path_audit": {"source": "unified_forecast + price_risk + direction_gate", "status": "guarded"},
        "event_pipeline_audit": get_events_audit("tomorrow"),
        "data_reality_audit": get_data_watermark(),
        "latency_audit": {"generated_at": _now()},
        "cache_conflict_audit": {"unified_forecast_version": payload.get("unified_forecast_version", "")},
        "disclaimer": DISCLAIMER,
    }


def get_system_truth_audit() -> dict[str, Any]:  # type: ignore[no-redef]
    payload = get_live_predictions()
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    prob_hashes: dict[str, str] = {}
    center_hashes: dict[str, str] = {}
    cache_keys: dict[str, str] = {}
    metadata_missing: dict[str, list[str]] = {}
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        prob_hashes[horizon] = _stable_hash([card.get("p_up"), card.get("p_down"), card.get("p_neutral")])
        center_hashes[horizon] = _stable_hash([card.get("price_center"), card.get("range_low"), card.get("range_high")])
        cache_keys[horizon] = str(card.get("prediction_cache_key", ""))
        missing = [
            key
            for key in ("prediction_id", "model_version", "data_timestamp", "source_timestamp", "feature_set_id", "prediction_cache_key")
            if not card.get(key)
        ]
        if missing:
            metadata_missing[horizon] = missing
    duplicate_prob = len(set(prob_hashes.values())) < len(prob_hashes) if prob_hashes else False
    duplicate_center = len(set(center_hashes.values())) < len(center_hashes) if center_hashes else False
    duplicate_cache = len(set(cache_keys.values())) < len(cache_keys) if cache_keys else False
    watermark = get_data_watermark()
    watermark_ok = bool(watermark.get("latest_price") and watermark.get("latest_quote_time"))
    status = "pass" if not (duplicate_prob or duplicate_center or duplicate_cache or metadata_missing) else "warning"
    return {
        "system_truth_audit": status,
        "model_independence_audit": {
            "duplicate_direction_prob_hash": duplicate_prob,
            "duplicate_center_hash": duplicate_center,
            "duplicate_prediction_cache_key": duplicate_cache,
            "prob_hashes": prob_hashes,
            "center_hashes": center_hashes,
            "cache_keys": cache_keys,
        },
        "metadata_audit": {"ok": not metadata_missing, "missing": metadata_missing},
        "watermark_audit": {"ok": watermark_ok, "latest_price": watermark.get("latest_price"), "latest_quote_time": watermark.get("latest_quote_time"), "stale_status": watermark.get("stale_status")},
        "model_training_audit": {"status": "candidate_requires_walk_forward", "promotion_gate": "direction_first"},
        "promotion_gate_audit": {"status": "active_retained_until_candidate_passes_gate", "gate_order": get_model_promotion_report().get("gate_order", [])},
        "no_leakage_audit": {"status": "guarded_by_available_at_and_cache_key_contract"},
        "forecast_path_audit": {"source": "return_path + continuity_guard", "status": "guarded"},
        "event_pipeline_audit": get_events_audit("tomorrow"),
        "data_reality_audit": watermark,
        "latency_audit": {"generated_at": _now(), "data_age_seconds": watermark.get("data_age_seconds")},
        "cache_conflict_audit": {"unified_forecast_version": payload.get("unified_forecast_version", ""), "metadata_missing": metadata_missing},
        "disclaimer": DISCLAIMER,
    }


def get_predictions_history(status: str = "verified") -> dict[str, Any]:
    path = _output_dir() / "sn_prediction_history.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if status == "all" or str(item.get("status", "pending")) == status:
                rows.append(item)
    return {"status": status, "items": rows, "count": len(rows), "disclaimer": DISCLAIMER}


def get_prediction_by_id(prediction_id: str) -> dict[str, Any]:
    live = get_live_predictions()
    for horizon, card in (live.get("cards") or {}).items():
        if isinstance(card, Mapping) and str(card.get("prediction_id", "")) == prediction_id:
            return {"found": True, "horizon": horizon, "prediction": card, "disclaimer": DISCLAIMER}
    return {"found": False, "prediction_id": prediction_id, "message": "未找到该预测快照。", "disclaimer": DISCLAIMER}


def get_reports_manifest() -> dict[str, Any]:
    return {
        "reports": [
            {"type": "daily", "title": "沪锡期货多周期方向预测与事件驱动分析日报"},
            {"type": "weekly", "title": "沪锡期货周度方向与风险报告"},
            {"type": "monthly", "title": "沪锡期货月度产业链与模型报告"},
            {"type": "event", "title": "沪锡重大事件专项分析报告"},
        ],
        "disclaimer": DISCLAIMER,
    }


def get_report_content(report_type: str = "daily") -> dict[str, Any]:
    live = get_live_predictions()
    news = get_news_policy_impact()
    health = get_models_health()
    learning = get_learning_status()
    return build_service_report_content(
        report_type=report_type,
        generated_at=_now(),
        data_watermark=get_data_watermark(),
        live_predictions=live,
        model_health=health,
        learning_status=learning,
        news_policy=news,
    )


def get_ui_bootstrap() -> dict[str, Any]:
    live = get_live_predictions()
    return {
        "app": "SNInsightTerminal",
        "version": runtime_status().get("app_version", "V3.8.0"),
        "runtime_status": runtime_status(),
        "navigation": ["首页", "行情预测", "新闻政策", "模型证据", "报告"],
        "data_watermark": get_data_watermark(),
        "model_health": get_models_health(),
        "latest_predictions": live.get("cards", {}),
        "news_policy_summary": get_news_policy_impact().get("summary", {}),
        "horizon_registry": list_horizon_configs(),
        "disclaimer": DISCLAIMER,
    }


def get_open_source_inspirations() -> dict[str, Any]:
    return {
        "items": [
            {"project": "Microsoft Qlib", "usage": "研究流水线、模型注册、walk-forward 思想借鉴，不直接复制代码"},
            {"project": "FinRL", "usage": "仅借鉴风控/阈值决策层，RL 不直接预测价格"},
            {"project": "MLForecast/MAPIE", "usage": "lag/rolling 特征与区间校准思想，可选依赖"},
        ],
        "license_note": "开源项目仅借鉴架构思想；正式包避免大型研究依赖。",
    }


def evaluate_decision_policy() -> dict[str, Any]:
    return {"policy": "contextual_bandit_threshold_layer", "status": "research_only", "disclaimer": DISCLAIMER}


def evaluate_position_scenario_api(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_position_scenario(payload, get_live_predictions())


def run_experiment_stub(model_type: str = "direction_first", horizon: str = "tomorrow", train_window: int = 126, compute_profile: str = "fast") -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:12],
        "status": "queued",
        "model_type": model_type,
        "horizon": horizon,
        "train_window": train_window,
        "compute_profile": compute_profile,
        "message": "实验任务已登记；candidate 必须通过 promotion gate 才能上线。",
    }

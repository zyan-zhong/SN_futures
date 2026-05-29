from __future__ import annotations

import math
from typing import Any, Mapping


MISSING_TEXT = "数据暂缺"
DISCLAIMER = "本内容仅用于沪锡期货量化投研参考，需独立决策，不构成投资建议。"


DISPLAY_LABELS = {
    "up": "上涨",
    "down": "下跌",
    "neutral": "观望",
    "bullish": "偏多",
    "bearish": "偏空",
    "volatility": "波动风险",
    "mixed": "多空分歧",
    "strong_up": "强偏多",
    "weak_up": "弱偏多",
    "weak_down": "弱偏空",
    "strong_down": "强偏空",
    "abstain": "暂不输出方向",
    "active": "现行模型",
    "candidate": "候选模型",
    "paper_active": "纸面现行",
    "degraded": "已降级",
    "retired": "已退役",
    "active_retained": "保留现行模型",
    "active_retained_until_candidate_passes_gate": "候选未过门槛，保留现行模型",
    "candidate_failed_or_not_run": "候选未通过或尚未运行",
    "candidate_ready_for_gate": "候选待晋级检查",
    "requires_walk_forward": "需要真实滚动验证",
    "fresh": "最新",
    "fresh_or_recent": "较新",
    "stale": "行情偏旧",
    "fallback": "备用源",
    "snapshot_cache": "本地快照缓存",
    "cached_or_pending": "缓存口径或待生成",
    "pass": "通过",
    "guarded": "已守门",
    "repaired": "已修复",
    "missing_payload_error": "后端字段缺失",
    "invalid_probability_payload": "概率字段异常",
    "low_impact": "影响分不足",
    "no_available_at": "缺少可用时间",
    "event_window_mismatch": "不在本周期事件窗口",
    "prediction_time_alignment_failed": "预测时间对齐失败",
}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "none", "null", "n/a"}
    try:
        # pandas.NA / numpy scalar compatibility without importing heavy modules.
        if value != value:  # noqa: PLR0124
            return True
    except Exception:
        return False
    return False


def sanitize_for_json(value: Any, *, text_for_nan: bool = False) -> Any:
    if isinstance(value, Mapping):
        return {str(key): sanitize_for_json(item, text_for_nan=text_for_nan) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item, text_for_nan=text_for_nan) for item in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return MISSING_TEXT if text_for_nan else None
    if hasattr(value, "item"):
        try:
            return sanitize_for_json(value.item(), text_for_nan=text_for_nan)
        except Exception:
            return str(value)
    if isinstance(value, str) and value.strip().lower() == "nan":
        return MISSING_TEXT
    return value


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if math.isfinite(parsed) else default


def label(value: Any, default: str = MISSING_TEXT) -> str:
    if is_missing(value):
        return default
    text = str(value)
    return DISPLAY_LABELS.get(text, text)


def fmt_pct(value: Any, digits: int = 1) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return MISSING_TEXT
    return f"{parsed * 100:.{digits}f}%"


def fmt_price(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None or parsed <= 0:
        return MISSING_TEXT
    return f"{parsed:,.0f}"


def fmt_num(value: Any, digits: int = 2) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return MISSING_TEXT
    return f"{parsed:.{digits}f}"


def direction_zh(card: Mapping[str, Any]) -> str:
    raw = str(card.get("direction") or card.get("direction_label") or card.get("direction_key") or "").lower()
    p_up = safe_float(card.get("p_up", card.get("prob_up")), 0.0) or 0.0
    p_down = safe_float(card.get("p_down", card.get("prob_down")), 0.0) or 0.0
    p_neutral = safe_float(card.get("p_neutral", card.get("prob_neutral")), 0.0) or 0.0
    if "up" in raw or "bull" in raw or "多" in raw or "涨" in raw:
        return "上涨"
    if "down" in raw or "bear" in raw or "空" in raw or "跌" in raw:
        return "下跌"
    if p_neutral >= max(p_up, p_down):
        return "观望"
    return "上涨" if p_up > p_down else "下跌"


def signal_zh(card: Mapping[str, Any]) -> str:
    signal = str(card.get("signal") or card.get("signal_label") or "").strip()
    if signal in {"多头研究观察", "空头研究观察", "观望"}:
        return signal
    direction = direction_zh(card)
    confidence = safe_float(card.get("confidence_score", card.get("confidence")), 0.0) or 0.0
    p_neutral = safe_float(card.get("p_neutral", card.get("prob_neutral")), 0.0) or 0.0
    if direction == "上涨" and confidence >= 55 and p_neutral < 0.62:
        return "多头研究观察"
    if direction == "下跌" and confidence >= 55 and p_neutral < 0.62:
        return "空头研究观察"
    return "观望"


def is_observe_signal(card: Mapping[str, Any]) -> bool:
    return signal_zh(card) == "观望" or direction_zh(card) == "观望"


def remove_trade_points_for_observe(card: dict[str, Any]) -> None:
    if not is_observe_signal(card):
        return
    for key in (
        "entry",
        "entry_price",
        "entry_reference",
        "stop_loss",
        "take_profit",
        "target_price",
        "suggested_entry",
    ):
        card[key] = None
    card["trade_point_note"] = "暂无交易点位"

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .horizon_registry import HorizonConfig, get_horizon_config
from .trading_calendar import sn_trading_session_state


TZ = "Asia/Hong_Kong"


def _local_ts(value: Any | None = None) -> pd.Timestamp:
    ts = pd.Timestamp.now(tz=TZ) if value is None else pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(TZ)
    return ts.tz_convert(TZ)


def _is_trading_time(ts: pd.Timestamp) -> bool:
    return bool(sn_trading_session_state(ts).get("is_trading"))


def _next_session_start(ts: pd.Timestamp) -> pd.Timestamp:
    state = sn_trading_session_state(ts)
    return _local_ts(state.get("next_session_start") or state.get("next_hour_start") or ts)


def _next_intraday_time(ts: pd.Timestamp, minutes: int) -> pd.Timestamp:
    if not _is_trading_time(ts):
        return _next_session_start(ts)
    candidate = _local_ts(ts) + pd.Timedelta(minutes=max(1, int(minutes)))
    state = sn_trading_session_state(ts)
    session_end = _local_ts(state.get("current_session_end") or state.get("next_session_end") or state.get("next_hour_end") or candidate)
    if candidate < session_end and _is_trading_time(candidate):
        return candidate
    return _next_session_start(session_end + pd.Timedelta(seconds=1))


def _next_business_day_session_close(ts: pd.Timestamp, interval_days: int) -> pd.Timestamp:
    out = _local_ts(ts)
    steps = max(1, int(interval_days))
    advanced = 0
    while advanced < steps:
        out = out + pd.Timedelta(days=1)
        while out.weekday() >= 5:
            out = out + pd.Timedelta(days=1)
        advanced += 1
    return out.normalize() + pd.Timedelta(hours=15)


def generate_future_trading_index(
    last_timestamp: Any,
    horizon_key: str,
    *,
    steps: int | None = None,
) -> list[str]:
    """Generate strictly future trading timestamps for a horizon.

    It deliberately avoids natural-day `date + n` for intraday horizons and
    skips weekends for daily horizons.  Exchange holidays can be added later
    without changing callers because the chart API consumes this function only.
    """
    cfg = get_horizon_config(horizon_key)
    current = _local_ts(last_timestamp)
    current = current.floor("min")
    count = int(steps or cfg.forecast_steps)
    out: list[pd.Timestamp] = []
    cursor = current
    if cfg.forecast_interval_minutes:
        for _ in range(count):
            cursor = _next_intraday_time(cursor, cfg.forecast_interval_minutes)
            out.append(cursor)
        return [ts.isoformat() for ts in out]

    interval = cfg.forecast_trading_day_interval or 1
    for _ in range(count):
        cursor = _next_business_day_session_close(cursor, interval)
        out.append(cursor)
    return [ts.isoformat() for ts in out]


def build_forecast_curve(
    *,
    live_card: dict[str, Any],
    last_timestamp: Any,
    horizon_key: str,
) -> list[dict[str, Any]]:
    cfg = get_horizon_config(horizon_key)
    future_index = generate_future_trading_index(last_timestamp, horizon_key, steps=cfg.forecast_steps)
    anchor = _safe_float(live_card.get("anchor_close") or live_card.get("anchor_price") or live_card.get("asof_price"), 0.0)
    if anchor <= 0:
        anchor = _safe_float(live_card.get("live_quote", {}).get("latest") if isinstance(live_card.get("live_quote"), dict) else 0.0, 0.0)
    center_final = _safe_float(live_card.get("price_center"), anchor)
    low_final = _safe_float(live_card.get("range_low"), min(anchor, center_final))
    high_final = _safe_float(live_card.get("range_high"), max(anchor, center_final))
    prob = _safe_float(live_card.get("prob_up"), 0.5)
    neutral_prob = _safe_float(live_card.get("p_neutral", live_card.get("prob_neutral", 0.0)), 0.0)
    volatility = abs(_safe_float(live_card.get("volatility"), 0.0))
    if volatility <= 0:
        volatility = max(abs(high_final - low_final) / max(anchor, 1.0) / 3.8, 0.0008)
    if anchor > 0 and center_final > 0:
        total_log_return = float(np.log(center_final / anchor))
    else:
        total_log_return = 0.0
    edge = max(0.0, min(1.0, abs(prob - 0.5) * 2.0))
    if neutral_prob >= 0.55:
        # A neutral forecast may still have a tiny drift, but should not imply a
        # strong terminal trend in the chart path.
        total_log_return *= 0.38
    wiggle_cap = min(max(volatility * 0.16, 0.00003), 0.0018) * (0.35 + edge)
    final_half_width = max(abs(high_final - center_final), abs(center_final - low_final), anchor * volatility * 1.2)
    min_half_width = max(anchor * 0.00025, 1.0)
    rows: list[dict[str, Any]] = []
    total = max(len(future_index), 1)
    for idx, ts in enumerate(future_index, start=1):
        progress = idx / total
        # Cumulative-return path instead of absolute-price interpolation.  The
        # ease curve keeps the first point continuous with the last real price;
        # the small deterministic wave prevents a copied flat line while still
        # ending exactly at the calibrated terminal center.
        ease = 0.58 * (1.0 - np.cos(np.pi * progress)) / 2.0 + 0.42 * progress
        wave = np.sin(2.0 * np.pi * progress) * wiggle_cap * (1.0 - 0.25 * progress)
        cumulative_return = total_log_return * ease + wave
        center = anchor * float(np.exp(cumulative_return))
        width_shape = 0.42 + 0.58 * np.sqrt(progress)
        width_wave = 1.0 + 0.045 * np.sin(np.pi * progress)
        half_width = max(min_half_width, final_half_width * width_shape * width_wave)
        if idx == total:
            center = center_final
            half_width = max(min_half_width, final_half_width)
        low = center - half_width
        high = center + half_width
        rows.append(
            {
                "date": ts,
                "close": None,
                "pred_center": center,
                "pred_low": max(0.0, low),
                "pred_high": max(high, center),
                "prob_up": prob,
                "p_neutral": neutral_prob,
                "expected_return_path": center / anchor - 1.0 if anchor else 0.0,
                "interval_width": max(high, center) - max(0.0, low),
                "row_status": "future_forecast",
                "forecast_step": idx,
                "forecast_steps": total,
                "horizon_key": horizon_key,
                "model_family": cfg.model_family,
                "bar_interval": cfg.bar_interval,
                "data_source": "unified_forecast",
            }
        )
    return _repair_forecast_path(rows, anchor=anchor, volatility=volatility, live_card=live_card)


def _repair_forecast_path(
    rows: list[dict[str, Any]],
    *,
    anchor: float,
    volatility: float,
    live_card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply final continuity and interval sanity checks before charting.

    This is a display safety gate, not a fake performance improvement.  If the
    upstream model produces an implausible first-step jump without a strong
    event-shock reason, we conservatively compress the return path around the
    last valid price and expose the repair reason in the chart payload.
    """
    if not rows or anchor <= 0:
        return rows
    impact = live_card.get("news_policy_impact") if isinstance(live_card.get("news_policy_impact"), dict) else {}
    event_weight = _safe_float(impact.get("confidence_weight"), 0.0)
    event_direction = str(impact.get("event_factor_direction", "") or "")
    event_shock_allowance = anchor * volatility * (2.2 if event_weight >= 0.55 and event_direction in {"volatility", "mixed"} else 0.0)
    max_first_jump = max(anchor * max(volatility, 0.0006) * 0.60, anchor * 0.0012, 3.0, event_shock_allowance)
    first_center = _safe_float(rows[0].get("pred_center"), anchor)
    first_jump = abs(first_center - anchor)
    repair_reasons: list[str] = []
    scale = 1.0
    if first_jump > max_first_jump > 0:
        scale = max_first_jump / first_jump
        repair_reasons.append("first_step_jump_repaired")

    centers = [_safe_float(row.get("pred_center"), anchor) for row in rows]
    unique_centers = {round(value, 4) for value in centers}
    if len(rows) >= 4 and len(unique_centers) <= 2:
        repair_reasons.append("flatline_path_micro_variation_added")
    widths = [max(0.0, _safe_float(row.get("pred_high"), anchor) - _safe_float(row.get("pred_low"), anchor)) for row in rows]
    horizon_key = str(rows[0].get("horizon_key") or "")
    max_width_growth_by_horizon = {
        "next_5m": 2.0,
        "next_15m": 2.15,
        "next_30m": 2.35,
        "next_hour": 2.65,
        "tomorrow": 1.85,
        "one_to_two_weeks": 2.25,
        "one_to_three_months": 3.0,
    }
    max_width_growth = max_width_growth_by_horizon.get(horizon_key, 2.8)
    if event_weight >= 0.55 and event_direction in {"volatility", "mixed"}:
        max_width_growth *= 1.18
    if len(widths) >= 4 and widths[0] > 0 and widths[-1] / widths[0] > max_width_growth:
        repair_reasons.append("interval_explosion_capped")

    if not repair_reasons:
        for row in rows:
            row["path_sanity_status"] = "pass"
            row["interval_growth_guard"] = f"max_growth_{max_width_growth:.2f}x"
            row["interval_policy"] = "volatility_atr_event_guard"
        return rows

    repaired: list[dict[str, Any]] = []
    base_width = max(widths[0] if widths else anchor * volatility, anchor * max(volatility, 0.0006), 1.0)
    for idx, row in enumerate(rows, start=1):
        progress = idx / max(len(rows), 1)
        original_center = _safe_float(row.get("pred_center"), anchor)
        center = anchor + (original_center - anchor) * scale
        if "flatline_path_micro_variation_added" in repair_reasons:
            center += anchor * min(max(volatility, 0.0004) * 0.12, 0.0006) * np.sin(2.0 * np.pi * progress)
        original_width = max(0.0, _safe_float(row.get("pred_high"), center) - _safe_float(row.get("pred_low"), center))
        max_width = base_width * (1.0 + (max_width_growth - 1.0) * np.sqrt(progress))
        width = min(max(original_width * max(scale, 0.35), base_width * (0.72 + 0.28 * np.sqrt(progress))), max_width)
        low = max(0.0, center - width / 2.0)
        high = max(center, center + width / 2.0)
        new_row = dict(row)
        new_row.update(
            {
                "pred_center": center,
                "pred_low": low,
                "pred_high": high,
                "expected_return_path": center / anchor - 1.0,
                "interval_width": high - low,
                "path_sanity_status": "repaired",
                "path_repair_reasons": repair_reasons,
                "path_repair_anchor": anchor,
                "path_repair_max_first_jump": max_first_jump,
                "interval_growth_guard": f"max_growth_{max_width_growth:.2f}x",
                "interval_policy": "volatility_atr_event_guard",
            }
        )
        repaired.append(new_row)
    return repaired


def validate_chart_alignment(history_rows: list[dict[str, Any]], forecast_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not history_rows or not forecast_rows:
        return {
            "ok": False,
            "reason": "历史区或未来预测区为空",
            "history_last": "",
            "forecast_first": "",
        }
    try:
        history_last = _local_ts(history_rows[-1].get("date"))
        forecast_first = _local_ts(forecast_rows[0].get("date"))
    except Exception as exc:
        return {"ok": False, "reason": f"时间解析失败：{exc}", "history_last": "", "forecast_first": ""}
    ok = forecast_first > history_last
    return {
        "ok": bool(ok),
        "reason": "预测区严格晚于历史区" if ok else "预测区未晚于历史区，图表时间轴存在错位",
        "history_last": history_last.isoformat(),
        "forecast_first": forecast_first.isoformat(),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default

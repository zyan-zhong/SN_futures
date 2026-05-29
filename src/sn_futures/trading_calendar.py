from __future__ import annotations

from typing import Any

import pandas as pd


TZ = "Asia/Hong_Kong"
DAY_SESSIONS = ((9, 0, 10, 15), (10, 30, 11, 30), (13, 30, 15, 0))
WINDOW_KEYS = {5: "next_5m", 15: "next_15m", 30: "next_30m", 60: "next_hour"}


def _to_local_ts(value: Any | None = None) -> pd.Timestamp:
    ts = pd.Timestamp.now(tz=TZ) if value is None else pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(TZ)
    return ts.tz_convert(TZ)


def _day_start(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_localize(None).normalize().tz_localize(TZ)


def _at(day: pd.Timestamp, hour: int, minute: int = 0) -> pd.Timestamp:
    return _day_start(day) + pd.Timedelta(hours=hour, minutes=minute)


def _next_weekday(day: pd.Timestamp) -> pd.Timestamp:
    next_day = _day_start(day) + pd.Timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += pd.Timedelta(days=1)
    return next_day


def _first_day_session(day: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_h, start_m, end_h, end_m = DAY_SESSIONS[0]
    return _at(day, start_h, start_m), _at(day, end_h, end_m)


def _night_session_for_start_day(day: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = _at(day, 21, 0)
    return start, start + pd.Timedelta(hours=4)


def _find_current_session(local: pd.Timestamp) -> tuple[str, pd.Timestamp, pd.Timestamp] | None:
    weekday = local.weekday()
    if weekday <= 4:
        for start_h, start_m, end_h, end_m in DAY_SESSIONS:
            start = _at(local, start_h, start_m)
            end = _at(local, end_h, end_m)
            if start <= local < end:
                return "day", start, end
        night_start, night_end = _night_session_for_start_day(local)
        if night_start <= local < night_end:
            return "night", night_start, night_end

    previous_day = _day_start(local) - pd.Timedelta(days=1)
    if previous_day.weekday() <= 4:
        night_start, night_end = _night_session_for_start_day(previous_day)
        if night_start <= local < night_end:
            return "night", night_start, night_end
    return None


def _find_next_session(local: pd.Timestamp) -> tuple[str, pd.Timestamp, pd.Timestamp]:
    day = _day_start(local)
    if local.weekday() <= 4:
        for start_h, start_m, end_h, end_m in DAY_SESSIONS:
            start = _at(day, start_h, start_m)
            end = _at(day, end_h, end_m)
            if local < start:
                return "day", start, end
        night_start, night_end = _night_session_for_start_day(day)
        if local < night_start:
            return "night", night_start, night_end

    next_day = _next_weekday(day)
    return "day", *_first_day_session(next_day)


def _trading_day_label(session_kind: str, session_start: pd.Timestamp) -> str:
    suffix = "夜盘" if session_kind == "night" else "日盘"
    return f"{session_start:%Y-%m-%d} {suffix}"


def sn_trading_session_state(current: Any | None = None) -> dict[str, Any]:
    local = _to_local_ts(current)
    session = _find_current_session(local)
    is_trading = session is not None
    if session is None:
        session_kind, session_start, session_end = _find_next_session(local)
        target_start = session_start
        note = "当前不在沪锡交易时段，短周期预测窗口已对齐到下一段真实开盘。"
    else:
        session_kind, session_start, session_end = session
        target_start = local.ceil("min")
        note = "当前处于沪锡交易时段，短周期预测窗口从当前可交易分钟开始。"

    target_end = min(target_start + pd.Timedelta(hours=1), session_end)
    remaining = max(0.0, (session_end - target_start).total_seconds() / 60.0)
    if remaining < 60:
        note += " 当前交易段剩余时间不足60分钟，部分窗口会截断到本段收盘。"

    forecast_windows: dict[str, dict[str, Any]] = {}
    for minutes, key in WINDOW_KEYS.items():
        window_end = min(target_start + pd.Timedelta(minutes=minutes), session_end)
        actual_minutes = max(0.0, (window_end - target_start).total_seconds() / 60.0)
        window_note = note
        if actual_minutes + 1e-9 < minutes:
            window_note += f" 目标{minutes}分钟窗口已按本交易段剩余时间截断。"
        forecast_windows[key] = {
            "horizon_key": key,
            "window_minutes": minutes,
            "start": target_start.isoformat(),
            "end": window_end.isoformat(),
            "actual_minutes": round(actual_minutes, 2),
            "is_truncated": bool(actual_minutes + 1e-9 < minutes),
            "is_trading": bool(is_trading),
            "is_night": bool(session_kind == "night"),
            "session_label": "夜盘" if session_kind == "night" else "日盘",
            "note": window_note,
        }

    return {
        "now": local.isoformat(),
        "is_trading": bool(is_trading),
        "is_night": bool(session_kind == "night"),
        "session_label": "夜盘" if session_kind == "night" else "日盘",
        "trading_day_label": _trading_day_label(session_kind, session_start),
        "current_session_start": session_start.isoformat() if is_trading else "",
        "current_session_end": session_end.isoformat() if is_trading else "",
        "next_session_start": session_start.isoformat(),
        "next_session_end": session_end.isoformat(),
        "next_hour_start": target_start.isoformat(),
        "next_hour_end": target_end.isoformat(),
        "remaining_minutes": round(remaining, 2),
        "note": note,
        "forecast_windows": forecast_windows,
    }


def next_sn_trading_window(
    current: Any | None = None,
    *,
    minutes: int = 60,
) -> tuple[pd.Timestamp, pd.Timestamp, dict[str, Any]]:
    state = sn_trading_session_state(current)
    key = WINDOW_KEYS.get(int(minutes), "next_hour")
    window = state.get("forecast_windows", {}).get(key, {}) if isinstance(state.get("forecast_windows"), dict) else {}
    if isinstance(window, dict) and window.get("start") and window.get("end"):
        return pd.Timestamp(window["start"]), pd.Timestamp(window["end"]), {**state, "active_forecast_window": window}
    return pd.Timestamp(state["next_hour_start"]), pd.Timestamp(state["next_hour_end"]), state

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


SOURCE_TTL_SECONDS: dict[str, int] = {
    "realtime_market": 15 * 60,
    "local_market_cache": 15 * 60,
    "sina_market": 15 * 60,
    "akshare_realtime": 15 * 60,
    "akshare_history": 36 * 60 * 60,
    "daily_market": 36 * 60 * 60,
    "shfe_public": 36 * 60 * 60,
    "newsapi": 24 * 60 * 60,
    "akshare_news": 24 * 60 * 60,
    "miit_policy": 7 * 24 * 60 * 60,
    "miit_policy_expire": 30 * 24 * 60 * 60,
    "reports": 24 * 60 * 60,
    "predictions": 24 * 60 * 60,
    "factor_diagnostics": 7 * 24 * 60 * 60,
}


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "数据暂缺", "本周期未更新"}:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None)
    except Exception:
        return None


def _ttl_seconds(source_name: str) -> int:
    key = (source_name or "").strip().lower()
    return SOURCE_TTL_SECONDS.get(key, SOURCE_TTL_SECONDS.get(key.replace("-", "_"), 24 * 60 * 60))


def _is_closed_session(trading_session: Any) -> bool:
    text = str(trading_session or "").lower()
    return any(token in text for token in ("closed", "休市", "非交易", "holiday", "weekend"))


def _ttl_zh(ttl_seconds: int) -> str:
    if ttl_seconds < 3600:
        return f"{round(ttl_seconds / 60)} 分钟"
    if ttl_seconds < 86400:
        return f"{round(ttl_seconds / 3600)} 小时"
    return f"{round(ttl_seconds / 86400)} 天"


def classify_freshness(
    source_name: str,
    last_update: Any,
    trading_session: Any = None,
    *,
    enabled: bool = True,
    success: bool | None = None,
    from_cache: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify provider freshness without turning unconfigured sources into stale failures."""
    current = (now or datetime.now()).replace(tzinfo=None)
    source_key = (source_name or "").strip().lower()
    ttl = _ttl_seconds(source_key)
    parsed = _parse_time(last_update)

    if not enabled:
        return {
            "status_code": "unconfigured",
            "status_zh": "未配置",
            "freshness_label": "未配置",
            "stale": False,
            "ttl_seconds": ttl,
            "ttl_zh": _ttl_zh(ttl),
            "next_expected_update_time": None,
            "message_zh": "数据源未配置，请在设置页配置后再刷新。",
        }

    if parsed is None:
        label = "请求失败" if success is False else "本周期未更新"
        return {
            "status_code": "failed" if success is False else "not_updated",
            "status_zh": label,
            "freshness_label": label,
            "stale": bool(success is False),
            "ttl_seconds": ttl,
            "ttl_zh": _ttl_zh(ttl),
            "next_expected_update_time": None,
            "message_zh": "尚未记录最近成功更新时间。",
        }

    age = max(0.0, (current - parsed).total_seconds())
    next_update = parsed + timedelta(seconds=ttl)
    stale = age > ttl

    if source_key == "miit_policy":
        expire_ttl = SOURCE_TTL_SECONDS["miit_policy_expire"]
        if age <= ttl:
            return {
                "status_code": "ok",
                "status_zh": "正常",
                "freshness_label": "正常",
                "stale": False,
                "ttl_seconds": ttl,
                "ttl_zh": _ttl_zh(ttl),
                "next_expected_update_time": next_update.isoformat(timespec="seconds"),
                "message_zh": "工信部政策源在 7 天建议更新窗口内。",
            }
        if age <= expire_ttl:
            return {
                "status_code": "old_usable",
                "status_zh": "较旧但可参考",
                "freshness_label": "较旧但可参考",
                "stale": False,
                "ttl_seconds": ttl,
                "ttl_zh": _ttl_zh(ttl),
                "next_expected_update_time": next_update.isoformat(timespec="seconds"),
                "message_zh": "政策源超过 7 天建议刷新窗口，但 30 天内仍可参考。",
            }
        stale = True

    if stale and _is_closed_session(trading_session) and source_key in {
        "realtime_market",
        "local_market_cache",
        "sina_market",
        "akshare_realtime",
        "shfe_public",
    }:
        return {
            "status_code": "waiting_next_session",
            "status_zh": "非交易时段等待更新",
            "freshness_label": "非交易时段等待更新",
            "stale": False,
            "ttl_seconds": ttl,
            "ttl_zh": _ttl_zh(ttl),
            "next_expected_update_time": next_update.isoformat(timespec="seconds"),
            "message_zh": "当前不在连续交易窗口或官方更新窗口内，等待下一交易时段/交易日更新。",
        }

    if from_cache:
        label = "已过期" if stale else "使用缓存"
        return {
            "status_code": "cache_stale" if stale else "cache",
            "status_zh": label,
            "freshness_label": label,
            "stale": stale,
            "ttl_seconds": ttl,
            "ttl_zh": _ttl_zh(ttl),
            "next_expected_update_time": next_update.isoformat(timespec="seconds"),
            "message_zh": "当前展示最近成功缓存。" if not stale else "缓存已超过建议更新周期，请尝试刷新。",
        }

    label = "已过期" if stale else "正常"
    return {
        "status_code": "stale" if stale else "ok",
        "status_zh": label,
        "freshness_label": label,
        "stale": stale,
        "ttl_seconds": ttl,
        "ttl_zh": _ttl_zh(ttl),
        "next_expected_update_time": next_update.isoformat(timespec="seconds"),
        "message_zh": "数据在建议更新周期内。" if not stale else "数据超过建议更新周期，请刷新。",
    }


def explain_freshness_zh(source_name: str, last_update: Any, trading_session: Any = None, **kwargs: Any) -> str:
    return str(classify_freshness(source_name, last_update, trading_session, **kwargs).get("message_zh", "状态待验证"))


def is_stale(source_name: str, last_update: Any, trading_session: Any = None, **kwargs: Any) -> bool:
    return bool(classify_freshness(source_name, last_update, trading_session, **kwargs).get("stale"))


def next_expected_update_time(source_name: str, last_update: Any) -> str | None:
    parsed = _parse_time(last_update)
    if parsed is None:
        return None
    return (parsed + timedelta(seconds=_ttl_seconds(source_name))).isoformat(timespec="seconds")


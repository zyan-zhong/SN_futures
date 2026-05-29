from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


RATE_LIMIT_COOLDOWN_MINUTES = 70
NETWORK_COOLDOWN_MINUTES = 15
SCHEMA_COOLDOWN_MINUTES = 30


def _now() -> datetime:
    return datetime.now()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _history_path() -> Path:
    return _fundamentals_dir() / "alpha_attempt_history.json"


def _read_history() -> dict[str, Any]:
    path = _history_path()
    if not path.exists():
        return {"attempts": [], "by_source": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"attempts": [], "by_source": {}}
    return payload if isinstance(payload, dict) else {"attempts": [], "by_source": {}}


def _write_history(payload: Mapping[str, Any]) -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _message_from_payload(payload: Any) -> str:
    if isinstance(payload, Mapping):
        parts: list[str] = []
        for key in ("Note", "Information", "Error Message", "message", "message_zh", "error", "error_message", "error_code"):
            value = payload.get(key)
            if value:
                parts.append(str(value))
        data = payload.get("data")
        if isinstance(data, Mapping):
            parts.append(_message_from_payload(data))
        return " ".join(part for part in parts if part)
    return str(payload or "")


def _cooldown_for_status(status: str) -> int:
    if status == "rate_limited":
        return RATE_LIMIT_COOLDOWN_MINUTES
    if status == "network_failed":
        return NETWORK_COOLDOWN_MINUTES
    if status == "schema_mismatch":
        return SCHEMA_COOLDOWN_MINUTES
    return 0


def classify_alpha_response(response_json: Any) -> dict[str, Any]:
    """Classify Alpha Vantage payloads without leaking API keys.

    Alpha Vantage often returns HTTP 200 with a JSON body containing ``Note``
    or ``Information`` for rate limits.  Provider code must treat those as
    failures and preserve the last good cache.
    """

    message = sanitize_text(_message_from_payload(response_json))
    lower = message.lower()
    status = "success"
    if isinstance(response_json, Mapping) and response_json.get("success") is False:
        status = str(response_json.get("error_code") or "").strip() or "request_failed"
    if (
        "invalid api key" in lower
        or "invalid key" in lower
        or "apikey is invalid" in lower
        or ("invalid api call" in lower and "apikey" in lower)
    ):
        status = "key_invalid"
    elif "note" in lower or "information" in lower or "frequency" in lower or "rate limit" in lower or "standard api call frequency" in lower:
        status = "rate_limited"
    elif "timed out" in lower or "urlopen" in lower or "network" in lower or "connection" in lower:
        status = "network_failed"
    elif "invalid api call" in lower or "malformed" in lower:
        status = "schema_mismatch"
    elif isinstance(response_json, Mapping) and response_json.get("success") is True:
        status = "success"
    elif isinstance(response_json, Mapping) and not response_json:
        status = "schema_mismatch"

    cooldown_minutes = _cooldown_for_status(status)
    cooldown_until = _iso(_now() + timedelta(minutes=cooldown_minutes)) if cooldown_minutes else ""
    return sanitize_for_json(
        {
            "status": status,
            "cooldown_until": cooldown_until,
            "message_zh": _message_zh(status),
            "safe_to_retry_now": cooldown_minutes == 0,
            "raw_message_sanitized": message,
        }
    )


def _message_zh(status: str) -> str:
    messages = {
        "success": "Alpha Vantage 请求成功。",
        "rate_limited": "Alpha Vantage 当前限流，已进入冷却窗口；不会覆盖最近成功缓存。",
        "key_invalid": "Alpha Vantage key 无效，请在设置页替换。",
        "network_failed": "Alpha Vantage 网络请求失败，可稍后重试。",
        "schema_mismatch": "Alpha Vantage 返回结构与预期不匹配，已保留缓存。",
        "request_failed": "Alpha Vantage 请求失败，已保留缓存。",
    }
    return messages.get(status, "Alpha Vantage 状态未知，已保留缓存。")


def is_rate_limited(payload: Any) -> bool:
    return classify_alpha_response(payload).get("status") == "rate_limited"


def is_invalid_key(payload: Any) -> bool:
    return classify_alpha_response(payload).get("status") == "key_invalid"


def is_success(payload: Any) -> bool:
    return classify_alpha_response(payload).get("status") == "success"


def record_alpha_attempt(source: str, status: str, *, message_zh: str = "", row_count: int = 0) -> dict[str, Any]:
    now = _now()
    cooldown_minutes = _cooldown_for_status(status)
    cooldown_until = _iso(now + timedelta(minutes=cooldown_minutes)) if cooldown_minutes else ""
    history = _read_history()
    attempts = history.setdefault("attempts", [])
    by_source = history.setdefault("by_source", {})
    entry = {
        "source": source,
        "status": status,
        "attempted_at": _iso(now),
        "cooldown_until": cooldown_until,
        "row_count": int(row_count),
        "message_zh": sanitize_text(message_zh or _message_zh(status)),
    }
    attempts.append(entry)
    by_source[source] = entry
    history["attempts"] = attempts[-200:]
    history["updated_at"] = _iso(now)
    _write_history(history)
    return sanitize_for_json(entry)


def _parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def should_skip_due_to_cooldown(source: str, *, now: datetime | None = None) -> bool:
    history = _read_history()
    by_source = history.get("by_source") if isinstance(history, Mapping) else {}
    entry = by_source.get(source) if isinstance(by_source, Mapping) else None
    if not isinstance(entry, Mapping):
        return False
    cooldown_until = _parse_iso(entry.get("cooldown_until"))
    if cooldown_until is None:
        return False
    return cooldown_until > (now or _now())


def next_retry_time(source: str, last_attempt_time: datetime | None = None) -> str:
    history = _read_history()
    by_source = history.get("by_source") if isinstance(history, Mapping) else {}
    entry = by_source.get(source) if isinstance(by_source, Mapping) else None
    if isinstance(entry, Mapping) and entry.get("cooldown_until"):
        return str(entry.get("cooldown_until"))
    base = last_attempt_time or _now()
    return _iso(base + timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES))

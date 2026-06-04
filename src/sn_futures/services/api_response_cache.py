from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Callable

from ..api.json_utils import sanitize_for_json


_CACHE: dict[str, dict[str, Any]] = {}
_LOCK = RLock()
_CACHE_CONTEXT: str | None = None


def _now() -> datetime:
    return datetime.now()


def _runtime_context() -> str:
    return str(os.environ.get("SN_DATA_DIR") or os.environ.get("SN_INSIGHT_DATA_DIR") or "")


def _reset_if_context_changed() -> None:
    global _CACHE_CONTEXT
    context = _runtime_context()
    if _CACHE_CONTEXT is None:
        _CACHE_CONTEXT = context
        return
    if _CACHE_CONTEXT != context:
        _CACHE.clear()
        _CACHE_CONTEXT = context


def clear_api_response_cache(prefix: str | None = None) -> None:
    with _LOCK:
        _reset_if_context_changed()
        if prefix is None:
            _CACHE.clear()
            return
        for key in list(_CACHE.keys()):
            if key.startswith(prefix):
                _CACHE.pop(key, None)


def get_cached_response(key: str, ttl_seconds: int) -> dict[str, Any] | None:
    with _LOCK:
        _reset_if_context_changed()
        item = _CACHE.get(key)
        if not item:
            return None
        created_at = item["created_at"]
        if _now() - created_at > timedelta(seconds=ttl_seconds):
            _CACHE.pop(key, None)
            return None
        payload = deepcopy(item["payload"])
        if isinstance(payload, dict):
            payload.setdefault("generated_at", created_at.isoformat(timespec="seconds"))
            payload["cache_hit"] = True
            payload["cache_age_seconds"] = max(0.0, round((_now() - created_at).total_seconds(), 3))
        return sanitize_for_json(payload)


def set_cached_response(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    created_at = _now()
    clean_payload = sanitize_for_json(deepcopy(payload))
    if isinstance(clean_payload, dict):
        clean_payload.setdefault("generated_at", created_at.isoformat(timespec="seconds"))
        clean_payload["cache_hit"] = False
        clean_payload["cache_age_seconds"] = 0.0
    with _LOCK:
        _reset_if_context_changed()
        _CACHE[key] = {"created_at": created_at, "payload": clean_payload}
    return sanitize_for_json(deepcopy(clean_payload))


def cached_call(key: str, ttl_seconds: int, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    cached = get_cached_response(key, ttl_seconds)
    if cached is not None:
        return cached
    return set_cached_response(key, fn())

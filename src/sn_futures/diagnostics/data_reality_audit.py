from __future__ import annotations

import re
from typing import Any, Mapping

import numpy as np
import pandas as pd


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _parse_ts(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?", text)
    if match:
        text = match.group(0)
    try:
        ts = pd.Timestamp(text)
    except Exception:
        return None
    if ts.tzinfo is None:
        return ts.tz_localize("Asia/Hong_Kong")
    return ts.tz_convert("Asia/Hong_Kong")


def audit_data_reality(watermark: Mapping[str, Any], trading_session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    live_quote = watermark.get("live_quote", {}) if isinstance(watermark.get("live_quote"), Mapping) else {}
    latest_price = _num(live_quote.get("latest"), 0.0)
    quote_ts = _parse_ts(live_quote.get("quote_time") or watermark.get("latest_realtime"))
    fetch_ts = _parse_ts(watermark.get("created_at") or live_quote.get("fetch_timestamp"))
    now = pd.Timestamp.now(tz="Asia/Hong_Kong")
    quote_age = None
    if quote_ts is not None:
        quote_age = max(0.0, (now - quote_ts).total_seconds())
    fetch_age = None
    if fetch_ts is not None:
        fetch_age = max(0.0, (now - fetch_ts).total_seconds())
    source_status = watermark.get("source_status", []) if isinstance(watermark.get("source_status", []), list) else []
    source_success = any(bool(item.get("success")) for item in source_status if isinstance(item, Mapping))
    from_cache = bool(live_quote.get("from_cache") or watermark.get("using_fallback"))
    source_mode = str(watermark.get("source_mode", ""))
    mock_terms = ("mock", "demo", "random", "static")
    mock_suspected = any(term in source_mode.lower() for term in mock_terms)
    issues: list[str] = []
    warnings: list[str] = []
    if latest_price <= 0:
        issues.append("missing_latest_price")
    if quote_ts is None:
        warnings.append("missing_quote_timestamp")
    if quote_age is not None and quote_age > 24 * 3600:
        warnings.append("quote_data_age_gt_24h")
    if not source_success and not from_cache:
        warnings.append("no_successful_source_status")
    if mock_suspected:
        issues.append("mock_or_static_data_suspected")
    if from_cache:
        warnings.append("using_cache_or_fallback")
    trading = bool((trading_session or {}).get("is_trading"))
    if trading and quote_age is not None and quote_age > 600:
        warnings.append("trading_time_quote_stale_gt_10m")
    ok = not issues
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "severity": "normal" if ok and not warnings else ("yellow" if ok else "red"),
        "summary": "行情真实性审计通过" if ok else "行情真实性存在关键风险",
        "issues": issues,
        "warnings": warnings,
        "latest_price": latest_price,
        "quote_timestamp": quote_ts.isoformat() if quote_ts is not None else "",
        "fetch_timestamp": fetch_ts.isoformat() if fetch_ts is not None else "",
        "quote_data_age_seconds": quote_age,
        "fetch_age_seconds": fetch_age,
        "source_mode": source_mode,
        "from_cache": from_cache,
        "source_success": source_success,
        "is_trading": trading,
    }

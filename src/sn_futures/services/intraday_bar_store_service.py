from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_url


SCHEMA_VERSION = "intraday_bar_store_v1"
TICK_SCHEMA_VERSION = "latest_quote_tick_v1"
REQUIRED_BAR_FIELDS = ("bar_start", "bar_end", "open", "high", "low", "close")
BAR_COLUMNS = (
    "symbol",
    "exchange",
    "active_contract",
    "interval",
    "trading_date",
    "bar_start",
    "bar_end",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "provider",
    "fetched_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_part(value: str, default: str) -> str:
    text = Path(str(value or default).strip() or default).name
    return text.replace(" ", "_") or default


def _store_dir(symbol: str, interval: str) -> Path:
    return get_user_output_dir() / "market" / "intraday_bars" / _safe_part(symbol.upper(), "SN") / _safe_part(interval.lower(), "5m")


def _manifest_path(symbol: str, interval: str) -> Path:
    return _store_dir(symbol, interval) / "manifest.json"


def _bars_path(symbol: str, interval: str) -> Path:
    return _store_dir(symbol, interval) / "bars.csv"


def _interval_seconds(interval: str) -> int | None:
    value = str(interval or "").strip().lower()
    if value.endswith("m") and value[:-1].isdigit():
        return int(value[:-1]) * 60
    if value.endswith("h") and value[:-1].isdigit():
        return int(value[:-1]) * 3600
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _is_date_only(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and "T" not in text and len(text) <= 10


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed == parsed else None


def _hash_rows(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(sanitize_for_json(rows), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def build_latest_quote_tick_manifest(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    provider = str(snapshot.get("provider") or snapshot.get("source") or "")
    quote_time = str(snapshot.get("quote_time") or snapshot.get("timestamp") or snapshot.get("fetched_at") or "")
    return sanitize_for_json(
        sanitize_mapping(
            {
                "schema_version": TICK_SCHEMA_VERSION,
                "data_kind": "latest_quote_tick",
                "symbol": str(snapshot.get("symbol") or "SN"),
                "exchange": str(snapshot.get("exchange") or "SHFE"),
                "provider": provider,
                "quote_time": quote_time,
                "fetched_at": str(snapshot.get("fetched_at") or _now()),
                "latest_price": _to_float(snapshot.get("latest") or snapshot.get("latest_price")),
                "display_only": True,
                "immutable_intraday_bar": False,
                "latest_quote_used_as_intraday_bar": False,
                "allowed_for_display": True,
                "allowed_for_feature_store": False,
                "allowed_for_training": False,
                "allowed_for_prediction": False,
                "allowed_for_backtest": False,
                "allowed_for_intraday_label": False,
                "sample_data_used": False,
                "baseline_used": False,
                "blocking_reasons": ["latest_quote_is_display_tick_not_label_source"],
            }
        )
    )


def _normalize_intraday_rows(
    rows: list[Mapping[str, Any]],
    *,
    symbol: str,
    exchange: str,
    active_contract: str,
    interval: str,
    provider: str,
    fetched_at: str,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    expected_seconds = _interval_seconds(interval)
    normalized: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    daily_bar_used_as_intraday = False
    if expected_seconds is None:
        return [], ["unsupported_intraday_interval"], False
    for row in rows:
        missing = [field for field in REQUIRED_BAR_FIELDS if row.get(field) in (None, "")]
        if missing:
            blocking_reasons.append("missing_required_intraday_bar_fields")
            continue
        start_raw = row.get("bar_start")
        end_raw = row.get("bar_end")
        start = _parse_timestamp(start_raw)
        end = _parse_timestamp(end_raw)
        if start is None or end is None or end <= start:
            blocking_reasons.append("malformed_intraday_bar_time")
            continue
        duration = (end - start).total_seconds()
        if _is_date_only(start_raw) or _is_date_only(end_raw) or duration > max(expected_seconds * 2, 7200):
            daily_bar_used_as_intraday = True
            blocking_reasons.append("daily_bar_used_as_intraday")
            continue
        if abs(duration - expected_seconds) > max(1, expected_seconds * 0.1):
            blocking_reasons.append("intraday_interval_mismatch")
            continue
        prices = {field: _to_float(row.get(field)) for field in ("open", "high", "low", "close")}
        if any(value is None for value in prices.values()):
            blocking_reasons.append("malformed_intraday_ohlc")
            continue
        volume = _to_float(row.get("volume"))
        open_interest = _to_float(row.get("open_interest"))
        normalized.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "active_contract": active_contract,
                "interval": interval,
                "trading_date": str(row.get("trading_date") or start.date().isoformat()),
                "bar_start": start.isoformat(),
                "bar_end": end.isoformat(),
                "open": prices["open"],
                "high": prices["high"],
                "low": prices["low"],
                "close": prices["close"],
                "volume": volume if volume is not None else 0.0,
                "open_interest": open_interest if open_interest is not None else 0.0,
                "provider": provider,
                "fetched_at": fetched_at,
            }
        )
    return normalized, sorted(set(blocking_reasons)), daily_bar_used_as_intraday


def _base_manifest(
    *,
    symbol: str,
    exchange: str,
    active_contract: str,
    interval: str,
    provider: str,
    fetched_at: str,
    as_of: str,
    source_url_sanitized: str,
    bars_path: str,
    row_count: int,
    content_hash: str,
    blocking_reasons: list[str],
    daily_bar_used_as_intraday: bool,
) -> dict[str, Any]:
    success = row_count > 0 and not blocking_reasons
    return sanitize_for_json(
        sanitize_mapping(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "success" if success else "blocked",
                "data_kind": "intraday_bar",
                "symbol": symbol,
                "exchange": exchange,
                "active_contract": active_contract,
                "interval": interval,
                "provider": provider,
                "fetched_at": fetched_at,
                "as_of": as_of or fetched_at,
                "source_url_sanitized": source_url_sanitized,
                "row_count": row_count,
                "bars_path": bars_path,
                "manifest_path": str(_manifest_path(symbol, interval)),
                "content_hash": content_hash,
                "history_immutable": success,
                "immutable_intraday_bars": success,
                "latest_quote_used": False,
                "latest_quote_used_as_intraday_bar": False,
                "daily_bar_used_as_intraday": daily_bar_used_as_intraday,
                "sample_data_used": False,
                "baseline_used": False,
                "allowed_for_display": success,
                "allowed_for_feature_store": success,
                "allowed_for_training": success,
                "allowed_for_prediction": success,
                "allowed_for_backtest": success,
                "allowed_for_intraday_label": success,
                "blocking_reasons": blocking_reasons,
            }
        )
    )


def write_intraday_bars(
    rows: list[Mapping[str, Any]],
    *,
    symbol: str = "SN",
    exchange: str = "SHFE",
    active_contract: str = "",
    interval: str = "5m",
    provider: str,
    source_url_sanitized: str = "",
    fetched_at: str = "",
    as_of: str = "",
) -> dict[str, Any]:
    symbol = str(symbol or "SN").upper()
    exchange = str(exchange or "SHFE").upper()
    interval = str(interval or "5m").lower()
    provider = str(provider or "unknown_provider")
    fetched_at = str(fetched_at or _now())
    source_url = sanitize_url(source_url_sanitized)
    normalized, blocking_reasons, daily_bar_used_as_intraday = _normalize_intraday_rows(
        rows,
        symbol=symbol,
        exchange=exchange,
        active_contract=str(active_contract or ""),
        interval=interval,
        provider=provider,
        fetched_at=fetched_at,
    )
    if not normalized and "intraday_bars_missing" not in blocking_reasons:
        blocking_reasons.append("intraday_bars_missing")
    bars_path = _bars_path(symbol, interval)
    if normalized and not blocking_reasons:
        bars_path.parent.mkdir(parents=True, exist_ok=True)
        with bars_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(BAR_COLUMNS))
            writer.writeheader()
            writer.writerows(normalized)
        visible_bars_path = str(bars_path)
    else:
        visible_bars_path = ""
    manifest = _base_manifest(
        symbol=symbol,
        exchange=exchange,
        active_contract=str(active_contract or ""),
        interval=interval,
        provider=provider,
        fetched_at=fetched_at,
        as_of=as_of or (normalized[-1]["bar_end"] if normalized else ""),
        source_url_sanitized=source_url,
        bars_path=visible_bars_path,
        row_count=len(normalized) if normalized and not blocking_reasons else 0,
        content_hash=_hash_rows(normalized) if normalized and not blocking_reasons else "",
        blocking_reasons=sorted(set(blocking_reasons)),
        daily_bar_used_as_intraday=daily_bar_used_as_intraday,
    )
    _write_json(_manifest_path(symbol, interval), manifest)
    return manifest


def get_intraday_bar_store_status(*, symbol: str = "SN", interval: str = "5m") -> dict[str, Any]:
    path = _manifest_path(symbol.upper(), interval.lower())
    payload = _read_json(path)
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "data_kind": "intraday_bar",
            "symbol": str(symbol or "SN").upper(),
            "exchange": "SHFE",
            "active_contract": "",
            "interval": str(interval or "5m").lower(),
            "provider": "",
            "fetched_at": "",
            "as_of": "",
            "row_count": 0,
            "bars_path": "",
            "manifest_path": str(path),
            "content_hash": "",
            "history_immutable": False,
            "immutable_intraday_bars": False,
            "latest_quote_used": False,
            "latest_quote_used_as_intraday_bar": False,
            "daily_bar_used_as_intraday": False,
            "sample_data_used": False,
            "baseline_used": False,
            "allowed_for_display": False,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "allowed_for_intraday_label": False,
            "blocking_reasons": ["intraday_bars_missing"],
        }
    )

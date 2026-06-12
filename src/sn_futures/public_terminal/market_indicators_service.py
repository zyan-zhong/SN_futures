from __future__ import annotations

import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.manifests import ManifestStore
from ..data_layer.stores import content_hash
from ..utils.secret_sanitizer import sanitize_mapping


INDICATOR_SCHEMA_VERSION = "public-market-indicators-v1"
MIN_BARS_FOR_INDICATORS = 35


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6)


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (1 - alpha))
    return result


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    window = values[-(period + 1) :]
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(window, window[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 6)


def _volatility(values: list[float], period: int = 20) -> float | None:
    if len(values) < period + 1:
        return None
    returns: list[float] = []
    for previous, current in zip(values[-(period + 1) :], values[-period:]):
        if previous == 0:
            continue
        returns.append((current / previous) - 1)
    if len(returns) < 2:
        return None
    return round(statistics.stdev(returns), 8)


def _latest_ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return round(_ema(values, period)[-1], 6)


def _atr(rows: list[Mapping[str, Any]], period: int = 14) -> float | None:
    if len(rows) < period + 1:
        return None
    true_ranges: list[float] = []
    for previous, current in zip(rows[-(period + 1) :], rows[-period:]):
        high = _to_float(current.get("high"))
        low = _to_float(current.get("low"))
        previous_close = _to_float(previous.get("close"))
        if high is None or low is None or previous_close is None:
            continue
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    if len(true_ranges) < period:
        return None
    return round(sum(true_ranges) / period, 6)


def _change_ratio(rows: list[Mapping[str, Any]], field: str) -> float | None:
    if len(rows) < 2:
        return None
    previous = _to_float(rows[-2].get(field))
    latest = _to_float(rows[-1].get(field))
    if previous is None or latest is None or previous == 0:
        return None
    return round((latest - previous) / previous, 8)


def _inventory_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else {}
    fields = ("warehouse_warrant", "inventory")
    summary: dict[str, Any] = {}
    for field in fields:
        latest_value = _to_float(latest.get(field))
        if latest_value is None:
            continue
        previous_value = _to_float(previous.get(field))
        summary[f"{field}_latest"] = latest_value
        summary[f"{field}_change_1"] = None if previous_value is None else round(latest_value - previous_value, 6)
    return summary


def _macd(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < MIN_BARS_FOR_INDICATORS:
        return None, None, None
    ema_12 = _ema(values, 12)
    ema_26 = _ema(values, 26)
    macd_line = [fast - slow for fast, slow in zip(ema_12, ema_26)]
    signal = _ema(macd_line, 9)
    if not macd_line or not signal:
        return None, None, None
    macd = round(macd_line[-1], 6)
    macd_signal = round(signal[-1], 6)
    macd_histogram = round(macd - macd_signal, 6)
    return macd, macd_signal, macd_histogram


def _write_manifest(manifest: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    return ManifestStore(output_dir=output_dir).write_manifest("public_market_indicators", dict(manifest))


def _blocked_manifest(rows: list[Mapping[str, Any]], reasons: list[str]) -> dict[str, Any]:
    source_published_at = str(rows[-1].get("source_published_at") or rows[-1].get("trade_date") or "") if rows else ""
    return _safe(
        {
            "schema_version": INDICATOR_SCHEMA_VERSION,
            "status": "blocked",
            "provider_id": "public_market",
            "data_kind": "technical_indicator",
            "row_count": len(rows),
            "indicator_count": 0,
            "indicator_names": [],
            "computed_at": _now(),
            "source_published_at": source_published_at,
            "content_hash": content_hash(rows),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": False,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "blocking_reasons": reasons,
        }
    )


def build_market_indicators(rows: list[Mapping[str, Any]], *, output_dir: Path | None = None) -> dict[str, Any]:
    row_list = [dict(row) for row in rows if isinstance(row, Mapping)]
    closes = [_to_float(row.get("close")) for row in row_list]
    close_values = [value for value in closes if value is not None]
    if len(close_values) < MIN_BARS_FOR_INDICATORS:
        reasons = ["missing_daily_bars"] if not row_list else ["insufficient_bars_for_indicators"]
        manifest = _write_manifest(_blocked_manifest(row_list, reasons), output_dir=output_dir)
        return _safe(
            {
                "status": "blocked",
                "values": {},
                "blocking_reasons": reasons,
                "inventory_summary": {},
                "manifest": manifest,
            }
        )

    macd, macd_signal, macd_histogram = _macd(close_values)
    values = {
        "sma_5": _mean(close_values[-5:]),
        "sma_20": _mean(close_values[-20:]),
        "ma_5": _mean(close_values[-5:]),
        "ma_20": _mean(close_values[-20:]),
        "ema_12": _latest_ema(close_values, 12),
        "ema_26": _latest_ema(close_values, 26),
        "rsi_14": _rsi(close_values, 14),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "atr_14": _atr(row_list, 14),
        "volatility_20": _volatility(close_values, 20),
        "volume_change_1": _change_ratio(row_list, "volume"),
        "open_interest_change_1": _change_ratio(row_list, "open_interest"),
    }
    if any(value is None for value in values.values()):
        reasons = ["insufficient_bars_for_indicators"]
        manifest = _write_manifest(_blocked_manifest(row_list, reasons), output_dir=output_dir)
        return _safe(
            {
                "status": "blocked",
                "values": {},
                "blocking_reasons": reasons,
                "inventory_summary": {},
                "manifest": manifest,
            }
        )

    inventory_summary = _inventory_summary(row_list)
    indicator_names = sorted(values)
    source_published_at = str(row_list[-1].get("source_published_at") or row_list[-1].get("trade_date") or "")
    manifest = _write_manifest(
        {
            "schema_version": INDICATOR_SCHEMA_VERSION,
            "status": "ready",
            "provider_id": "public_market",
            "data_kind": "technical_indicator",
            "row_count": len(row_list),
            "indicator_count": len(indicator_names),
            "indicator_names": indicator_names,
            "computed_at": _now(),
            "source_published_at": source_published_at,
            "content_hash": content_hash({"values": values, "inventory_summary": inventory_summary, "rows": row_list}),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": True,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "blocking_reasons": [],
        },
        output_dir=output_dir,
    )
    return _safe(
        {
            "status": "ready",
            "values": values,
            "inventory_summary": inventory_summary,
            "blocking_reasons": [],
            "manifest": manifest,
        }
    )

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
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


def _blocked_manifest(rows: list[Mapping[str, Any]], reasons: list[str]) -> dict[str, Any]:
    source_published_at = str(rows[-1].get("source_published_at") or rows[-1].get("trade_date") or "") if rows else ""
    return _safe(
        {
            "schema_version": INDICATOR_SCHEMA_VERSION,
            "status": "blocked",
            "row_count": len(rows),
            "indicator_count": 0,
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


def build_market_indicators(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    row_list = [dict(row) for row in rows if isinstance(row, Mapping)]
    closes = [_to_float(row.get("close")) for row in row_list]
    close_values = [value for value in closes if value is not None]
    if len(close_values) < MIN_BARS_FOR_INDICATORS:
        reasons = ["missing_daily_bars"] if not row_list else ["insufficient_bars_for_indicators"]
        return _safe(
            {
                "status": "blocked",
                "values": {},
                "blocking_reasons": reasons,
                "manifest": _blocked_manifest(row_list, reasons),
            }
        )

    macd, macd_signal, macd_histogram = _macd(close_values)
    values = {
        "sma_5": _mean(close_values[-5:]),
        "sma_20": _mean(close_values[-20:]),
        "ma_5": _mean(close_values[-5:]),
        "ma_20": _mean(close_values[-20:]),
        "rsi_14": _rsi(close_values, 14),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "volatility_20": _volatility(close_values, 20),
    }
    if any(value is None for value in values.values()):
        reasons = ["insufficient_bars_for_indicators"]
        return _safe(
            {
                "status": "blocked",
                "values": {},
                "blocking_reasons": reasons,
                "manifest": _blocked_manifest(row_list, reasons),
            }
        )

    source_published_at = str(row_list[-1].get("source_published_at") or row_list[-1].get("trade_date") or "")
    manifest = _safe(
        {
            "schema_version": INDICATOR_SCHEMA_VERSION,
            "status": "ready",
            "row_count": len(row_list),
            "indicator_count": len(values),
            "computed_at": _now(),
            "source_published_at": source_published_at,
            "content_hash": content_hash({"values": values, "rows": row_list}),
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
        }
    )
    return _safe(
        {
            "status": "ready",
            "values": values,
            "blocking_reasons": [],
            "manifest": manifest,
        }
    )

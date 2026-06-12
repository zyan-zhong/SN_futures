from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.intraday_store import IntradayStore
from ..data_layer.stores import NormalizedStore
from ..data_layer.watermark import WatermarkStore
from ..utils.secret_sanitizer import sanitize_mapping
from .market_indicators_service import build_market_indicators


DOWNSTREAM_FALSE_FLAGS = {
    "training_invoked": False,
    "prediction_generated": False,
    "backtest_invoked": False,
    "feature_store_written": False,
    "production_cache_written": False,
    "customer_prediction_generated": False,
}


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "sample", "fake", "demo"}
    return bool(value)


def _dirty_payload(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key in ("sample", "sample_data_used", "sample_mode", "fake", "fake_data_used", "demo", "demo_data_used", "baseline_used"):
            if _truthy(payload.get(key)):
                return True
        return any(_dirty_payload(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_dirty_payload(item) for item in payload)
    return False


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed == parsed else None


def _chart_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return _safe(
        {
            "date": row.get("trade_date") or row.get("date") or row.get("source_published_at"),
            "symbol": row.get("symbol") or "SN",
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "open_interest": row.get("open_interest"),
            "warehouse_warrant": row.get("warehouse_warrant"),
            "inventory": row.get("inventory"),
            "source_published_at": row.get("source_published_at") or row.get("trade_date") or row.get("date"),
        }
    )


def _blocked_market(*, reason: str, watermark: Mapping[str, Any], reasons: list[str] | None = None) -> dict[str, Any]:
    blocking_reasons = reasons or [reason]
    indicators = build_market_indicators([])
    return _safe(
        {
            "market": {
                "status": "blocked",
                "reason": reason,
                "chart": [],
                "kline": {"status": "blocked", "bars": [], "timeframe": "daily"},
                "watch_header": {
                    "status": "blocked",
                    "symbol": "SN",
                    "latest_price": None,
                    "daily_close": None,
                    "latest_quote_display_only": True,
                    "volume": None,
                    "open_interest": None,
                },
                "inventory": {"warehouse_warrant": None, "inventory": None},
                "latest_quote": None,
                "intraday_status": _intraday_status(None),
                "indicators": indicators,
                "data_watermark": dict(watermark),
                "data_watermark_panel": {
                    "display_allowed": False,
                    "prediction_allowed": False,
                    "cache_status": "missing",
                    "stale_status": "missing",
                    "source_published_at": "",
                },
                "missing_data": {"reasons": blocking_reasons},
                "sample_data_used": False,
                "baseline_used": False,
                "customer_prediction_generated": False,
            },
            **DOWNSTREAM_FALSE_FLAGS,
        }
    )


def _daily_record(watermark: Mapping[str, Any]) -> dict[str, Any]:
    records_by_kind = watermark.get("records_by_kind") if isinstance(watermark.get("records_by_kind"), Mapping) else {}
    daily = records_by_kind.get("daily_bar") if isinstance(records_by_kind.get("daily_bar"), Mapping) else {}
    return dict(daily)


def _latest_quote(output_dir: Path | None = None) -> dict[str, Any]:
    payload = IntradayStore(output_dir=output_dir).load_latest_quote(symbol="SN")
    quote = payload.get("quote") if isinstance(payload.get("quote"), Mapping) else {}
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}
    if not quote:
        return {}
    latest = _to_float(quote.get("latest_price") or quote.get("latest") or quote.get("price"))
    return _safe(
        {
            **dict(quote),
            "latest_price": latest,
            "quote_time": quote.get("quote_time") or quote.get("timestamp") or manifest.get("quote_time"),
            "display_only": True,
            "latest_quote_display_only": True,
            "manifest": manifest,
        }
    )


def _intraday_status(output_dir: Path | None = None) -> dict[str, Any]:
    payload = IntradayStore(output_dir=output_dir).load_latest_intraday_bars(symbol="SN")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}
    if _dirty_payload({"rows": rows, "manifest": manifest}):
        return _safe(
            {
                "status": "blocked",
                "reason": "no_demo_public_firewall",
                "interval": "",
                "row_count": 0,
                "latest_bar_time": "",
                "display_allowed": False,
                "prediction_allowed": False,
                "latest_quote_used_as_intraday_bar": False,
                "daily_bar_used_as_intraday": False,
                "blocking_reasons": ["no_demo_public_firewall"],
            }
        )
    if not rows:
        return _safe(
            {
                "status": "blocked",
                "reason": "missing_intraday_bars",
                "interval": "",
                "row_count": 0,
                "latest_bar_time": "",
                "display_allowed": False,
                "prediction_allowed": False,
                "latest_quote_used_as_intraday_bar": False,
                "daily_bar_used_as_intraday": False,
                "blocking_reasons": ["missing_intraday_bars"],
            }
        )
    latest_bar = rows[-1] if isinstance(rows[-1], Mapping) else {}
    return _safe(
        {
            "status": "ready",
            "reason": "",
            "interval": str(manifest.get("interval") or ""),
            "row_count": len(rows),
            "latest_bar_time": str(latest_bar.get("bar_end") or manifest.get("source_published_at") or ""),
            "source_published_at": str(manifest.get("source_published_at") or latest_bar.get("bar_end") or ""),
            "display_allowed": bool(manifest.get("allowed_for_display")),
            "prediction_allowed": False,
            "latest_quote_used_as_intraday_bar": False,
            "daily_bar_used_as_intraday": False,
            "blocking_reasons": [],
        }
    )


def _watch_header(chart: list[Mapping[str, Any]], latest_quote: Mapping[str, Any], status: str) -> dict[str, Any]:
    latest_bar = chart[-1] if chart else {}
    quote_price = _to_float(latest_quote.get("latest_price")) if latest_quote else None
    return _safe(
        {
            "status": status,
            "symbol": latest_bar.get("symbol") or latest_quote.get("symbol") or "SN",
            "latest_price": quote_price if quote_price is not None else _to_float(latest_bar.get("close")),
            "daily_close": _to_float(latest_bar.get("close")),
            "latest_quote_display_only": True,
            "quote_time": latest_quote.get("quote_time") if latest_quote else "",
            "trade_date": latest_bar.get("date"),
            "volume": latest_bar.get("volume"),
            "open_interest": latest_bar.get("open_interest"),
        }
    )


def _inventory(chart: list[Mapping[str, Any]]) -> dict[str, Any]:
    latest = chart[-1] if chart else {}
    return _safe(
        {
            "warehouse_warrant": latest.get("warehouse_warrant"),
            "inventory": latest.get("inventory"),
            "volume": latest.get("volume"),
            "open_interest": latest.get("open_interest"),
        }
    )


def build_public_market(output_dir: Path | None = None) -> dict[str, Any]:
    normalized = NormalizedStore(output_dir=output_dir).load_latest_by_kind("daily_bar")
    rows = normalized.get("rows") if isinstance(normalized.get("rows"), list) else []
    manifest = normalized.get("manifest") if isinstance(normalized.get("manifest"), Mapping) else {}
    watermark = WatermarkStore(output_dir=output_dir).load()

    if _dirty_payload({"rows": rows, "manifest": manifest}):
        return _blocked_market(reason="no_demo_public_firewall", watermark=watermark, reasons=["no_demo_public_firewall"])

    if not rows:
        return _blocked_market(reason="missing_daily_bars", watermark=watermark, reasons=["missing_daily_bars"])

    chart = [_chart_row(row) for row in rows if isinstance(row, Mapping)]
    daily_record = _daily_record(watermark)
    stale = str(manifest.get("stale_status") or daily_record.get("stale_status") or "").lower() == "stale"
    market_status = "stale" if stale else "ready"
    missing_reasons = ["stale_daily_bars"] if stale else []
    latest = _latest_quote(output_dir=output_dir)
    intraday_status = _intraday_status(output_dir=output_dir)
    indicators = build_market_indicators(chart, output_dir=output_dir)
    return _safe(
        {
            "market": {
                "status": market_status,
                "reason": "stale_daily_bars" if stale else "",
                "chart": chart[-240:],
                "kline": {"status": "ready", "bars": chart[-240:], "timeframe": "daily"},
                "watch_header": _watch_header(chart, latest, market_status),
                "inventory": _inventory(chart),
                "latest_quote": latest or None,
                "intraday_status": intraday_status,
                "indicators": indicators,
                "manifest": manifest,
                "data_watermark": watermark,
                "data_watermark_panel": {
                    "display_allowed": True,
                    "prediction_allowed": False,
                    "cache_status": manifest.get("cache_status") or daily_record.get("cache_status") or "unknown",
                    "stale_status": "stale" if stale else (manifest.get("stale_status") or daily_record.get("stale_status") or "fresh"),
                    "source_published_at": manifest.get("source_published_at") or daily_record.get("source_published_at") or "",
                },
                "missing_data": {"reasons": missing_reasons},
                "sample_data_used": False,
                "baseline_used": False,
                "customer_prediction_generated": False,
            },
            **DOWNSTREAM_FALSE_FLAGS,
        }
    )

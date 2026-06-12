from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .manifests import DataLayerContractError
from .stores import atomic_write_json, content_hash, data_layer_root, read_json, safe_part, safe_payload, utc_now, validate_no_sample


INTRADAY_STORE_SCHEMA_VERSION = "data-layer-intraday-store-v1"
LATEST_QUOTE_SCHEMA_VERSION = "data-layer-latest-quote-v1"
DAILY_INTERVALS = {"1d", "d", "day", "daily", "24h"}


class IntradayStore:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir

    @property
    def root(self) -> Path:
        return data_layer_root(self.output_dir) / "intraday"

    def persist_latest_quote(
        self,
        *,
        provider_id: str,
        symbol: str,
        quote: Mapping[str, Any],
        fetched_at: str = "",
    ) -> dict[str, Any]:
        fetched = str(fetched_at or utc_now())
        quote_time = str(quote.get("quote_time") or quote.get("timestamp") or "")
        manifest = {
            "schema_version": LATEST_QUOTE_SCHEMA_VERSION,
            "provider_id": str(provider_id or "unknown_provider"),
            "data_kind": "latest_quote",
            "symbol": str(symbol or "SN").upper(),
            "fetched_at": fetched,
            "source_published_at": quote_time,
            "quote_time": quote_time,
            "content_hash": content_hash(dict(quote)),
            "display_only": True,
            "latest_quote_display_only": True,
            "latest_quote_used_as_intraday_bar": False,
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": True,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "allowed_for_intraday_label": False,
            "blocking_reasons": ["latest_quote_is_display_tick_not_label_source"],
        }
        payload = {"quote": safe_payload(dict(quote)), "manifest": safe_payload(manifest)}
        validate_no_sample(payload)
        path = self.root / "latest_quote" / safe_part(provider_id, "unknown_provider") / f"{safe_part(symbol.upper(), 'SN')}.json"
        atomic_write_json(path, payload)
        return safe_payload(payload)

    def load_latest_quote(self, *, provider_id: str | None = None, symbol: str = "SN") -> dict[str, Any]:
        if provider_id:
            path = self.root / "latest_quote" / safe_part(provider_id, "unknown_provider") / f"{safe_part(symbol.upper(), 'SN')}.json"
            payload = read_json(path, {})
            return safe_payload(payload if isinstance(payload, Mapping) else {})
        candidates: list[dict[str, Any]] = []
        for path in (self.root / "latest_quote").glob(f"*/{safe_part(symbol.upper(), 'SN')}.json"):
            payload = read_json(path, {})
            if isinstance(payload, Mapping):
                candidates.append(dict(payload))
        if not candidates:
            return {}
        return safe_payload(
            max(
                candidates,
                key=lambda payload: str(
                    (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("quote_time")
                    or (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("fetched_at")
                    or ""
                ),
            )
        )

    def persist_intraday_bars(
        self,
        *,
        provider_id: str,
        symbol: str,
        interval: str,
        rows: list[Mapping[str, Any]],
        fetched_at: str = "",
    ) -> dict[str, Any]:
        clean_interval = str(interval or "").strip().lower()
        if clean_interval in DAILY_INTERVALS:
            raise DataLayerContractError("daily_not_intraday")
        row_list = [dict(row) for row in rows]
        validate_no_sample(row_list)
        manifest = {
            "schema_version": INTRADAY_STORE_SCHEMA_VERSION,
            "provider_id": str(provider_id or "unknown_provider"),
            "data_kind": "intraday_bar",
            "symbol": str(symbol or "SN").upper(),
            "interval": clean_interval,
            "row_count": len(row_list),
            "fetched_at": str(fetched_at or utc_now()),
            "source_published_at": str(row_list[-1].get("bar_end") if row_list else ""),
            "content_hash": content_hash(row_list),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "daily_bar_used_as_intraday": False,
            "latest_quote_used_as_intraday_bar": False,
            "allowed_for_display": bool(row_list),
            "allowed_for_feature_store": bool(row_list),
            "allowed_for_training": bool(row_list),
            "allowed_for_prediction": bool(row_list),
            "allowed_for_backtest": bool(row_list),
            "allowed_for_intraday_label": bool(row_list),
            "blocking_reasons": [] if row_list else ["intraday_bars_missing"],
        }
        payload = {"rows": safe_payload(row_list), "manifest": safe_payload(manifest)}
        path = self.root / "bars" / safe_part(symbol.upper(), "SN") / f"{safe_part(clean_interval, 'intraday')}.json"
        atomic_write_json(path, payload)
        return safe_payload(payload)

    def load_latest_intraday_bars(self, *, symbol: str = "SN") -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        for path in (self.root / "bars" / safe_part(symbol.upper(), "SN")).glob("*.json"):
            payload = read_json(path, {})
            if isinstance(payload, Mapping):
                candidates.append(dict(payload))
        if not candidates:
            return {}
        return safe_payload(
            max(
                candidates,
                key=lambda payload: str(
                    (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("source_published_at")
                    or (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("fetched_at")
                    or ""
                ),
            )
        )

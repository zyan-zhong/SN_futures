from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


WATERMARK_FIELDS = {
    "market_data_updated_at": "",
    "price_history_updated_at": "",
    "cross_market_updated_at": "",
    "news_updated_at": "",
    "event_factor_updated_at": "",
    "feature_store_updated_at": "",
    "training_dataset_updated_at": "",
    "candidate_updated_at": "",
    "backtest_updated_at": "",
    "active_model_updated_at": "",
    "provider_watermarks": {},
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _watermark_path() -> Path:
    return get_user_output_dir() / "data_watermark.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_watermark(payload: dict[str, Any]) -> None:
    path = _watermark_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_mapping(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_provider_watermarks(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from .provider_status_canonical_service import get_canonical_provider_status

        canonical = get_canonical_provider_status()
    except Exception:
        return payload
    providers = canonical.get("providers") if isinstance(canonical, dict) else {}
    if not isinstance(providers, dict):
        return payload
    watermarks = payload.get("provider_watermarks")
    if not isinstance(watermarks, dict):
        watermarks = {}
    changed = False
    for provider_id, row in providers.items():
        if not isinstance(row, dict):
            continue
        last_success = str(row.get("last_success_time") or "")
        last_attempt = str(row.get("last_attempt_time") or "")
        provider_row = dict(watermarks.get(provider_id) or {})
        next_row = {
            **provider_row,
            "status": row.get("status", ""),
            "last_attempt_time": last_attempt,
            "last_success_time": last_success,
            "from_cache": bool(row.get("from_cache")),
            "row_count": int(row.get("row_count") or 0),
        }
        if next_row != provider_row:
            watermarks[str(provider_id)] = next_row
            changed = True
        if provider_id == "newsapi" and last_success and row.get("status") in {"success", "using_cache", "using_cache_rate_limited"}:
            if payload.get("news_updated_at") != last_success:
                payload["news_updated_at"] = last_success
                changed = True
            if payload.get("event_factor_updated_at") != last_success:
                payload["event_factor_updated_at"] = last_success
                changed = True
        if provider_id == "alpha_vantage" and last_success and row.get("status") in {"success", "using_cache", "using_cache_rate_limited"}:
            if payload.get("cross_market_updated_at") != last_success:
                payload["cross_market_updated_at"] = last_success
                changed = True
    if changed:
        payload["provider_watermarks"] = watermarks
        payload["provider_watermarks_synced_at"] = _now()
    return payload


def _has_real_market_data(output_dir: Path) -> bool:
    candidates = [
        output_dir / "sn_market_history.json",
        output_dir / "market" / "sn_market_history.json",
        output_dir / "sn_live_snapshot.json",
    ]
    for path in candidates:
        if path.exists() and path.stat().st_size > 2:
            return True
    return False


def _derive_mode(payload: dict[str, Any], output_dir: Path) -> str:
    real = _has_real_market_data(output_dir)
    if real:
        return "real"
    if payload.get("market_data_updated_at") or payload.get("price_history_updated_at"):
        return "cache"
    return "sample"


def get_data_watermark_report() -> dict[str, Any]:
    output_dir = get_user_output_dir()
    payload = {**WATERMARK_FIELDS, **_read_json(_watermark_path())}
    payload = _sync_provider_watermarks(payload)
    payload["generated_at"] = _now()
    payload["sample_mode"] = _derive_mode(payload, output_dir) == "sample"
    payload["current_data_mode"] = _derive_mode(payload, output_dir)
    payload.setdefault("last_invalidation_reason", "")
    payload.setdefault("stale_reasons", [])
    if not isinstance(payload["stale_reasons"], list):
        payload["stale_reasons"] = [str(payload["stale_reasons"])]
    payload["freshness_summary"] = {
        "market": payload.get("market_data_updated_at") or "missing",
        "cross_market": payload.get("cross_market_updated_at") or "missing",
        "news": payload.get("news_updated_at") or "missing",
        "feature_store": payload.get("feature_store_updated_at") or "missing",
        "training_dataset": payload.get("training_dataset_updated_at") or "missing",
        "candidate": payload.get("candidate_updated_at") or "missing",
        "backtest": payload.get("backtest_updated_at") or "missing",
    }
    try:
        from .provenance_gate_service import build_runtime_provenance_report

        provenance = build_runtime_provenance_report(output_dir, aggregate_watermark=payload)
        gates = provenance.get("gates") if isinstance(provenance.get("gates"), dict) else {}
        prediction_gate = gates.get("prediction") if isinstance(gates.get("prediction"), dict) else {}
        payload["provenance_schema_version"] = provenance.get("schema_version")
        payload["provenance_records"] = provenance.get("records", [])
        payload["provenance_gates"] = gates
        payload["provenance_gate"] = prediction_gate
        payload["allowed_for_display"] = bool(gates.get("display", {}).get("allowed_for_display")) if isinstance(gates.get("display"), dict) else False
        payload["allowed_for_feature_store"] = bool(gates.get("feature_store", {}).get("allowed_for_feature_store")) if isinstance(gates.get("feature_store"), dict) else False
        payload["allowed_for_training"] = bool(gates.get("training", {}).get("allowed_for_training")) if isinstance(gates.get("training"), dict) else False
        payload["allowed_for_prediction"] = bool(prediction_gate.get("allowed_for_prediction")) if isinstance(prediction_gate, dict) else False
        payload["allowed_for_backtest"] = bool(gates.get("backtest", {}).get("allowed_for_backtest")) if isinstance(gates.get("backtest"), dict) else False
        payload["sample_data_used"] = bool(provenance.get("sample_data_used"))
        payload["baseline_used"] = bool(provenance.get("baseline_used"))
        payload["blocking_reasons"] = prediction_gate.get("blocking_reasons", []) if isinstance(prediction_gate.get("blocking_reasons"), list) else []
    except Exception:
        payload.setdefault("provenance_records", [])
        payload.setdefault("provenance_gates", {})
    if payload.get("provider_watermarks_synced_at"):
        _write_watermark(payload)
    return sanitize_for_json(sanitize_mapping(payload))


def update_data_watermark(kind: str, source: str = "", at_time: str | None = None, cache_used: bool = False) -> dict[str, Any]:
    kind = str(kind or "").strip()
    now = at_time or _now()
    payload = get_data_watermark_report()
    mapping = {
        "market": ("market_data_updated_at", "price_history_updated_at"),
        "refresh_market": ("market_data_updated_at", "price_history_updated_at"),
        "refresh_all": ("market_data_updated_at", "price_history_updated_at"),
        "cross_market": ("cross_market_updated_at",),
        "refresh_cross_market": ("cross_market_updated_at",),
        "news": ("news_updated_at", "event_factor_updated_at"),
        "refresh_news": ("news_updated_at", "event_factor_updated_at"),
        "event": ("event_factor_updated_at",),
        "feature_store": ("feature_store_updated_at",),
        "build_feature_store": ("feature_store_updated_at",),
        "training_dataset": ("training_dataset_updated_at",),
        "build_training_dataset": ("training_dataset_updated_at",),
        "candidate": ("candidate_updated_at",),
        "train_candidate": ("candidate_updated_at",),
        "backtest": ("backtest_updated_at",),
        "run_research_backtest": ("backtest_updated_at",),
        "active": ("active_model_updated_at",),
    }
    for field in mapping.get(kind, ()):
        payload[field] = now
    payload["last_update_kind"] = kind
    payload["last_update_source"] = str(source or "")
    payload["last_update_from_cache"] = bool(cache_used)
    payload["updated_at"] = now
    payload["current_data_mode"] = _derive_mode(payload, get_user_output_dir())
    payload["sample_mode"] = payload["current_data_mode"] == "sample"
    _write_watermark(payload)
    return get_data_watermark_report()


def update_provider_watermark(
    provider_id: str,
    *,
    status: str,
    last_attempt_time: str = "",
    last_success_time: str = "",
    row_count: int = 0,
    from_cache: bool = False,
) -> dict[str, Any]:
    payload = get_data_watermark_report()
    watermarks = payload.get("provider_watermarks")
    if not isinstance(watermarks, dict):
        watermarks = {}
    provider_id = str(provider_id or "").strip()
    watermarks[provider_id] = {
        "status": str(status or ""),
        "last_attempt_time": str(last_attempt_time or ""),
        "last_success_time": str(last_success_time or ""),
        "row_count": int(row_count or 0),
        "from_cache": bool(from_cache),
    }
    payload["provider_watermarks"] = watermarks
    if provider_id == "newsapi" and last_success_time:
        payload["news_updated_at"] = str(last_success_time)
        payload["event_factor_updated_at"] = str(last_success_time)
        payload["cache_used_at"] = str(last_attempt_time or _now()) if from_cache else payload.get("cache_used_at", "")
    if provider_id == "alpha_vantage" and last_success_time:
        payload["cross_market_updated_at"] = str(last_success_time)
        payload["cache_used_at"] = str(last_attempt_time or _now()) if from_cache else payload.get("cache_used_at", "")
    payload["updated_at"] = str(last_attempt_time or last_success_time or _now())
    payload["last_update_source"] = f"provider:{provider_id}"
    _write_watermark(payload)
    return get_data_watermark_report()

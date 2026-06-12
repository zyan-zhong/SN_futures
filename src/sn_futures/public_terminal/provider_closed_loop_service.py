from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.event_store import EventStore
from ..data_layer.provider_result_store import persist_provider_result
from ..data_layer.stores import content_hash
from ..data_layer.watermark import WatermarkStore
from ..data_providers.base import PROVIDER_SCHEMA_VERSION, ProviderResult
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .runtime import provider_smoke_report_path


CLOSED_LOOP_SCHEMA_VERSION = "provider-closed-loop-v1"
SUCCESS_STATUSES = {"success", "pass", "passed", "ready"}
SKIPPED_NO_REMOTE_CODES = {"remote_http_disabled", "remote_disabled", "skipped_no_remote"}
EVENT_DATA_KINDS = {"news_event", "policy_event"}

DOWNSTREAM_FLAGS = (
    "feature_store_written",
    "production_cache_written",
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "active_updated",
    "customer_prediction_generated",
)

PROVIDER_DATA_KINDS = {
    "alpha_vantage": "daily_bar",
    "newsapi": "news_event",
    "newsapi_news": "news_event",
    "akshare_news": "news_event",
    "tushare_futures": "futures_fundamentals",
    "shfe_public": "exchange_public",
    "public_policy_rss": "policy_event",
    "local_api_provider": "daily_bar",
    "custom_http_provider": "daily_bar",
}

PROVIDER_ALIASES = {
    "newsapi_news": "newsapi",
    "custom_http_provider": "local_api_provider",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _provider_id(payload: Mapping[str, Any], manifest: Mapping[str, Any], source_statuses: list[Mapping[str, Any]]) -> str:
    for source in (payload, manifest, *(source_statuses or [])):
        for key in ("provider_id", "provider", "source_id", "id"):
            text = str(source.get(key) or "").strip().lower()
            if text:
                return PROVIDER_ALIASES.get(text, text)
    return "unknown_provider"


def _normalize_error_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in SKIPPED_NO_REMOTE_CODES:
        return "remote_http_disabled"
    if text in {"timeout", "timed_out"}:
        return "request_timeout"
    if text in {"malformed", "schema_mismatch"}:
        return "malformed_response"
    return text


def _source_statuses(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = _as_list(payload.get("source_statuses"))
    if not raw:
        raw = _as_list(manifest.get("source_statuses"))
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _error_code(payload: Mapping[str, Any], manifest: Mapping[str, Any], source_statuses: list[Mapping[str, Any]]) -> str:
    for source in (payload, manifest):
        for key in ("error_code", "error", "reason"):
            text = _normalize_error_code(source.get(key))
            if text:
                return text
        reasons = _as_list(source.get("blocking_reasons"))
        if reasons:
            return _normalize_error_code(reasons[0])
    for status in source_statuses:
        text = _normalize_error_code(status.get("error_code") or status.get("error") or status.get("reason"))
        if text:
            return text
    return ""


def _rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[Any] = []
    for key in ("normalized_rows", "rows", "events", "articles", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(value)
            if rows:
                break
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _row_count(payload: Mapping[str, Any], manifest: Mapping[str, Any], rows: list[Mapping[str, Any]], source_statuses: list[Mapping[str, Any]]) -> int:
    for value in (
        len(rows),
        payload.get("normalized_row_count"),
        payload.get("row_count"),
        manifest.get("normalized_row_count"),
        manifest.get("row_count"),
    ):
        count = _safe_int(value)
        if count:
            return count
    return max((_safe_int(status.get("row_count")) for status in source_statuses), default=0)


def _success(payload: Mapping[str, Any], *, row_count: int, error_code: str) -> bool:
    status = str(payload.get("status") or payload.get("status_code") or "").strip().lower()
    return row_count > 0 and not error_code and (bool(payload.get("success")) or status in SUCCESS_STATUSES)


def _source_published_at(rows: list[Mapping[str, Any]], payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    explicit = str(
        payload.get("source_published_at")
        or payload.get("source_timestamp")
        or manifest.get("source_published_at")
        or manifest.get("source_timestamp")
        or ""
    ).strip()
    if explicit:
        return explicit
    values = [
        str(
            row.get("source_published_at")
            or row.get("published_at")
            or row.get("source_timestamp")
            or row.get("trade_date")
            or row.get("date")
            or ""
        )
        for row in rows
    ]
    values = [value for value in values if value]
    return max(values) if values else ""


def _data_kind(provider_id: str, rows: list[Mapping[str, Any]], payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    if not rows:
        return "provider_smoke_status"
    if all(str(row.get("data_kind") or "") == "provider_smoke_status" for row in rows):
        return "provider_smoke_status"
    declared = str(payload.get("data_kind") or manifest.get("data_kind") or "").strip()
    if declared == "market_daily_bar":
        return "daily_bar"
    return PROVIDER_DATA_KINDS.get(provider_id, declared or "provider_data")


def _smoke_status_row(provider_id: str, row_count: int, fetched_at: str) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "status": "success",
        "row_count": int(row_count),
        "source_published_at": fetched_at,
        "fetched_at": fetched_at,
        "data_kind": "provider_smoke_status",
        "business_rows_absent": True,
    }


def provider_result_from_smoke_result(result: Mapping[str, Any], *, source: str) -> ProviderResult:
    payload = _safe(dict(result))
    manifest = _as_mapping(payload.get("manifest"))
    source_statuses = _source_statuses(payload, manifest)
    provider_id = _provider_id(payload, manifest, source_statuses)
    rows = _rows(payload)
    row_count = _row_count(payload, manifest, rows, source_statuses)
    error_code = _error_code(payload, manifest, source_statuses)
    success = _success(payload, row_count=row_count, error_code=error_code)
    fetched_at = str(payload.get("fetched_at") or manifest.get("fetched_at") or _now())

    if success and not rows and row_count > 0:
        rows = [_smoke_status_row(provider_id, row_count, fetched_at)]
    if not success and not error_code:
        error_code = "no_rows" if row_count == 0 else "provider_smoke_blocked"

    source_published_at = _source_published_at(rows, payload, manifest)
    data_kind = _data_kind(provider_id, rows if success else [], payload, manifest)
    blocking_reasons = [] if success else [error_code]
    normalized_source_statuses = [
        _safe(
            {
                **dict(status),
                "provider_id": str(status.get("provider_id") or status.get("source_id") or provider_id).lower(),
                "source_id": str(status.get("source_id") or status.get("provider_id") or provider_id).lower(),
                "status": "success" if success else "blocked",
                "success": bool(success),
                "row_count": len(rows) if success else 0,
                "error_code": "" if success else error_code,
                "timed_out": bool(status.get("timed_out") or error_code == "request_timeout"),
            }
        )
        for status in (source_statuses or [{"provider_id": provider_id}])
    ]
    normalized_manifest = _safe(
        {
            **dict(manifest),
            "schema_version": CLOSED_LOOP_SCHEMA_VERSION,
            "provider_interface_schema_version": PROVIDER_SCHEMA_VERSION,
            "provider_id": provider_id,
            "data_kind": data_kind,
            "source": source,
            "allow_remote": bool(payload.get("allow_remote") or manifest.get("allow_remote")),
            "fetched_at": fetched_at,
            "source_published_at": source_published_at,
            "source_timestamp": source_published_at,
            "as_of": source_published_at or fetched_at,
            "row_count": len(rows) if success else 0,
            "normalized_row_count": len(rows) if success else 0,
            "source_statuses": normalized_source_statuses,
            "cache_status": str(manifest.get("cache_status") or ("remote" if success else "missing")),
            "stale_status": str(manifest.get("stale_status") or ("fresh" if success else "missing")),
            "content_hash": content_hash(rows if success else {"provider_id": provider_id, "error_code": error_code}),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": bool(success),
            "allowed_for_public": False,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "blocking_reasons": blocking_reasons,
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )
    return ProviderResult(
        provider_id=provider_id,
        data_kind=data_kind,
        success=bool(success),
        status_code="success" if success else "blocked",
        error_code="" if success else error_code,
        rows=[dict(row) for row in rows] if success else [],
        normalized_rows=[dict(row) for row in rows] if success else [],
        fetched_at=fetched_at,
        source_timestamp=source_published_at,
        as_of=source_published_at or fetched_at if success else "",
        from_cache=str(normalized_manifest.get("cache_status")) == "cache",
        stale=str(normalized_manifest.get("stale_status")) == "stale",
        rate_limited=error_code == "rate_limited",
        schema_version=PROVIDER_SCHEMA_VERSION,
        manifest=normalized_manifest,
        sanitized_error="" if success else sanitize_text(str(payload.get("sanitized_error") or error_code)),
    )


def _load_smoke_report() -> dict[str, Any]:
    path = provider_smoke_report_path()
    if not path.exists():
        return {
            "schema_version": "public-terminal-provider-smoke-bridge-v1",
            "generated_at": _now(),
            "status": "blocked",
            "passed_count": 0,
            "failed_count": 0,
            "passed_providers": [],
            "providers": [],
            "source_statuses": [],
            "blocking_reasons": ["no_provider_smoke_report"],
            "report_path": str(path),
            **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _smoke_item(result: ProviderResult) -> dict[str, Any]:
    source_statuses = _as_list(result.manifest.get("source_statuses"))
    return _safe(
        {
            "provider_id": result.provider_id,
            "source": result.manifest.get("source") or "provider_closed_loop",
            "status": "success" if result.success else "blocked",
            "success": bool(result.success),
            "error_code": "" if result.success else result.error_code,
            "row_count": len(result.normalized_rows),
            "source_statuses": source_statuses,
            "manifest": result.manifest,
            "blocking_reasons": [] if result.success else [result.error_code],
            **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
        }
    )


def _write_smoke_report(results: list[ProviderResult]) -> dict[str, Any]:
    current = _load_smoke_report()
    providers = [
        dict(provider)
        for provider in _as_list(current.get("providers"))
        if isinstance(provider, Mapping) and str(provider.get("provider_id")) not in {result.provider_id for result in results}
    ]
    providers.extend(_smoke_item(result) for result in results)
    passed = [provider for provider in providers if provider.get("status") == "success"]
    failed = [provider for provider in providers if provider.get("status") != "success"]
    source_statuses = [
        dict(status)
        for provider in providers
        for status in _as_list(provider.get("source_statuses"))
        if isinstance(status, Mapping)
    ]
    blocking_reasons = sorted(
        {
            str(reason)
            for provider in failed
            for reason in _as_list(provider.get("blocking_reasons") or ([provider.get("error_code")] if provider.get("error_code") else []))
            if str(reason or "").strip()
        }
    )
    report = _safe(
        {
            "schema_version": "public-terminal-provider-smoke-bridge-v1",
            "generated_at": _now(),
            "status": "success" if passed else "blocked",
            "passed_count": len(passed),
            "failed_count": len(failed),
            "passed_providers": [str(provider.get("provider_id")) for provider in passed],
            "providers": providers,
            "source_statuses": source_statuses,
            "blocking_reasons": blocking_reasons or ([] if passed else ["no_active_provider_smoke_pass"]),
            "report_path": str(provider_smoke_report_path()),
            **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
        }
    )
    path = provider_smoke_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _watermark_record(result: ProviderResult) -> dict[str, Any]:
    return {
        "provider_id": result.provider_id,
        "data_kind": result.data_kind,
        "row_count": len(result.normalized_rows),
        "fetched_at": result.fetched_at,
        "source_published_at": result.source_timestamp,
        "cache_status": str(result.manifest.get("cache_status") or ("remote" if result.success else "missing")),
        "stale_status": str(result.manifest.get("stale_status") or ("fresh" if result.success else "missing")),
        "content_hash": str(result.manifest.get("content_hash") or content_hash(result.normalized_rows)),
        "blocking_reasons": list(result.manifest.get("blocking_reasons") or ([] if result.success else [result.error_code])),
    }


def _persist_events(result: ProviderResult) -> None:
    if result.data_kind not in EVENT_DATA_KINDS or not result.normalized_rows:
        return
    store = EventStore()
    for row in result.normalized_rows:
        store.persist_event(
            provider_id=result.provider_id,
            data_kind=result.data_kind,
            event=row,
            fetched_at=result.fetched_at,
        )


def _update_watermark(results: list[ProviderResult]) -> dict[str, Any]:
    store = WatermarkStore()
    existing = store.load()
    current_records = [
        dict(record)
        for record in _as_list(existing.get("records"))
        if isinstance(record, Mapping) and existing.get("reason") != "missing_data_layer_watermark"
    ]
    replacement_keys = {(result.provider_id, result.data_kind) for result in results}
    kept = [
        record
        for record in current_records
        if (str(record.get("provider_id")), str(record.get("data_kind"))) not in replacement_keys
    ]
    records = [*kept, *[_watermark_record(result) for result in results]]
    return store.merge_records(records)


def _persist_results(results: list[ProviderResult], *, write_smoke_report: bool) -> dict[str, Any]:
    provider_payloads: list[dict[str, Any]] = []
    for result in results:
        paths = persist_provider_result(result)
        _persist_events(result)
        provider_payloads.append(_safe({**result.to_dict(), "paths": paths}))
    watermark = _update_watermark(results)
    smoke_report = _write_smoke_report(results) if write_smoke_report else {}
    return _safe(
        {
            "schema_version": CLOSED_LOOP_SCHEMA_VERSION,
            "status": "success" if any(result.success for result in results) else "blocked",
            "provider_results": provider_payloads,
            "data_watermark": watermark,
            "provider_smoke_report": smoke_report,
            **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
        }
    )


def record_provider_closed_loop_result(
    result: Mapping[str, Any],
    *,
    source: str = "provider_closed_loop",
    write_smoke_report: bool = True,
) -> dict[str, Any]:
    return record_provider_closed_loop_report(
        {"providers": [dict(result)]},
        source=source,
        write_smoke_report=write_smoke_report,
    )


def record_provider_closed_loop_report(
    report: Mapping[str, Any],
    *,
    source: str = "provider_closed_loop",
    write_smoke_report: bool = True,
) -> dict[str, Any]:
    provider_items = _as_list(report.get("providers")) if isinstance(report.get("providers"), list) else [report]
    results = [
        provider_result_from_smoke_result(dict(item), source=source)
        for item in provider_items
        if isinstance(item, Mapping)
    ]
    if not results:
        return _safe(
            {
                "schema_version": CLOSED_LOOP_SCHEMA_VERSION,
                "status": "blocked",
                "provider_results": [],
                "data_watermark": WatermarkStore().load(),
                "provider_smoke_report": {},
                **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
            }
        )
    return _persist_results(results, write_smoke_report=write_smoke_report)


def build_provider_closed_loop_refresh_status(report: Mapping[str, Any]) -> dict[str, Any]:
    closed_loop = record_provider_closed_loop_report(report, source="public_refresh", write_smoke_report=False)
    watermark = closed_loop.get("data_watermark") if isinstance(closed_loop.get("data_watermark"), Mapping) else WatermarkStore().load()
    records = [dict(record) for record in _as_list(watermark.get("records")) if isinstance(record, Mapping)]
    ready_records = [record for record in records if record.get("status") == "ready" and _safe_int(record.get("row_count")) > 0]
    if not ready_records:
        return _safe(
            {
                "status": "blocked",
                "reason": "no_active_provider_smoke_pass",
                "data_watermark": watermark,
                "provider_coverage": records,
                "missing_data": ["provider_closed_loop_ready_record"],
                **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
            }
        )
    return _safe(
        {
            "status": "success",
            "reason": "",
            "data_watermark": watermark,
            "provider_coverage": ready_records,
            "missing_data": [],
            "row_count": sum(_safe_int(record.get("row_count")) for record in ready_records),
            **{flag: False for flag in DOWNSTREAM_FLAGS if flag != "active_updated"},
        }
    )

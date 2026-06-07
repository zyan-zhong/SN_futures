from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..data_providers.base import PROVIDER_SCHEMA_VERSION, ProviderResult
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


BRIDGE_SCHEMA_VERSION = "provider-result-service-bridge-v1"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any, secrets: Iterable[str] = ()) -> Any:
    return sanitize_for_json(sanitize_mapping(payload, extra_secrets=secrets))


def _content_hash(payload: Any, secrets: Iterable[str] = ()) -> str:
    encoded = json.dumps(_safe(payload, secrets), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _status_text(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("error_code") or "").strip().lower()


def _classify_error(payload: Mapping[str, Any]) -> str:
    explicit = str(payload.get("error_code") or "").strip().lower()
    status = _status_text(payload)
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("status", "error_code", "message_zh", "error_message_zh", "message", "sanitized_error")
    ).lower()
    if explicit:
        return explicit
    if status in {"success", "pass", "usable"}:
        return ""
    if status in {"token_missing", "key_missing", "not_configured"}:
        return "token_missing" if "token" in status else status
    if "waf" in status or "blocked_by_waf" in text or "captcha" in text:
        return "waf_blocked"
    if "rate" in text or "limit" in text or "429" in text:
        return "rate_limited"
    if "missing_required_columns" in text or "schema_mismatch" in text:
        return "missing_required_columns"
    if "malformed" in text or "parse" in text:
        return "malformed_response"
    if "network" in text or "timeout" in text or "connection" in text:
        return "network_failed"
    if status in {"no_rows", "no_tin_rows", "empty"}:
        return "no_rows"
    return status or "request_failed"


def _rows_from_payload(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    rows: list[Any] = []
    for key in ("rows", "events", "articles", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(value)

    results = payload.get("results")
    if isinstance(results, Mapping):
        for nested in results.values():
            if not isinstance(nested, Mapping):
                continue
            for key in ("rows", "events", "articles", "items", "data"):
                value = nested.get(key)
                if isinstance(value, list):
                    rows.extend(value)

    if any(not isinstance(row, Mapping) for row in rows):
        return [], "malformed_response"
    return [dict(row) for row in rows if isinstance(row, Mapping)], ""


def _source_timestamp(rows: Sequence[Mapping[str, Any]]) -> str:
    values = [
        str(
            row.get("source_published_at")
            or row.get("published_at")
            or row.get("source_timestamp")
            or row.get("trade_date")
            or ""
        )
        for row in rows
    ]
    values = [value for value in values if value]
    return max(values) if values else ""


def _missing_required_columns(rows: Sequence[Mapping[str, Any]], required_fields: Sequence[str]) -> list[str]:
    missing: set[str] = set()
    for row in rows:
        for field in required_fields:
            if not str(row.get(field) or "").strip():
                missing.add(field)
    return sorted(missing)


def _source_status_from_item(
    source_id: str,
    item: Mapping[str, Any],
    *,
    provider_id: str,
    secrets: Iterable[str],
) -> dict[str, Any]:
    success = bool(item.get("success")) or _status_text(item) in {"success", "pass", "usable"}
    error_code = "" if success else _classify_error(item)
    return _safe(
        {
            "source_id": source_id,
            "provider_id": provider_id,
            "function_name": item.get("function_name") or source_id,
            "success": success,
            "row_count": _safe_int(item.get("row_count")),
            "error_code": error_code,
            "error_message_sanitized": sanitize_text(
                item.get("error_message_zh") or item.get("message_zh") or item.get("message") or error_code,
                extra_secrets=secrets,
            ),
        },
        secrets,
    )


def _source_statuses(provider_id: str, service_output: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], secrets: Iterable[str]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    results = service_output.get("results")
    if isinstance(results, Mapping):
        for source_id, item in results.items():
            if isinstance(item, Mapping):
                statuses.append(_source_status_from_item(str(source_id), item, provider_id=provider_id, secrets=secrets))
    if not statuses:
        statuses.append(
            _source_status_from_item(
                str(service_output.get("function_name") or service_output.get("source_name") or provider_id),
                {**dict(service_output), "row_count": len(rows)},
                provider_id=provider_id,
                secrets=secrets,
            )
        )
    return statuses


def _normalise_policy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if not str(item.get("source_published_at") or item.get("published_at") or "").strip():
            item["used_in_model"] = False
            item["allowed_for_event_factor"] = False
            item["rejection_reason"] = "missing_source_published_at"
            item["event_time_confidence"] = 0.25
        else:
            item["source_published_at"] = str(item.get("source_published_at") or item.get("published_at"))
            item["event_time_confidence"] = item.get("event_time_confidence", 1.0)
        normalized.append(item)
    return normalized


def _provider_results_dir(provider_id: str, output_dir: Path | None = None) -> Path:
    root = output_dir or get_user_output_dir()
    path = root / "provider_results" / provider_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_provider_result_bridge(result: ProviderResult, output_dir: Path | None = None) -> dict[str, str]:
    path = _provider_results_dir(result.provider_id, output_dir)
    result_path = path / "latest_result.json"
    status_path = path / "latest_status.json"
    result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    status_path.write_text(json.dumps(result.to_status().to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"result_path": str(result_path), "status_path": str(status_path)}


def bridge_service_output_to_provider_result(
    *,
    provider_id: str,
    data_kind: str,
    service_output: Mapping[str, Any],
    required_fields: Sequence[str] = (),
    secrets: Iterable[str] = (),
    persist: bool = False,
    output_dir: Path | None = None,
    policy_event_rows: bool = False,
) -> ProviderResult:
    fetched_at = str(service_output.get("generated_at") or service_output.get("fetched_at") or _now())
    rows, row_error = _rows_from_payload(service_output)
    if row_error:
        rows = []
    normalized_rows = _normalise_policy_rows(rows) if policy_event_rows else [dict(row) for row in rows]
    missing = _missing_required_columns(normalized_rows, required_fields) if normalized_rows else []

    declared_success = bool(service_output.get("success")) or _status_text(service_output) in {"success", "pass", "usable"}
    error_code = row_error
    if not error_code and not declared_success:
        error_code = _classify_error(service_output)
    if not error_code and declared_success and not normalized_rows:
        error_code = "no_rows"
    if not error_code and missing:
        error_code = "missing_required_columns"

    success = not error_code and bool(normalized_rows)
    if not success:
        normalized_rows = []
    source_statuses = _source_statuses(provider_id, service_output, rows, secrets)
    if error_code and not any(status.get("error_code") for status in source_statuses):
        source_statuses[0]["success"] = False
        source_statuses[0]["error_code"] = error_code
    source_timestamp = _source_timestamp(normalized_rows)
    content_basis = {"rows": rows, "normalized_rows": normalized_rows, "service_output": service_output}
    published_count = len([row for row in normalized_rows if str(row.get("source_published_at") or row.get("published_at") or "").strip()])
    coverage = round(published_count / len(normalized_rows), 4) if normalized_rows else 0.0
    blocking_reasons = [] if success else [error_code or "provider_result_blocked"]
    if missing:
        blocking_reasons.append("missing required columns: " + ", ".join(missing))

    manifest = _safe(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "provider_interface_schema_version": PROVIDER_SCHEMA_VERSION,
            "provider_id": provider_id,
            "data_kind": data_kind,
            "fetched_at": fetched_at,
            "source_timestamp": source_timestamp,
            "as_of": source_timestamp or fetched_at,
            "row_count": len(rows),
            "normalized_row_count": len(normalized_rows),
            "source_statuses": source_statuses,
            "cache_status": "cache" if bool(service_output.get("from_cache") or service_output.get("cache_used")) else ("missing" if not rows else "remote"),
            "stale_status": "stale" if bool(service_output.get("stale")) else ("missing" if not rows else "fresh"),
            "content_hash": _content_hash(content_basis, secrets),
            "source_published_at_coverage": coverage,
            "sample_data_used": False,
            "baseline_used": False,
            "safe_refresh_available": False,
            "allowed_for_display": success,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "feature_store_written": False,
            "training_invoked": False,
            "backtest_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "blocking_reasons": blocking_reasons,
            "service_status": service_output.get("status") or "",
        },
        secrets,
    )
    sanitized_error = sanitize_text(
        service_output.get("error_message_zh") or service_output.get("message_zh") or error_code,
        extra_secrets=secrets,
    )
    result = ProviderResult(
        provider_id=provider_id,
        data_kind=data_kind,
        success=success,
        status_code=str(service_output.get("status_code") or service_output.get("status") or ""),
        error_code="" if success else (error_code or "request_failed"),
        rows=[dict(row) for row in rows],
        normalized_rows=[dict(row) for row in normalized_rows],
        fetched_at=fetched_at,
        source_timestamp=source_timestamp,
        as_of=source_timestamp or fetched_at if success else "",
        from_cache=bool(service_output.get("from_cache") or service_output.get("cache_used")),
        stale=bool(service_output.get("stale")),
        rate_limited=bool(error_code == "rate_limited" or service_output.get("rate_limited")),
        schema_version=PROVIDER_SCHEMA_VERSION,
        manifest=manifest,
        sanitized_error="" if success else sanitized_error,
    )
    if persist:
        paths = write_provider_result_bridge(result, output_dir)
        manifest = dict(result.manifest)
        manifest.update(paths)
        result = replace(result, manifest=_safe(manifest, secrets))
        write_provider_result_bridge(result, output_dir)
    return result


def bridge_tushare_service_output(
    service_output: Mapping[str, Any],
    *,
    secrets: Iterable[str] = (),
    persist: bool = False,
    output_dir: Path | None = None,
) -> ProviderResult:
    return bridge_service_output_to_provider_result(
        provider_id="tushare_futures",
        data_kind="futures_fundamentals",
        service_output=service_output,
        required_fields=("ts_code", "trade_date"),
        secrets=secrets,
        persist=persist,
        output_dir=output_dir,
    )


def bridge_shfe_public_service_output(
    service_output: Mapping[str, Any],
    *,
    secrets: Iterable[str] = (),
    persist: bool = False,
    output_dir: Path | None = None,
) -> ProviderResult:
    return bridge_service_output_to_provider_result(
        provider_id="shfe_public",
        data_kind="exchange_public",
        service_output=service_output,
        required_fields=("symbol", "trade_date"),
        secrets=secrets,
        persist=persist,
        output_dir=output_dir,
    )


def bridge_public_policy_rss_service_output(
    service_output: Mapping[str, Any],
    *,
    secrets: Iterable[str] = (),
    persist: bool = False,
    output_dir: Path | None = None,
) -> ProviderResult:
    return bridge_service_output_to_provider_result(
        provider_id="public_policy_rss",
        data_kind="policy",
        service_output=service_output,
        required_fields=("title", "url"),
        secrets=secrets,
        persist=persist,
        output_dir=output_dir,
        policy_event_rows=True,
    )

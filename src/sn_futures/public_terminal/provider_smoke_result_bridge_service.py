from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..utils.secret_sanitizer import sanitize_mapping
from .provider_closed_loop_service import record_provider_closed_loop_report
from .runtime import provider_smoke_report_path


BRIDGE_SCHEMA_VERSION = "public-terminal-provider-smoke-bridge-v1"
DOWNSTREAM_FLAGS = (
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "feature_store_written",
    "production_cache_written",
    "customer_prediction_generated",
)
SUCCESS_STATUSES = {"success", "pass", "passed", "ready"}
REMOTE_DISABLED_CODES = {"remote_http_disabled", "remote_disabled", "skipped_no_remote"}


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


def _nested_status(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    status = payload.get("status")
    return status if isinstance(status, Mapping) else {}


def _normalize_error_code(value: Any) -> str:
    text = str(value or "").strip()
    return "remote_http_disabled" if text.lower() in REMOTE_DISABLED_CODES else text


def _provider_id(payload: Mapping[str, Any], source_statuses: list[Mapping[str, Any]]) -> str:
    for key in ("provider_id", "provider", "source_id", "id"):
        value = str(payload.get(key) or "").strip().lower()
        if value:
            return value
    for status in source_statuses:
        for key in ("provider_id", "provider", "source_id", "id"):
            value = str(status.get(key) or "").strip().lower()
            if value:
                return value
    return "unknown_provider"


def _row_count(payload: Mapping[str, Any], manifest: Mapping[str, Any], source_statuses: list[Mapping[str, Any]]) -> int:
    direct = _safe_int(payload.get("row_count"))
    if direct:
        return direct
    nested_rows = _safe_int(_nested_status(payload).get("normalized_row_count") or _nested_status(payload).get("row_count"))
    if nested_rows:
        return nested_rows
    manifest_rows = _safe_int(manifest.get("normalized_row_count") or manifest.get("row_count"))
    if manifest_rows:
        return manifest_rows
    return max((_safe_int(status.get("row_count")) for status in source_statuses), default=0)


def _error_code(payload: Mapping[str, Any], manifest: Mapping[str, Any], source_statuses: list[Mapping[str, Any]]) -> str:
    for value in (payload.get("error_code"), payload.get("error"), payload.get("reason")):
        text = _normalize_error_code(value)
        if text:
            return text
    nested = _nested_status(payload)
    for value in (nested.get("error_code"), nested.get("error"), nested.get("reason")):
        text = _normalize_error_code(value)
        if text:
            return text
    reasons = _as_list(manifest.get("blocking_reasons") or payload.get("blocking_reasons"))
    if reasons:
        return _normalize_error_code(reasons[0])
    nested_reasons = _as_list(nested.get("blocking_reasons"))
    if nested_reasons:
        return _normalize_error_code(nested_reasons[0])
    for status in source_statuses:
        text = _normalize_error_code(status.get("error_code") or status.get("error"))
        if text:
            return text
    return ""


def _source_statuses(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = _as_list(payload.get("source_statuses"))
    if not raw:
        raw = _as_list(manifest.get("source_statuses"))
    if not raw:
        raw = _as_list(_nested_status(payload).get("source_statuses"))
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _is_success(payload: Mapping[str, Any], *, row_count: int, error_code: str) -> bool:
    nested = _nested_status(payload)
    status = str(
        nested.get("status")
        or nested.get("status_code")
        or payload.get("status")
        or payload.get("status_code")
        or ""
    ).strip().lower()
    success = bool(payload.get("success"))
    return row_count > 0 and not error_code and (success or status in SUCCESS_STATUSES)


def _empty_report() -> dict[str, Any]:
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "blocked",
        "passed_count": 0,
        "failed_count": 0,
        "providers": [],
        "source_statuses": [],
        "blocking_reasons": ["no_provider_smoke_report"],
        **{flag: False for flag in DOWNSTREAM_FLAGS},
    }


def _load_existing() -> dict[str, Any]:
    path = provider_smoke_report_path()
    if not path.exists():
        return _empty_report()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_report()
    return dict(payload) if isinstance(payload, Mapping) else _empty_report()


def _normalize_result(result: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    manifest = _as_mapping(result.get("manifest"))
    source_statuses = _source_statuses(result, manifest)
    provider_id = _provider_id(result, source_statuses)
    row_count = _row_count(result, manifest, source_statuses)
    error_code = _error_code(result, manifest, source_statuses)
    success = _is_success(result, row_count=row_count, error_code=error_code)
    status = "success" if success else "blocked"
    blocking_reasons = [] if success else [error_code or "provider_smoke_blocked"]
    normalized_source_statuses = [
        _safe(
            {
                **dict(status_item),
                "provider_id": str(status_item.get("provider_id") or status_item.get("source_id") or provider_id).lower(),
                "source_id": str(status_item.get("source_id") or status_item.get("provider_id") or provider_id).lower(),
                "status": "success" if success else "blocked",
                "success": bool(success),
                "row_count": row_count,
                "error_code": "" if success else error_code,
            }
        )
        for status_item in (source_statuses or [{"provider_id": provider_id}])
    ]
    normalized_manifest = _safe(
        {
            **dict(manifest),
            "provider_id": provider_id,
            "source": source,
            "row_count": row_count,
            "normalized_row_count": _safe_int(manifest.get("normalized_row_count")) or row_count,
            "source_statuses": normalized_source_statuses,
            "blocking_reasons": blocking_reasons,
            "sample_data_used": False,
            "baseline_used": False,
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )
    return _safe(
        {
            "provider_id": provider_id,
            "source": source,
            "status": status,
            "success": success,
            "error_code": "" if success else error_code,
            "row_count": row_count,
            "source_statuses": normalized_source_statuses,
            "manifest": normalized_manifest,
            "blocking_reasons": blocking_reasons,
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )


def _merge_provider(report: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = str(item.get("provider_id") or "unknown_provider")
    providers = [
        dict(provider)
        for provider in _as_list(report.get("providers"))
        if isinstance(provider, Mapping) and str(provider.get("provider_id")) != provider_id
    ]
    providers.append(dict(item))
    passed = [provider for provider in providers if provider.get("status") == "success"]
    failed = [provider for provider in providers if provider.get("status") != "success"]
    blocking_reasons = sorted(
        {
            str(reason)
            for provider in failed
            for reason in _as_list(provider.get("blocking_reasons") or ([provider.get("error_code")] if provider.get("error_code") else []))
            if str(reason or "").strip()
        }
    )
    source_statuses = [
        dict(status_item)
        for provider in providers
        for status_item in _as_list(provider.get("source_statuses"))
        if isinstance(status_item, Mapping)
    ]
    return _safe(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "generated_at": _now(),
            "status": "success" if passed else "blocked",
            "passed_count": len(passed),
            "failed_count": len(failed),
            "passed_providers": [str(provider.get("provider_id")) for provider in passed],
            "providers": providers,
            "source_statuses": source_statuses,
            "blocking_reasons": blocking_reasons or ([] if passed else ["no_active_provider_smoke_pass"]),
            "report_path": str(provider_smoke_report_path()),
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )


def bridge_provider_smoke_result(result: Mapping[str, Any], *, source: str = "provider_only_harness", write: bool = True) -> dict[str, Any]:
    """Convert a legacy provider test or provider-only harness result into the Public Terminal smoke report."""

    payload = _safe(result)
    if isinstance(payload, Mapping) and isinstance(payload.get("providers"), list):
        report = _load_existing()
        for item in payload["providers"]:
            if isinstance(item, Mapping):
                report = _merge_provider(report, _normalize_result(item, source=source))
    else:
        report = _merge_provider(_load_existing(), _normalize_result(_as_mapping(payload), source=source))

    if write:
        path = provider_smoke_report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        record_provider_closed_loop_report(report, source=source, write_smoke_report=False)
    return report


def get_public_provider_smoke_report() -> dict[str, Any]:
    report = _load_existing()
    return _safe(report)

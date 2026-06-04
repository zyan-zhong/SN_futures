from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS, ManagedProxyHttpClient, _headers
from .managed_proxy_setup_service import HEALTH_ENDPOINT, REQUIRED_TIMESTAMP_FIELDS, validate_managed_proxy_config_source


RELIABILITY_VERSION = "managed_proxy_reliability_v1"
RELIABILITY_REPORT_FILENAME = "managed_proxy_reliability_report.json"
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_CACHE_MAX_AGE_HOURS = 48
DEFAULT_FAILURE_THRESHOLD = 3
REQUIRED_CANARY_FIELDS = tuple(dict.fromkeys((*REQUIRED_TIMESTAMP_FIELDS, *MANAGED_REQUIRED_RESEARCH_FIELDS)))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / RELIABILITY_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _fundamentals_status_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_proxy_status.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _safe_response_size(body: Any, fallback: int = 0) -> int:
    if body is None:
        return fallback
    if isinstance(body, bytes):
        return len(body)
    if isinstance(body, str):
        return len(body.encode("utf-8"))
    try:
        return len(json.dumps(body, ensure_ascii=False, default=str).encode("utf-8"))
    except Exception:
        return fallback


def _fields_from_rows(rows: Any) -> list[str]:
    seen: set[str] = set()
    if not isinstance(rows, list):
        return []
    for row in rows:
        if isinstance(row, Mapping):
            for key, value in row.items():
                if value not in {None, ""}:
                    seen.add(str(key))
    return sorted(seen)


def _provider_fields_from_body(body: Any) -> list[str]:
    if not isinstance(body, Mapping):
        return []
    fields = body.get("fields")
    if isinstance(fields, list):
        return sorted({str(item) for item in fields if str(item or "").strip()})
    rows = body.get("rows") or body.get("data") or body.get("history")
    return _fields_from_rows(rows)


def _previous_failure_count() -> int:
    previous = _read_json(_report_path())
    if isinstance(previous, Mapping):
        try:
            return int(previous.get("consecutive_failure_count") or 0)
        except Exception:
            return 0
    return 0


def compute_endpoint_latency_summary(latency_ms: Iterable[int | float]) -> dict[str, Any]:
    values = [float(item) for item in latency_ms if item is not None]
    if not values:
        return {"count": 0, "min_ms": None, "median_ms": None, "max_ms": None, "p95_ms": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return {
        "count": len(ordered),
        "min_ms": round(ordered[0], 3),
        "median_ms": round(float(statistics.median(ordered)), 3),
        "max_ms": round(ordered[-1], 3),
        "p95_ms": round(ordered[p95_index], 3),
    }


def detect_response_size_violation(response_size_bytes: int, max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES) -> dict[str, Any]:
    size = max(0, int(response_size_bytes or 0))
    limit = max(1, int(max_response_bytes or DEFAULT_MAX_RESPONSE_BYTES))
    return {
        "status": "fail" if size > limit else "pass",
        "violated": size > limit,
        "response_size_bytes": size,
        "max_response_bytes": limit,
    }


def detect_schema_drift_against_baseline(provider_fields: Iterable[str], baseline_fields: Iterable[str] = REQUIRED_CANARY_FIELDS) -> dict[str, Any]:
    provider = sorted({str(item) for item in provider_fields if str(item or "").strip()})
    baseline = sorted({str(item) for item in baseline_fields if str(item or "").strip()})
    missing = sorted(set(baseline) - set(provider))
    return {
        "status": "fail" if missing else "pass",
        "provider_fields_seen": provider,
        "baseline_fields": baseline,
        "missing_fields": missing,
        "schema_mapping_ready": not missing,
    }


def detect_cache_staleness(status_payload: Mapping[str, Any] | None = None, *, max_age_hours: int = DEFAULT_CACHE_MAX_AGE_HOURS) -> dict[str, Any]:
    payload = dict(status_payload) if status_payload is not None else {}
    if status_payload is None:
        current = _read_json(_fundamentals_status_path())
        payload = dict(current) if isinstance(current, Mapping) else {}
    if not payload:
        return {"status": "not_run", "stale": False, "age_hours": None, "blocking_reasons": [], "warning_reasons": []}

    from_cache = bool(payload.get("from_cache")) or str(payload.get("status") or "").lower() == "using_cache"
    if not from_cache:
        return {"status": "pass", "stale": False, "age_hours": 0.0, "blocking_reasons": [], "warning_reasons": []}

    stamp = _parse_datetime(payload.get("last_success_time") or payload.get("generated_at") or payload.get("last_refresh_time"))
    if stamp is None:
        return {
            "status": "fail",
            "stale": True,
            "age_hours": None,
            "blocking_reasons": ["managed_proxy_cache_staleness_unknown"],
            "warning_reasons": [],
        }
    age = datetime.now(stamp.tzinfo) - stamp
    stale = age > timedelta(hours=max_age_hours)
    return {
        "status": "fail" if stale else "pass",
        "stale": bool(stale),
        "age_hours": round(age.total_seconds() / 3600, 3),
        "blocking_reasons": ["managed_proxy_cache_stale"] if stale else [],
        "warning_reasons": [],
    }


def _config_blocking(config: Mapping[str, Any]) -> list[str]:
    if not config.get("enabled"):
        return ["managed_proxy_disabled"]
    if not config.get("base_url_configured"):
        return ["managed_proxy_base_url_missing"]
    if not config.get("token_configured"):
        return ["managed_proxy_token_missing"]
    return []


def _next_action(blocking_reasons: list[str], *, circuit_open: bool = False) -> str:
    if circuit_open or any(reason.startswith("managed_proxy_canary") or reason.startswith("managed_proxy_response") for reason in blocking_reasons):
        return "fix_managed_proxy_reliability"
    if "managed_proxy_invalid_content_type" in blocking_reasons or "managed_proxy_schema_drift" in blocking_reasons:
        return "fix_managed_proxy_reliability"
    if "managed_proxy_cache_stale" in blocking_reasons:
        return "fix_managed_proxy_reliability"
    if "managed_proxy_disabled" in blocking_reasons:
        return "enable_managed_proxy"
    if "managed_proxy_base_url_missing" in blocking_reasons:
        return "configure_managed_proxy_base_url"
    if "managed_proxy_token_missing" in blocking_reasons:
        return "configure_managed_proxy_token"
    return "run_managed_proxy_canary"


def build_reliability_report(
    *,
    canary_status: str,
    blocking_reasons: list[str] | None = None,
    warning_reasons: list[str] | None = None,
    latency_ms: float | int | None = None,
    timeout_count: int = 0,
    error_rate: float = 0.0,
    response_size_bytes: int = 0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    schema_drift_status: str = "not_run",
    cache_staleness_status: str = "not_run",
    circuit_breaker_status: str = "closed",
    consecutive_failure_count: int = 0,
    provider_fields_seen: list[str] | None = None,
    schema_missing_fields: list[str] | None = None,
    cache_age_hours: float | None = None,
    next_allowed_action: str | None = None,
    error_message_zh: str = "",
    write: bool = False,
) -> dict[str, Any]:
    blocking = list(dict.fromkeys(blocking_reasons or []))
    warnings = list(dict.fromkeys(warning_reasons or []))
    status = "pass" if canary_status == "pass" and not blocking and circuit_breaker_status != "open" else "blocked"
    payload = {
        "status": status,
        "reliability_version": RELIABILITY_VERSION,
        "generated_at": _now(),
        "canary_status": canary_status,
        "latency_ms": latency_ms,
        "latency_summary": compute_endpoint_latency_summary([] if latency_ms is None else [latency_ms]),
        "timeout_count": int(timeout_count),
        "error_rate": round(float(error_rate), 4),
        "response_size_bytes": int(response_size_bytes or 0),
        "max_response_bytes": int(max_response_bytes or DEFAULT_MAX_RESPONSE_BYTES),
        "schema_drift_status": schema_drift_status,
        "provider_fields_seen": provider_fields_seen or [],
        "schema_missing_fields": schema_missing_fields or [],
        "cache_staleness_status": cache_staleness_status,
        "cache_age_hours": cache_age_hours,
        "circuit_breaker_status": circuit_breaker_status,
        "consecutive_failure_count": int(consecutive_failure_count),
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
        "next_allowed_action": next_allowed_action or _next_action(blocking, circuit_open=circuit_breaker_status == "open"),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "fake_data_used": False,
        "mock_data_used": False,
        "report_path": str(_report_path()),
        "message_zh": "managed proxy reliability canary passed." if status == "pass" else "managed proxy reliability canary is blocked.",
        "error_message_zh": error_message_zh,
    }
    return _write_report(payload) if write else sanitize_for_json(payload)


def _call_canary(client: Any, *, base_url: str, token: str, timeout_seconds: int) -> dict[str, Any]:
    headers = _headers(token)
    if hasattr(client, "get_canary"):
        return dict(client.get_canary(HEALTH_ENDPOINT, headers))

    start = time.perf_counter()
    payload = client.get_json(HEALTH_ENDPOINT, headers)
    elapsed = (time.perf_counter() - start) * 1000
    return {
        "status_code": 200,
        "content_type": "application/json",
        "body": payload,
        "elapsed_ms": elapsed,
    }


def run_managed_proxy_canary_check(
    *,
    client: Any | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    cache_max_age_hours: int = DEFAULT_CACHE_MAX_AGE_HOURS,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    write: bool = True,
) -> dict[str, Any]:
    config = validate_managed_proxy_config_source()
    token = str(config.get("_token") or "")
    base_url = str(config.get("_base_url") or "")
    timeout_seconds = int(config.get("timeout_seconds") or 20)
    config_blocking = _config_blocking(config)
    if config_blocking:
        return build_reliability_report(
            canary_status="not_run",
            blocking_reasons=config_blocking,
            next_allowed_action=_next_action(config_blocking),
            write=write,
        )

    canary_client = client if client is not None else ManagedProxyHttpClient(base_url, timeout_seconds=timeout_seconds)
    blocking: list[str] = []
    warnings: list[str] = []
    timeout_count = 0
    latency_ms: float | None = None
    response_size = 0
    provider_fields: list[str] = []
    schema_missing: list[str] = []
    schema_status = "not_run"
    canary_status = "pass"
    error_message = ""

    try:
        result = _call_canary(canary_client, base_url=base_url, token=token, timeout_seconds=timeout_seconds)
        status_code = int(result.get("status_code") or 200)
        content_type = str(result.get("content_type") or "application/json")
        body = result.get("body")
        latency_ms = round(float(result.get("elapsed_ms") or 0), 3)
        response_size = int(result.get("response_size_bytes") or _safe_response_size(body))

        if status_code in {401, 403}:
            canary_status = "auth_failed"
            blocking.append("managed_proxy_auth_failed")
        elif status_code >= 500:
            canary_status = "server_error"
            blocking.append("managed_proxy_canary_5xx")
        elif "json" not in content_type.lower():
            canary_status = "invalid_content_type"
            blocking.append("managed_proxy_invalid_content_type")
        else:
            size_check = detect_response_size_violation(response_size, max_response_bytes)
            if size_check["violated"]:
                canary_status = "response_too_large"
                blocking.append("managed_proxy_response_too_large")
            else:
                provider_fields = _provider_fields_from_body(body)
                drift = detect_schema_drift_against_baseline(provider_fields, REQUIRED_CANARY_FIELDS)
                schema_status = str(drift["status"])
                schema_missing = list(drift.get("missing_fields") or [])
                if schema_status == "fail":
                    canary_status = "schema_drift"
                    blocking.append("managed_proxy_schema_drift")
    except TimeoutError as exc:
        canary_status = "timeout"
        timeout_count = 1
        blocking.append("managed_proxy_canary_timeout")
        error_message = sanitize_text(str(exc), extra_secrets=[token, base_url])
    except HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        canary_status = "auth_failed" if code in {401, 403} else "server_error" if code >= 500 else "endpoint_unreachable"
        blocking.append("managed_proxy_auth_failed" if code in {401, 403} else "managed_proxy_canary_5xx" if code >= 500 else "managed_proxy_endpoint_unreachable")
        error_message = sanitize_text(str(exc), extra_secrets=[token, base_url])
    except URLError as exc:
        canary_status = "endpoint_unreachable"
        blocking.append("managed_proxy_endpoint_unreachable")
        error_message = sanitize_text(str(exc), extra_secrets=[token, base_url])
    except Exception as exc:
        canary_status = "endpoint_unreachable"
        blocking.append("managed_proxy_endpoint_unreachable")
        error_message = sanitize_text(str(exc), extra_secrets=[token, base_url])

    cache = detect_cache_staleness(max_age_hours=cache_max_age_hours)
    if cache["status"] == "fail":
        blocking.extend(cache.get("blocking_reasons") or [])
    elif cache["status"] == "warning":
        warnings.extend(cache.get("warning_reasons") or [])

    failed = bool(blocking) or canary_status != "pass"
    consecutive = _previous_failure_count() + 1 if failed else 0
    circuit_status = "open" if consecutive >= int(failure_threshold or DEFAULT_FAILURE_THRESHOLD) else "closed"
    if circuit_status == "open" and "managed_proxy_circuit_breaker_open" not in blocking:
        blocking.append("managed_proxy_circuit_breaker_open")

    return build_reliability_report(
        canary_status=canary_status,
        blocking_reasons=blocking,
        warning_reasons=warnings,
        latency_ms=latency_ms,
        timeout_count=timeout_count,
        error_rate=1.0 if failed else 0.0,
        response_size_bytes=response_size,
        max_response_bytes=max_response_bytes,
        schema_drift_status=schema_status,
        cache_staleness_status=str(cache.get("status") or "not_run"),
        circuit_breaker_status=circuit_status,
        consecutive_failure_count=consecutive,
        provider_fields_seen=provider_fields,
        schema_missing_fields=schema_missing,
        cache_age_hours=cache.get("age_hours") if isinstance(cache, Mapping) else None,
        next_allowed_action=_next_action(blocking, circuit_open=circuit_status == "open"),
        error_message_zh=error_message,
        write=write,
    )


def get_managed_proxy_reliability_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_reliability_report(
        canary_status="not_run",
        blocking_reasons=["managed_proxy_reliability_not_run"],
        next_allowed_action="run_managed_proxy_canary",
        write=False,
    )

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .managed_data_audit_service import validate_managed_point_in_time_rows
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS, ManagedProxyHttpClient
from .managed_proxy_schema_mapper_service import (
    apply_field_mapping_to_sample_rows,
    build_schema_mapping_report,
    load_managed_proxy_field_mapping,
)
from .managed_proxy_setup_service import FUNDAMENTALS_ENDPOINT, REQUIRED_TIMESTAMP_FIELDS, validate_managed_proxy_config_source


SMOKE_VERSION = "managed_proxy_endpoint_smoke_v1"
SMOKE_REPORT_FILENAME = "managed_proxy_endpoint_smoke_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / SMOKE_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _report_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") or payload.get("data") or payload.get("history") if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _field_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    for row in rows:
        seen.update(str(key) for key in row.keys())
    return sorted(seen)


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _present_fields(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[str]:
    present: list[str] = []
    for field in fields:
        if field == "feature_date":
            found = any(_present(row.get("feature_date")) or _present(row.get("trading_date")) for row in rows)
        else:
            found = any(_present(row.get(field)) for row in rows)
        if found:
            present.append(str(field))
    return present


def _missing_fields(present: Sequence[str], required: Sequence[str]) -> list[str]:
    return sorted(set(str(field) for field in required) - set(str(field) for field in present))


def _next_action(blocking_reasons: Sequence[str], status: str) -> str:
    reasons = set(blocking_reasons)
    if status == "pass":
        return "run_managed_proxy_health"
    if "managed_proxy_disabled" in reasons:
        return "enable_managed_proxy"
    if "managed_proxy_base_url_missing" in reasons:
        return "configure_managed_proxy_base_url"
    if "managed_proxy_token_missing" in reasons:
        return "configure_managed_proxy_token"
    if "auth_failed" in reasons:
        return "verify_managed_proxy_token"
    if "endpoint_timeout" in reasons or "endpoint_unreachable" in reasons:
        return "check_managed_proxy_endpoint"
    if "secret_leakage_detected" in reasons:
        return "resolve_managed_proxy_secret_echo"
    if "invalid_response_format" in reasons:
        return "fix_managed_proxy_response_format"
    if "schema_missing_fields" in reasons:
        return "fix_managed_proxy_schema"
    if "pit_timestamp_missing" in reasons or "pit_timestamp_leakage" in reasons:
        return "fix_managed_proxy_pit_timestamps"
    return "run_managed_proxy_endpoint_smoke"


def build_endpoint_smoke_report(
    *,
    status: str,
    auth_status: str,
    endpoint_reachable: bool,
    response_format_status: str = "not_run",
    token_echo_status: str = "not_run",
    schema_field_names_seen: Sequence[str] | None = None,
    required_fields_present: Sequence[str] | None = None,
    timestamp_fields_present: Sequence[str] | None = None,
    sample_row_count: int = 0,
    blocking_reasons: Sequence[str] | None = None,
    warning_reasons: Sequence[str] | None = None,
    latency_ms: float | None = None,
    write: bool = False,
) -> dict[str, Any]:
    blocking = sorted({str(reason) for reason in (blocking_reasons or []) if str(reason or "").strip()})
    payload = {
        "status": status,
        "generated_at": _now(),
        "smoke_version": SMOKE_VERSION,
        "auth_status": auth_status,
        "endpoint_reachable": bool(endpoint_reachable),
        "response_format_status": response_format_status,
        "token_echo_status": token_echo_status,
        "schema_field_names_seen": sorted({str(field) for field in (schema_field_names_seen or []) if str(field or "").strip()}),
        "required_fields_present": sorted({str(field) for field in (required_fields_present or []) if str(field or "").strip()}),
        "timestamp_fields_present": sorted({str(field) for field in (timestamp_fields_present or []) if str(field or "").strip()}),
        "sample_row_count": int(sample_row_count or 0),
        "raw_rows_persisted": False,
        "managed_data_cache_updated": False,
        "feature_store_v12_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "blocking_reasons": blocking,
        "warning_reasons": sorted({str(reason) for reason in (warning_reasons or []) if str(reason or "").strip()}),
        "next_allowed_action": _next_action(blocking, status),
        "latency_ms": latency_ms,
        "report_path": str(_report_path()),
    }
    return _write_report(payload) if write else sanitize_for_json(payload)


def validate_auth_without_persisting_rows(response: Mapping[str, Any]) -> dict[str, Any]:
    status_code = int(response.get("status_code") or 200)
    if status_code in {401, 403}:
        return {"auth_status": "auth_failed", "endpoint_reachable": True, "blocking_reasons": ["auth_failed"]}
    if status_code >= 500:
        return {"auth_status": "endpoint_unreachable", "endpoint_reachable": False, "blocking_reasons": ["endpoint_unreachable"]}
    return {"auth_status": "pass", "endpoint_reachable": True, "blocking_reasons": []}


def validate_schema_from_redacted_sample(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mapping = load_managed_proxy_field_mapping()
    mapped_rows = apply_field_mapping_to_sample_rows([dict(row) for row in rows], mapping)
    mapping_report = build_schema_mapping_report(sample_rows=mapped_rows, field_mapping={}, write=False)
    fields = _field_names(mapped_rows)
    present = _present_fields(mapped_rows, MANAGED_REQUIRED_RESEARCH_FIELDS)
    missing = _missing_fields(present, MANAGED_REQUIRED_RESEARCH_FIELDS)
    blocking: list[str] = []
    if not bool(mapping_report.get("schema_mapping_ready")):
        blocking.extend(str(item) for item in (mapping_report.get("blocking_reasons") or []))
    if missing:
        blocking.append("schema_missing_fields")
    return sanitize_for_json(
        {
            "status": "pass" if not blocking else "blocked",
            "schema_field_names_seen": fields,
            "required_fields_present": present,
            "required_fields_missing": missing,
            "mapping_applied": bool(mapping),
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def validate_pit_timestamps_from_redacted_sample(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    clean_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    present = _present_fields(clean_rows, REQUIRED_TIMESTAMP_FIELDS)
    missing = _missing_fields(present, REQUIRED_TIMESTAMP_FIELDS)
    audit = validate_managed_point_in_time_rows(clean_rows)
    blocking = list(audit.get("blocking_reasons") or [])
    if missing and "pit_timestamp_missing" not in blocking:
        blocking.append("pit_timestamp_missing")
    if "source_timestamp_leakage" in blocking or "asof_date_leakage" in blocking or "feature_date_cutoff_fail" in blocking:
        blocking.append("pit_timestamp_leakage")
    return sanitize_for_json(
        {
            "status": "pass" if not blocking else "blocked",
            "timestamp_fields_present": present,
            "timestamp_fields_missing": missing,
            "point_in_time_join_ready": bool(audit.get("leakage_checks", {}).get("point_in_time_join_ready")) and not missing,
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def detect_token_echo_in_response(response: Any, token: str) -> dict[str, Any]:
    text = json.dumps(response, ensure_ascii=False, default=str) if isinstance(response, (Mapping, list)) else str(response or "")
    echoed = bool(token and token in text)
    return {
        "token_echo_status": "secret_leakage_detected" if echoed else "pass",
        "blocking_reasons": ["secret_leakage_detected"] if echoed else [],
    }


def _call_smoke(client: Any, *, token: str) -> dict[str, Any]:
    headers = _headers(token)
    if hasattr(client, "get_smoke"):
        return dict(client.get_smoke(FUNDAMENTALS_ENDPOINT, headers))
    start = time.perf_counter()
    body = client.get_json(FUNDAMENTALS_ENDPOINT, headers)
    elapsed = round((time.perf_counter() - start) * 1000, 3)
    return {"status_code": 200, "content_type": "application/json", "body": body, "elapsed_ms": elapsed}


def _config_blocking(config: Mapping[str, Any]) -> list[str]:
    if not bool(config.get("enabled")):
        return ["managed_proxy_disabled"]
    blocking: list[str] = []
    if not bool(config.get("base_url_configured")) or not str(config.get("_base_url") or "").strip():
        blocking.append("managed_proxy_base_url_missing")
    if not bool(config.get("token_configured")) or not str(config.get("_token") or "").strip():
        blocking.append("managed_proxy_token_missing")
    return blocking


def run_endpoint_smoke_test(
    *,
    config: Mapping[str, Any] | None = None,
    client: Any | None = None,
    write: bool = True,
) -> dict[str, Any]:
    config_payload = dict(config if isinstance(config, Mapping) else validate_managed_proxy_config_source())
    config_blocking = _config_blocking(config_payload)
    if config_blocking:
        return build_endpoint_smoke_report(
            status="blocked",
            auth_status="not_run",
            endpoint_reachable=False,
            blocking_reasons=config_blocking,
            write=write,
        )

    token = str(config_payload.get("_token") or "")
    base_url = str(config_payload.get("_base_url") or "")
    timeout_seconds = int(config_payload.get("timeout_seconds") or 20)
    smoke_client = client if client is not None else ManagedProxyHttpClient(base_url, timeout_seconds=timeout_seconds)
    blocking: list[str] = []
    warnings: list[str] = []
    latency_ms: float | None = None
    rows: list[dict[str, Any]] = []
    response_format_status = "not_run"
    token_echo_status = "not_run"
    auth_status = "not_run"
    endpoint_reachable = False

    try:
        result = _call_smoke(smoke_client, token=token)
        latency_value = result.get("elapsed_ms")
        latency_ms = round(float(latency_value), 3) if latency_value is not None else None
        auth = validate_auth_without_persisting_rows(result)
        auth_status = str(auth["auth_status"])
        endpoint_reachable = bool(auth["endpoint_reachable"])
        blocking.extend(str(item) for item in (auth.get("blocking_reasons") or []))
        content_type = str(result.get("content_type") or "application/json")
        body = result.get("body")
        if auth_status == "pass":
            if "json" not in content_type.lower() or not isinstance(body, Mapping):
                response_format_status = "invalid_response_format"
                blocking.append("invalid_response_format")
            else:
                response_format_status = "pass"
                echo = detect_token_echo_in_response(body, token)
                token_echo_status = str(echo["token_echo_status"])
                blocking.extend(str(item) for item in (echo.get("blocking_reasons") or []))
                rows = _rows_from_payload(body)
        else:
            response_format_status = "not_run"
            token_echo_status = "not_run"
    except TimeoutError as exc:
        auth_status = "not_run"
        endpoint_reachable = False
        response_format_status = "not_run"
        token_echo_status = "not_run"
        blocking.append("endpoint_timeout")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, base_url]))
    except HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        auth_status = "auth_failed" if code in {401, 403} else "endpoint_unreachable"
        endpoint_reachable = code in {401, 403}
        blocking.append("auth_failed" if code in {401, 403} else "endpoint_unreachable")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, base_url]))
    except (URLError, json.JSONDecodeError) as exc:
        auth_status = "not_run"
        endpoint_reachable = False
        reason = "invalid_response_format" if isinstance(exc, json.JSONDecodeError) else "endpoint_unreachable"
        response_format_status = reason
        token_echo_status = "not_run"
        blocking.append(reason)
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, base_url]))
    except Exception as exc:
        auth_status = "not_run"
        endpoint_reachable = False
        response_format_status = "not_run"
        token_echo_status = "not_run"
        blocking.append("endpoint_unreachable")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, base_url]))

    schema = validate_schema_from_redacted_sample(rows) if rows else {"status": "blocked", "schema_field_names_seen": [], "required_fields_present": [], "blocking_reasons": ["schema_missing_fields"]}
    pit = validate_pit_timestamps_from_redacted_sample(rows) if rows else {"status": "blocked", "timestamp_fields_present": [], "blocking_reasons": ["pit_timestamp_missing"]}
    if rows and schema["status"] != "pass":
        blocking.extend(str(item) for item in (schema.get("blocking_reasons") or []))
    if rows and pit["status"] != "pass":
        blocking.extend(str(item) for item in (pit.get("blocking_reasons") or []))

    blocking = sorted({reason for reason in blocking if reason})
    status = "pass" if auth_status == "pass" and response_format_status == "pass" and token_echo_status == "pass" and rows and not blocking else "blocked"
    return build_endpoint_smoke_report(
        status=status,
        auth_status=auth_status,
        endpoint_reachable=endpoint_reachable,
        response_format_status=response_format_status,
        token_echo_status=token_echo_status,
        schema_field_names_seen=schema.get("schema_field_names_seen") or [],
        required_fields_present=schema.get("required_fields_present") or [],
        timestamp_fields_present=pit.get("timestamp_fields_present") or [],
        sample_row_count=len(rows),
        blocking_reasons=blocking,
        warning_reasons=warnings,
        latency_ms=latency_ms,
        write=write,
    )


def get_latest_endpoint_smoke_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_endpoint_smoke_report(
        status="blocked",
        auth_status="not_run",
        endpoint_reachable=False,
        response_format_status="not_run",
        token_echo_status="not_run",
        blocking_reasons=["endpoint_smoke_report_missing"],
        write=False,
    )

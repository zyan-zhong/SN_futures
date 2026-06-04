from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value, sanitize_text
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS, ManagedProxyHttpClient
from .managed_proxy_endpoint_smoke_service import get_latest_endpoint_smoke_report
from .managed_proxy_setup_service import FUNDAMENTALS_ENDPOINT, REQUIRED_TIMESTAMP_FIELDS, validate_managed_proxy_config_source


SNAPSHOT_VERSION = "managed_proxy_quarantine_snapshot_v1"
SNAPSHOT_REPORT_FILENAME = "managed_proxy_quarantine_snapshot_report.json"
DEFAULT_ROW_BUDGET = 5
DEFAULT_REQUESTED_ROWS = 1
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024
SENSITIVE_KEY_HINTS = ("authorization", "token", "secret", "password", "api_key", "apikey", "header", "endpoint", "base_url")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / SNAPSHOT_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _quarantine_root() -> Path:
    return get_user_output_dir() / "managed_proxy_quarantine"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    _write_json(_report_path(), safe)
    return safe


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") or payload.get("data") or payload.get("history") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _field_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(str(key) for key in row.keys())
    return sorted(fields)


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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _snapshot_endpoint(requested_rows: int) -> str:
    separator = "&" if "?" in FUNDAMENTALS_ENDPOINT else "?"
    return f"{FUNDAMENTALS_ENDPOINT}{separator}limit={int(requested_rows)}"


def _base_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "generated_at": _now(),
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_pulled": False,
        "snapshot_row_count": 0,
        "row_budget": DEFAULT_ROW_BUDGET,
        "quarantine_path": "",
        "preview_path": "",
        "redacted_preview": {},
        "schema_field_names_seen": [],
        "timestamp_fields_seen": [],
        "required_fields_seen": [],
        "missing_required_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
        "missing_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS),
        "secret_safety_status": "not_run",
        "raw_rows_persisted": False,
        "managed_cache_updated": False,
        "production_eligible": False,
        "feature_store_v12_allowed": False,
        "blocking_reasons": [],
        "warning_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }


def _blocked_payload(reason: str | Sequence[str], *, row_budget: int = DEFAULT_ROW_BUDGET, write: bool = False) -> dict[str, Any]:
    reasons = [reason] if isinstance(reason, str) else [str(item) for item in reason]
    payload = _base_payload()
    payload["row_budget"] = int(row_budget)
    payload["blocking_reasons"] = sorted({item for item in reasons if item})
    payload["secret_safety_status"] = "pass" if "secret_leakage_detected" not in payload["blocking_reasons"] else "failed"
    return _write_report(payload) if write else sanitize_for_json(payload)


def _config_ready(config: Mapping[str, Any]) -> bool:
    return (
        bool(config.get("enabled"))
        and bool(config.get("configured", True))
        and bool(config.get("base_url_configured"))
        and bool(config.get("token_configured"))
        and bool(str(config.get("_base_url") or "").strip())
        and bool(str(config.get("_token") or "").strip())
    )


def _smoke_ready(smoke: Mapping[str, Any]) -> bool:
    return (
        str(smoke.get("status") or "").lower() in {"pass", "ready", "success"}
        and str(smoke.get("auth_status") or "").lower() == "pass"
        and bool(smoke.get("endpoint_reachable"))
        and str(smoke.get("response_format_status") or "").lower() == "pass"
        and str(smoke.get("token_echo_status") or "").lower() == "pass"
    )


def validate_quarantine_snapshot_preconditions(
    *,
    smoke_report: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    requested_rows: int = DEFAULT_REQUESTED_ROWS,
    row_budget: int = DEFAULT_ROW_BUDGET,
) -> dict[str, Any]:
    blocking: list[str] = []
    smoke = dict(smoke_report) if isinstance(smoke_report, Mapping) else get_latest_endpoint_smoke_report()
    config_payload = dict(config if isinstance(config, Mapping) else validate_managed_proxy_config_source())

    if int(row_budget or 0) <= 0:
        blocking.append("row_budget_missing")
    if int(requested_rows or 0) <= 0:
        blocking.append("requested_rows_invalid")
    if int(requested_rows or 0) > int(row_budget or 0):
        blocking.append("requested_rows_exceed_budget")
    if not _config_ready(config_payload):
        if not bool(config_payload.get("enabled")):
            blocking.append("managed_proxy_disabled")
        if not bool(config_payload.get("base_url_configured")) or not str(config_payload.get("_base_url") or "").strip():
            blocking.append("managed_proxy_base_url_missing")
        if not bool(config_payload.get("token_configured")) or not str(config_payload.get("_token") or "").strip():
            blocking.append("managed_proxy_token_missing")
    if not _smoke_ready(smoke):
        blocking.extend(str(item) for item in (smoke.get("blocking_reasons") or []) if item)
        smoke_status = str(smoke.get("status") or "missing")
        if smoke_status in {"missing", ""} or "endpoint_smoke_report_missing" in (smoke.get("blocking_reasons") or []):
            blocking.append("endpoint_smoke_report_missing")
        else:
            blocking.append("endpoint_smoke_not_passed")

    blocking = sorted({reason for reason in blocking if reason})
    return sanitize_for_json(
        {
            "status": "pass" if not blocking else "blocked",
            "requested_rows": int(requested_rows or 0),
            "row_budget": int(row_budget or 0),
            "endpoint_smoke_status": smoke.get("status", "missing"),
            "auth_status": smoke.get("auth_status", "not_run"),
            "token_echo_status": smoke.get("token_echo_status", "not_run"),
            "endpoint_reachable": bool(smoke.get("endpoint_reachable")),
            "blocking_reasons": blocking,
            "snapshot_allowed": not blocking,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def validate_snapshot_secret_safety(payload: Any, *, token: str = "", endpoint: str = "") -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, default=str) if isinstance(payload, (Mapping, list)) else str(payload or "")
    blocking: list[str] = []
    if token and token in text:
        blocking.append("secret_leakage_detected")
    if endpoint and endpoint in text:
        blocking.append("endpoint_secret_leakage_detected")
    if "Authorization" in text or "Bearer " in text:
        blocking.append("authorization_header_detected")

    def _secret_key_or_value(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                lower = str(key).lower()
                if any(hint in lower for hint in SENSITIVE_KEY_HINTS):
                    return True
                if _secret_key_or_value(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(_secret_key_or_value(item) for item in value)
        if isinstance(value, str):
            return contains_secret_like_value(value)
        return False

    if _secret_key_or_value(payload):
        blocking.append("secret_like_value_detected")
    blocking = sorted(set(blocking))
    return sanitize_for_json({"secret_safety_status": "failed" if blocking else "pass", "blocking_reasons": blocking})


def validate_snapshot_size_budget(
    rows: Sequence[Mapping[str, Any]],
    *,
    requested_rows: int,
    row_budget: int,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    blocking: list[str] = []
    if int(requested_rows or 0) > int(row_budget or 0):
        blocking.append("requested_rows_exceed_budget")
    if len(rows) > int(row_budget or 0):
        blocking.append("response_rows_exceed_budget")
    response_bytes = len(json.dumps(list(rows), ensure_ascii=False, default=str).encode("utf-8"))
    if response_bytes > int(max_response_bytes or 0):
        blocking.append("response_too_large")
    return sanitize_for_json(
        {
            "status": "pass" if not blocking else "blocked",
            "row_count": len(rows),
            "row_budget": int(row_budget or 0),
            "response_size_bytes": response_bytes,
            "max_response_bytes": int(max_response_bytes or 0),
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def _example_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "timestamp" if any(mark in value for mark in ("T", "-", ":")) else "string"
    return type(value).__name__


def redact_snapshot_preview(rows: Sequence[Mapping[str, Any]], *, preview_rows: int = 2) -> dict[str, Any]:
    capped_rows = [dict(row) for row in rows[: max(0, int(preview_rows))]]
    fields = _field_names(capped_rows)
    field_preview: list[dict[str, Any]] = []
    for field in fields:
        values = [row.get(field) for row in capped_rows]
        non_null = sum(1 for value in values if _present(value))
        first = next((value for value in values if _present(value)), None)
        field_preview.append(
            {
                "field": field,
                "type": _example_type(first),
                "non_null_count": non_null,
                "null_count": max(len(capped_rows) - non_null, 0),
                "masked_example": "<present>" if first is not None else "<missing>",
            }
        )
    timestamp_fields = _present_fields(capped_rows, REQUIRED_TIMESTAMP_FIELDS)
    return sanitize_for_json(
        {
            "preview_status": "ready" if capped_rows else "empty",
            "row_count_previewed": len(capped_rows),
            "field_count": len(fields),
            "fields": field_preview,
            "timestamp_coverage": {
                "required": list(REQUIRED_TIMESTAMP_FIELDS),
                "present": timestamp_fields,
                "missing": _missing_fields(timestamp_fields, REQUIRED_TIMESTAMP_FIELDS),
            },
            "full_rows_included": False,
        }
    )


def build_quarantine_snapshot_report(
    *,
    status: str,
    snapshot_pulled: bool,
    snapshot_row_count: int = 0,
    row_budget: int = DEFAULT_ROW_BUDGET,
    quarantine_path: str = "",
    preview_path: str = "",
    redacted_preview: Mapping[str, Any] | None = None,
    schema_field_names_seen: Sequence[str] | None = None,
    timestamp_fields_seen: Sequence[str] | None = None,
    required_fields_seen: Sequence[str] | None = None,
    secret_safety_status: str = "pass",
    blocking_reasons: Sequence[str] | None = None,
    warning_reasons: Sequence[str] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    fields = sorted({str(field) for field in (schema_field_names_seen or []) if str(field or "").strip()})
    timestamp_seen = sorted({str(field) for field in (timestamp_fields_seen or []) if str(field or "").strip()})
    required_seen = sorted({str(field) for field in (required_fields_seen or []) if str(field or "").strip()})
    payload = _base_payload()
    payload.update(
        {
            "status": status,
            "snapshot_pulled": bool(snapshot_pulled),
            "snapshot_row_count": int(snapshot_row_count or 0),
            "row_budget": int(row_budget or 0),
            "quarantine_path": quarantine_path,
            "preview_path": preview_path,
            "redacted_preview": sanitize_for_json(dict(redacted_preview or {})),
            "schema_field_names_seen": fields,
            "timestamp_fields_seen": timestamp_seen,
            "required_fields_seen": required_seen,
            "missing_required_fields": _missing_fields(required_seen, MANAGED_REQUIRED_RESEARCH_FIELDS),
            "missing_timestamp_fields": _missing_fields(timestamp_seen, REQUIRED_TIMESTAMP_FIELDS),
            "secret_safety_status": secret_safety_status,
            "blocking_reasons": sorted({str(reason) for reason in (blocking_reasons or []) if str(reason or "").strip()}),
            "warning_reasons": sorted({str(reason) for reason in (warning_reasons or []) if str(reason or "").strip()}),
        }
    )
    return _write_report(payload) if write else sanitize_for_json(payload)


def _call_snapshot(client: Any, *, token: str, requested_rows: int) -> dict[str, Any]:
    path = _snapshot_endpoint(requested_rows)
    headers = _headers(token)
    if hasattr(client, "get_quarantine_snapshot"):
        return dict(client.get_quarantine_snapshot(path, headers, requested_rows))
    body = client.get_json(path, headers)
    return {"status_code": 200, "content_type": "application/json", "body": body}


def pull_managed_proxy_quarantine_snapshot(
    *,
    config: Mapping[str, Any] | None = None,
    client: Any | None = None,
    requested_rows: int = DEFAULT_REQUESTED_ROWS,
    row_budget: int = DEFAULT_ROW_BUDGET,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    config_payload = dict(config if isinstance(config, Mapping) else validate_managed_proxy_config_source())
    preconditions = validate_quarantine_snapshot_preconditions(config=config_payload, requested_rows=requested_rows, row_budget=row_budget)
    if preconditions["status"] != "pass":
        return _blocked_payload(preconditions["blocking_reasons"], row_budget=row_budget, write=True)

    token = str(config_payload.get("_token") or "")
    endpoint = str(config_payload.get("_base_url") or "")
    timeout_seconds = int(config_payload.get("timeout_seconds") or 20)
    snapshot_client = client if client is not None else ManagedProxyHttpClient(endpoint, timeout_seconds=timeout_seconds)
    blocking: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        result = _call_snapshot(snapshot_client, token=token, requested_rows=requested_rows)
        status_code = int(result.get("status_code") or 200)
        content_type = str(result.get("content_type") or "application/json")
        if status_code in {401, 403}:
            blocking.append("auth_failed")
        elif status_code >= 500:
            blocking.append("endpoint_unreachable")
        elif "json" not in content_type.lower() or not isinstance(result.get("body"), Mapping):
            blocking.append("invalid_response_format")
        else:
            body = result.get("body")
            secret_safety = validate_snapshot_secret_safety(body, token=token, endpoint=endpoint)
            if secret_safety["secret_safety_status"] != "pass":
                blocking.extend(str(item) for item in (secret_safety.get("blocking_reasons") or []))
            rows = _rows_from_payload(body)
            size = validate_snapshot_size_budget(rows, requested_rows=requested_rows, row_budget=row_budget, max_response_bytes=max_response_bytes)
            if size["status"] != "pass":
                blocking.extend(str(item) for item in (size.get("blocking_reasons") or []))
    except TimeoutError as exc:
        blocking.append("endpoint_timeout")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, endpoint]))
    except HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        blocking.append("auth_failed" if code in {401, 403} else "endpoint_unreachable")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, endpoint]))
    except (URLError, json.JSONDecodeError) as exc:
        blocking.append("invalid_response_format" if isinstance(exc, json.JSONDecodeError) else "endpoint_unreachable")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, endpoint]))
    except Exception as exc:
        blocking.append("endpoint_unreachable")
        warnings.append(sanitize_text(str(exc), extra_secrets=[token, endpoint]))

    blocking = sorted({reason for reason in blocking if reason})
    if blocking or not rows:
        if not rows and not blocking:
            blocking.append("snapshot_rows_missing")
        return build_quarantine_snapshot_report(
            status="blocked",
            snapshot_pulled=False,
            row_budget=row_budget,
            secret_safety_status="failed" if any("secret" in reason or "authorization" in reason for reason in blocking) else "pass",
            blocking_reasons=blocking,
            warning_reasons=warnings,
            write=True,
        )

    root = _quarantine_root()
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    snapshot_path = root / f"managed_proxy_quarantine_snapshot_{stamp}.json"
    preview_path = root / f"managed_proxy_quarantine_preview_{stamp}.json"
    preview = redact_snapshot_preview(rows)
    _write_json(
        snapshot_path,
        {
            "snapshot_version": SNAPSHOT_VERSION,
            "generated_at": _now(),
            "quarantine_only": True,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "rows": rows,
        },
    )
    _write_json(preview_path, preview)
    fields = _field_names(rows)
    timestamp_seen = _present_fields(rows, REQUIRED_TIMESTAMP_FIELDS)
    required_seen = _present_fields(rows, MANAGED_REQUIRED_RESEARCH_FIELDS)
    return build_quarantine_snapshot_report(
        status="ready",
        snapshot_pulled=True,
        snapshot_row_count=len(rows),
        row_budget=row_budget,
        quarantine_path=str(snapshot_path),
        preview_path=str(preview_path),
        redacted_preview=preview,
        schema_field_names_seen=fields,
        timestamp_fields_seen=timestamp_seen,
        required_fields_seen=required_seen,
        secret_safety_status="pass",
        blocking_reasons=[],
        warning_reasons=warnings,
        write=True,
    )


def get_latest_quarantine_snapshot_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    report = _base_payload()
    report["blocking_reasons"] = ["quarantine_snapshot_report_missing"]
    return sanitize_for_json(report)

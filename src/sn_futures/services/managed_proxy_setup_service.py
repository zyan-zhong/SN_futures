from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir
from ..user_data import secrets_path
from ..utils.secret_sanitizer import sanitize_text
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS, ManagedProxyHttpClient
from .managed_proxy_schema_mapper_service import (
    apply_field_mapping_to_sample_rows,
    build_schema_mapping_report,
    load_managed_proxy_field_mapping,
)


SETUP_VERSION = "managed_proxy_setup_v1"
SETUP_REPORT_FILENAME = "managed_proxy_setup_report.json"
REQUIRED_TIMESTAMP_FIELDS = (
    "source_timestamp",
    "asof_date",
    "ingest_timestamp",
    "feature_date",
    "prediction_cutoff_date",
)
REQUIRED_FUNDAMENTAL_FIELDS = tuple(MANAGED_REQUIRED_RESEARCH_FIELDS)
HEALTH_ENDPOINT = "/api/sn/status"
FUNDAMENTALS_ENDPOINT = "/api/sn/fundamentals/history"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / SETUP_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _report_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            sample = text[:10] if fmt == "%Y-%m-%d" else text[:8]
            return datetime.strptime(sample, fmt)
        except Exception:
            continue
    return None


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if not text or lower in {"masked", "[masked]", "redacted", "[redacted]", "configured", "your_token_here"}:
        return ""
    if set(text) <= {"*"}:
        return ""
    return text


def _local_config() -> dict[str, Any]:
    project_local = Path.cwd() / "config" / "managed_proxy.local.json"
    user_local = secrets_path().parent / "managed_proxy.local.json"
    data: dict[str, Any] = {}
    for path in (project_local, user_local):
        payload = _read_json(path)
        if payload:
            data.update(payload)
    return data


def _config_value(env_names: tuple[str, ...], json_names: tuple[str, ...]) -> tuple[str, str]:
    for name in env_names:
        value = _clean(os.environ.get(name, ""))
        if value:
            return value, "env"
    payload = _local_config()
    for name in json_names:
        value = _clean(payload.get(name, ""))
        if value:
            return value, "local_config"
    return "", "none"


def _enabled_from(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def validate_managed_proxy_config_source() -> dict[str, Any]:
    base_url, base_url_source = _config_value(
        ("SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL"),
        ("base_url", "endpoint", "SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL"),
    )
    token, token_source = _config_value(
        ("SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN"),
        ("token", "SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN"),
    )
    timeout_text, timeout_source = _config_value(
        ("SN_MANAGED_PROXY_TIMEOUT_SECONDS", "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS"),
        ("timeout_seconds", "SN_MANAGED_PROXY_TIMEOUT_SECONDS", "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS"),
    )
    enabled_text, enabled_source = _config_value(
        ("SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED"),
        ("enabled", "SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED"),
    )
    enabled = _enabled_from(enabled_text) or bool(base_url or token)
    try:
        timeout_seconds = int(timeout_text) if timeout_text else 20
    except ValueError:
        timeout_seconds = -1
    return {
        "enabled": enabled,
        "configured": bool(base_url and token),
        "base_url_configured": bool(base_url),
        "token_configured": bool(token),
        "token_masked": mask_secret(token) if token else "",
        "token_source": token_source,
        "base_url_source": base_url_source,
        "timeout_seconds": timeout_seconds,
        "timeout_source": timeout_source,
        "_base_url": base_url,
        "_token": token,
        "_enabled_source": enabled_source,
    }


def build_managed_proxy_endpoint_contract(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = config or validate_managed_proxy_config_source()
    return {
        "auth_method": "bearer_token",
        "base_url_configured": bool(config.get("base_url_configured")),
        "health_endpoint": HEALTH_ENDPOINT,
        "fundamentals_endpoint": FUNDAMENTALS_ENDPOINT,
        "timeout_seconds": int(config.get("timeout_seconds") or 20),
        "max_response_bytes": 2_000_000,
        "content_type": "application/json",
        "required_headers": ["bearer_auth_header_configured", "Accept: application/json"],
        "no_secret_echo_allowed": True,
        "https_required_for_non_local": True,
    }


def validate_managed_proxy_endpoint_contract(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = config or validate_managed_proxy_config_source()
    base_url = str(config.get("_base_url") or "")
    timeout_seconds = int(config.get("timeout_seconds") or 0)
    blocking: list[str] = []
    warnings: list[str] = []
    if not config.get("enabled"):
        contract = build_managed_proxy_endpoint_contract(config)
        return {**contract, "status": "not_run", "blocking_reasons": [], "warning_reasons": []}
    if not base_url:
        blocking.append("managed_proxy_base_url_missing")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        blocking.append("managed_proxy_timeout_invalid")
    if base_url:
        lower = base_url.lower()
        is_local = any(item in lower for item in ("localhost", "127.0.0.1", "::1"))
        if not (lower.startswith("https://") or (is_local and lower.startswith("http://"))):
            blocking.append("managed_proxy_https_required")
    status = "pass" if not blocking else "blocked"
    return {
        **build_managed_proxy_endpoint_contract(config),
        "status": status,
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
    }


def get_managed_proxy_setup_status() -> dict[str, Any]:
    config = validate_managed_proxy_config_source()
    endpoint = validate_managed_proxy_endpoint_contract(config)
    blocking: list[str] = []
    if not config["enabled"]:
        blocking.append("managed_proxy_disabled")
    elif not config["base_url_configured"]:
        blocking.append("managed_proxy_base_url_missing")
    elif not config["token_configured"]:
        blocking.append("managed_proxy_token_missing")
    blocking.extend(endpoint["blocking_reasons"])
    status = "blocked" if blocking else "configured"
    return _build_report(config=config, endpoint_contract=endpoint, blocking_reasons=blocking, status=status, write=False)


def _next_allowed_action(blocking_reasons: list[str]) -> str:
    if "managed_proxy_disabled" in blocking_reasons:
        return "enable_managed_proxy"
    if "managed_proxy_base_url_missing" in blocking_reasons:
        return "configure_managed_proxy_base_url"
    if "managed_proxy_token_missing" in blocking_reasons:
        return "configure_managed_proxy_token"
    if "managed_proxy_auth_failed" in blocking_reasons or "auth_failed" in blocking_reasons:
        return "verify_managed_proxy_token"
    if "managed_proxy_schema_mapping_failed" in blocking_reasons:
        return "fix_managed_proxy_schema_mapping"
    if "managed_proxy_schema_missing_fields" in blocking_reasons:
        return "fix_managed_proxy_schema"
    if "managed_proxy_pit_timestamp_missing" in blocking_reasons or "managed_proxy_pit_leakage_failed" in blocking_reasons:
        return "fix_managed_proxy_pit_timestamps"
    if blocking_reasons:
        return "fix_managed_proxy_endpoint_contract"
    return "run_managed_proxy_health"


def _build_report(
    *,
    config: Mapping[str, Any],
    endpoint_contract: Mapping[str, Any],
    blocking_reasons: list[str],
    status: str,
    schema_contract_status: str = "not_run",
    pit_timestamp_contract_status: str = "not_run",
    missing_fields: list[str] | None = None,
    missing_timestamp_fields: list[str] | None = None,
    dry_run_row_count: int = 0,
    warning_reasons: list[str] | None = None,
    mapping_applied: bool = False,
    schema_mapping_status: str = "not_run",
    schema_mapping_ready: bool = False,
    schema_mapping_report_path: str = "",
    schema_mapping_blocking_reasons: list[str] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    ready = status == "ready"
    payload = {
        "status": status,
        "setup_version": SETUP_VERSION,
        "generated_at": _now(),
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("configured")),
        "base_url_configured": bool(config.get("base_url_configured")),
        "token_configured": bool(config.get("token_configured")),
        "token_masked": str(config.get("token_masked") or ""),
        "token_source": str(config.get("token_source") or "none"),
        "base_url_source": str(config.get("base_url_source") or "none"),
        "timeout_seconds": int(config.get("timeout_seconds") or 20),
        "endpoint_contract": dict(endpoint_contract),
        "endpoint_contract_status": endpoint_contract.get("status", "blocked"),
        "schema_contract_status": schema_contract_status,
        "schema_mapping_status": schema_mapping_status,
        "schema_mapping_ready": bool(schema_mapping_ready),
        "schema_mapping_report_path": schema_mapping_report_path,
        "schema_mapping_blocking_reasons": schema_mapping_blocking_reasons or [],
        "mapping_applied": bool(mapping_applied),
        "pit_timestamp_contract_status": pit_timestamp_contract_status,
        "required_fields": list(REQUIRED_FUNDAMENTAL_FIELDS),
        "missing_fields": list(REQUIRED_FUNDAMENTAL_FIELDS) if missing_fields is None else missing_fields,
        "required_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS),
        "missing_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS) if missing_timestamp_fields is None else missing_timestamp_fields,
        "dry_run_row_count": int(dry_run_row_count),
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "warning_reasons": warning_reasons or [],
        "next_allowed_action": _next_allowed_action(blocking_reasons),
        "managed_proxy_health_allowed": ready,
        "pit_audit_allowed": ready,
        "feature_store_v12_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "no_fake_data": True,
        "fake_data_used": False,
        "mock_data_used": False,
        "report_path": str(_report_path()),
    }
    if write:
        return _write_report(payload)
    return sanitize_for_json(payload)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _client(base_url: str, timeout_seconds: int, client: Any | None = None) -> Any:
    return client if client is not None else ManagedProxyHttpClient(base_url, timeout_seconds=timeout_seconds)


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _missing_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return list(REQUIRED_FUNDAMENTAL_FIELDS)
    missing: list[str] = []
    for field in REQUIRED_FUNDAMENTAL_FIELDS:
        if not any(row.get(field) not in {None, ""} for row in rows):
            missing.append(field)
    return missing


def _missing_timestamp_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return list(REQUIRED_TIMESTAMP_FIELDS)
    missing: list[str] = []
    for field in REQUIRED_TIMESTAMP_FIELDS:
        if field == "feature_date":
            field_missing = any(not str(row.get("feature_date") or row.get("trading_date") or "").strip() for row in rows)
        else:
            field_missing = any(not str(row.get(field) or "").strip() for row in rows)
        if field_missing:
            missing.append(field)
    return missing


def _pit_leakage_failed(rows: list[Mapping[str, Any]]) -> bool:
    for row in rows:
        feature_date = _parse_date(row.get("feature_date") or row.get("trading_date"))
        cutoff = _parse_date(row.get("prediction_cutoff_date"))
        source = _parse_date(row.get("source_timestamp"))
        asof = _parse_date(row.get("asof_date"))
        if feature_date and cutoff and feature_date > cutoff:
            return True
        if source and cutoff and source > cutoff:
            return True
        if asof and ((feature_date and asof > feature_date) or (cutoff and asof > cutoff)):
            return True
    return False


def _blocked_dry_run_report(
    *,
    config: Mapping[str, Any],
    endpoint_contract: Mapping[str, Any],
    reason: str,
    message: str = "",
    schema_contract_status: str = "not_run",
    pit_timestamp_contract_status: str = "not_run",
    missing_fields: list[str] | None = None,
    missing_timestamp_fields: list[str] | None = None,
    mapping_applied: bool = False,
    schema_mapping_status: str = "not_run",
    schema_mapping_ready: bool = False,
    schema_mapping_report_path: str = "",
    schema_mapping_blocking_reasons: list[str] | None = None,
) -> dict[str, Any]:
    warning = [sanitize_text(message, extra_secrets=[str(config.get("_token") or ""), str(config.get("_base_url") or "")])] if message else []
    return _build_report(
        config=config,
        endpoint_contract=endpoint_contract,
        blocking_reasons=[reason],
        status="blocked",
        schema_contract_status=schema_contract_status,
        pit_timestamp_contract_status=pit_timestamp_contract_status,
        missing_fields=missing_fields,
        missing_timestamp_fields=missing_timestamp_fields,
        warning_reasons=warning,
        mapping_applied=mapping_applied,
        schema_mapping_status=schema_mapping_status,
        schema_mapping_ready=schema_mapping_ready,
        schema_mapping_report_path=schema_mapping_report_path,
        schema_mapping_blocking_reasons=schema_mapping_blocking_reasons,
    )


def build_managed_proxy_setup_report() -> dict[str, Any]:
    config = validate_managed_proxy_config_source()
    endpoint = validate_managed_proxy_endpoint_contract(config)
    blocking: list[str] = []
    if not config["enabled"]:
        blocking.append("managed_proxy_disabled")
    elif not config["base_url_configured"]:
        blocking.append("managed_proxy_base_url_missing")
    elif not config["token_configured"]:
        blocking.append("managed_proxy_token_missing")
    blocking.extend(endpoint["blocking_reasons"])
    return _build_report(config=config, endpoint_contract=endpoint, blocking_reasons=blocking, status="blocked" if blocking else "configured")


def refresh_managed_proxy_setup() -> dict[str, Any]:
    return build_managed_proxy_setup_report()


def run_managed_proxy_schema_dry_run(*, client: Any | None = None) -> dict[str, Any]:
    config = validate_managed_proxy_config_source()
    endpoint = validate_managed_proxy_endpoint_contract(config)
    setup = build_managed_proxy_setup_report()
    if setup.get("blocking_reasons"):
        return setup

    token = str(config.get("_token") or "")
    base_url = str(config.get("_base_url") or "")
    timeout_seconds = int(config.get("timeout_seconds") or 20)
    try:
        payload = _client(base_url, timeout_seconds, client=client).get_json(FUNDAMENTALS_ENDPOINT, _headers(token))
    except HTTPError as exc:
        status = "auth_failed" if int(getattr(exc, "code", 0) or 0) in {401, 403} else "endpoint_unreachable"
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason=status, message=str(exc))
    except TimeoutError as exc:
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="endpoint_timeout", message=str(exc))
    except URLError as exc:
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="endpoint_unreachable", message=str(exc))
    except json.JSONDecodeError as exc:
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="invalid_response_format", message=str(exc))
    except Exception as exc:
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="endpoint_unreachable", message=str(exc))

    raw_payload_text = json.dumps(payload, ensure_ascii=False, default=str) if isinstance(payload, Mapping) else str(payload)
    if token and token in raw_payload_text:
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="secret_leakage_detected")
    if not isinstance(payload, Mapping):
        return _blocked_dry_run_report(config=config, endpoint_contract=endpoint, reason="invalid_response_format")

    rows = _rows_from_payload(payload)
    field_mapping = load_managed_proxy_field_mapping()
    mapping_report = build_schema_mapping_report(sample_rows=rows, field_mapping=field_mapping, write=True)
    rows = apply_field_mapping_to_sample_rows(rows, field_mapping)
    mapping_applied = bool(mapping_report.get("mapping_applied"))
    schema_mapping_status = str(mapping_report.get("status") or "blocked")
    schema_mapping_ready = bool(mapping_report.get("schema_mapping_ready"))
    schema_mapping_report_path = str(mapping_report.get("report_path") or "")
    schema_mapping_blocking = list(mapping_report.get("blocking_reasons") or [])
    missing_fields = _missing_fields(rows)
    missing_ts = _missing_timestamp_fields(rows)
    blocking: list[str] = []
    schema_status = "pass"
    pit_status = "pass"
    if not schema_mapping_ready:
        blocking.append("managed_proxy_schema_mapping_failed")
        schema_status = "blocked"
    if missing_fields:
        blocking.append("managed_proxy_schema_missing_fields")
        schema_status = "blocked"
    if missing_ts:
        blocking.append("managed_proxy_pit_timestamp_missing")
        pit_status = "blocked"
    if _pit_leakage_failed(rows):
        blocking.append("managed_proxy_pit_leakage_failed")
        pit_status = "blocked"
    status = "ready" if not blocking else "blocked"
    return _build_report(
        config=config,
        endpoint_contract=endpoint,
        blocking_reasons=blocking,
        status=status,
        schema_contract_status=schema_status,
        pit_timestamp_contract_status=pit_status,
        missing_fields=missing_fields,
        missing_timestamp_fields=missing_ts,
        dry_run_row_count=len(rows),
        mapping_applied=mapping_applied,
        schema_mapping_status=schema_mapping_status,
        schema_mapping_ready=schema_mapping_ready,
        schema_mapping_report_path=schema_mapping_report_path,
        schema_mapping_blocking_reasons=schema_mapping_blocking,
    )


def run_managed_proxy_pit_timestamp_dry_run(*, client: Any | None = None) -> dict[str, Any]:
    return run_managed_proxy_schema_dry_run(client=client)

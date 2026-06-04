from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .managed_data_proxy_service import (
    MANAGED_RESEARCH_GROUPS,
    MANAGED_REQUIRED_RESEARCH_FIELDS,
    _client,
    _headers,
    _history_path,
    _managed_endpoint,
    _managed_token,
    managed_proxy_status,
    normalize_managed_fundamental_rows,
)


HEALTH_FILENAME = "managed_proxy_health.json"
READY_STATUS = "success_with_required_fields"
BLOCKING_STATUS_REASONS = {
    "disabled": "managed_proxy_disabled",
    "token_missing": "managed_proxy_token_missing",
    "base_url_missing": "managed_proxy_base_url_missing",
    "endpoint_missing": "managed_proxy_base_url_missing",
    "auth_failed": "managed_proxy_auth_failed",
    "endpoint_unreachable": "managed_proxy_endpoint_unreachable",
    "schema_missing_fields": "managed_proxy_schema_missing_fields",
}
NEXT_ALLOWED_ACTIONS = {
    "disabled": "configure_managed_proxy_endpoint_and_token",
    "token_missing": "configure_managed_proxy_token",
    "base_url_missing": "configure_managed_proxy_endpoint",
    "endpoint_missing": "configure_managed_proxy_endpoint",
    "auth_failed": "verify_managed_proxy_token",
    "endpoint_unreachable": "check_managed_proxy_endpoint",
    "schema_missing_fields": "update_managed_proxy_schema_or_wait_for_required_fields",
    READY_STATUS: "build_feature_store_v12",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / HEALTH_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _fundamentals_status_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_proxy_status.json"


def _fundamentals_data_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_fundamentals.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_health(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _output_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _enabled(token_configured: bool, endpoint_configured: bool) -> bool:
    env_enabled = os.getenv("SN_MANAGED_DATA_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    return bool(token_configured or endpoint_configured or env_enabled)


def _configured_payload() -> dict[str, Any]:
    token = _managed_token()
    endpoint = _managed_endpoint()
    token_configured = bool(token.get("configured"))
    endpoint_configured = bool(endpoint)
    return {
        "enabled": _enabled(token_configured, endpoint_configured),
        "configured": bool(token_configured and endpoint_configured),
        "token_configured": token_configured,
        "endpoint_configured": endpoint_configured,
        "token_masked": str(token.get("masked") or ""),
        "token_source": str(token.get("source") or "none"),
        "_token_value": str(token.get("value") or ""),
        "_endpoint_value": endpoint,
    }


def _available_fields_from_rows(rows: list[Mapping[str, Any]]) -> list[str]:
    available: set[str] = set()
    for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
        for row in rows:
            value = row.get(field)
            if value is not None and value != "":
                available.add(field)
                break
    return sorted(available)


def _available_fields_from_current_files() -> list[str]:
    payload = _read_json(_fundamentals_data_path())
    rows = []
    if isinstance(payload, Mapping):
        raw_rows = payload.get("rows")
        rows = raw_rows if isinstance(raw_rows, list) else []
    normalized = normalize_managed_fundamental_rows(rows)
    return _available_fields_from_rows(normalized)


def _group_ready(available_fields: list[str]) -> dict[str, bool]:
    available = set(available_fields)
    required = set(MANAGED_REQUIRED_RESEARCH_FIELDS)
    group_status: dict[str, bool] = {}
    for group, fields in MANAGED_RESEARCH_GROUPS.items():
        numeric_fields = [field for field in fields if field in required]
        group_status[group] = bool(numeric_fields and set(numeric_fields).issubset(available))
    return group_status


def _coverage(available_fields: list[str], missing_fields: list[str]) -> dict[str, Any]:
    total = len(MANAGED_REQUIRED_RESEARCH_FIELDS)
    available = len(available_fields)
    ratio = round(available / total, 4) if total else 0.0
    return {
        "total": total,
        "available": available,
        "missing": len(missing_fields),
        "ratio": ratio,
        "label": f"{available}/{total}",
    }


def _status_from_config(config: Mapping[str, Any]) -> str | None:
    if not config.get("enabled"):
        return "disabled"
    if not config.get("token_configured"):
        return "token_missing"
    if not config.get("endpoint_configured"):
        return "base_url_missing"
    return None


def _status_from_saved_file() -> str:
    status_file = _read_json(_fundamentals_status_path())
    if not isinstance(status_file, Mapping):
        return "configured"
    raw = str(status_file.get("status") or "configured")
    return "base_url_missing" if raw == "endpoint_missing" else raw


def _base_health(
    *,
    provider_status: str,
    config: Mapping[str, Any],
    available_fields: list[str] | None = None,
    error_message_zh: str = "",
    write: bool = True,
) -> dict[str, Any]:
    available = sorted(set(available_fields or []))
    missing = sorted(set(MANAGED_REQUIRED_RESEARCH_FIELDS) - set(available))
    groups = _group_ready(available)
    ready = bool(provider_status == READY_STATUS and not missing and all(groups.values()) and config.get("configured"))
    status = "ready" if ready else "blocked"
    blocking = [] if ready else [BLOCKING_STATUS_REASONS.get(provider_status, "managed_proxy_not_ready")]
    if missing and "managed_proxy_schema_missing_fields" not in blocking and provider_status in {"configured", "success", "using_cache"}:
        blocking.append("managed_proxy_schema_missing_fields")
    status_file = _read_json(_fundamentals_status_path())
    status_file = status_file if isinstance(status_file, Mapping) else {}
    payload = {
        "status": status,
        "provider_status": provider_status,
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("configured")),
        "endpoint_configured": bool(config.get("endpoint_configured")),
        "token_configured": bool(config.get("token_configured")),
        "token_masked": str(config.get("token_masked") or ""),
        "token_source": str(config.get("token_source") or "none"),
        "last_refresh_time": str(status_file.get("generated_at") or ""),
        "last_success_time": str(status_file.get("last_success_time") or ""),
        "row_count": int(status_file.get("row_count") or 0),
        "from_cache": bool(status_file.get("from_cache") or False),
        "required_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
        "available_fields": available,
        "missing_fields": missing,
        "group_ready": groups,
        "required_field_coverage": _coverage(available, missing),
        "blocking_reasons": sorted(set(blocking)),
        "next_allowed_action": NEXT_ALLOWED_ACTIONS.get(provider_status, "check_managed_proxy_health"),
        "v12_allowed": ready,
        "ready": ready,
        "no_fake_data": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
        "active_model_written": False,
        "customer_prediction_generated": False,
        "error_message_zh": error_message_zh,
        "output_path": str(_output_path()),
        "generated_at": _now(),
        "message_zh": "managed proxy ready for Feature Store v12." if ready else "managed proxy blocked for Feature Store v12.",
    }
    return _write_health(payload) if write else sanitize_for_json(payload)


def get_managed_proxy_health(*, write: bool = True) -> dict[str, Any]:
    config = _configured_payload()
    config_status = _status_from_config(config)
    if config_status:
        return _base_health(provider_status=config_status, config=config, write=write)

    saved_status = _status_from_saved_file()
    available = _available_fields_from_current_files()
    provider_status = READY_STATUS if saved_status in {"success", "using_cache"} and not set(MANAGED_REQUIRED_RESEARCH_FIELDS) - set(available) else saved_status
    if provider_status == "endpoint_missing":
        provider_status = "base_url_missing"
    if provider_status not in {READY_STATUS, "auth_failed", "endpoint_unreachable", "schema_missing_fields"} and set(MANAGED_REQUIRED_RESEARCH_FIELDS) - set(available):
        provider_status = "schema_missing_fields" if saved_status in {"success", "using_cache"} else provider_status
    return _base_health(provider_status=provider_status, config=config, available_fields=available, write=write)


def check_managed_proxy_health(*, client: Any | None = None, write: bool = True) -> dict[str, Any]:
    config = _configured_payload()
    config_status = _status_from_config(config)
    if config_status:
        return _base_health(provider_status=config_status, config=config, write=write)

    token = str(config.get("_token_value") or "")
    endpoint = str(config.get("_endpoint_value") or "")
    try:
        payload = _client(endpoint, client).get_json(_history_path(), _headers(token))
    except HTTPError as exc:
        code = getattr(exc, "code", 0)
        provider_status = "auth_failed" if int(code or 0) in {401, 403} else "endpoint_unreachable"
        return _base_health(
            provider_status=provider_status,
            config=config,
            error_message_zh=sanitize_text(str(exc), extra_secrets=[token, endpoint]),
            write=write,
        )
    except URLError as exc:
        return _base_health(
            provider_status="endpoint_unreachable",
            config=config,
            error_message_zh=sanitize_text(str(exc), extra_secrets=[token, endpoint]),
            write=write,
        )
    except Exception as exc:
        return _base_health(
            provider_status="endpoint_unreachable",
            config=config,
            error_message_zh=sanitize_text(str(exc), extra_secrets=[token, endpoint]),
            write=write,
        )

    rows = normalize_managed_fundamental_rows(payload.get("rows") if isinstance(payload, Mapping) else [])
    available = _available_fields_from_rows(rows)
    missing = sorted(set(MANAGED_REQUIRED_RESEARCH_FIELDS) - set(available))
    provider_status = READY_STATUS if rows and not missing and all(_group_ready(available).values()) else "schema_missing_fields"
    return _base_health(provider_status=provider_status, config=config, available_fields=available, write=write)


def get_managed_proxy_readiness() -> dict[str, Any]:
    health = get_managed_proxy_health()
    return sanitize_for_json(
        {
            "status": health.get("status"),
            "ready": bool(health.get("v12_allowed")),
            "v12_allowed": bool(health.get("v12_allowed")),
            "provider_status": health.get("provider_status"),
            "required_field_coverage": health.get("required_field_coverage"),
            "required_fields": health.get("required_fields"),
            "available_fields": health.get("available_fields"),
            "missing_fields": health.get("missing_fields"),
            "group_ready": health.get("group_ready"),
            "blocking_reasons": health.get("blocking_reasons"),
            "next_allowed_action": health.get("next_allowed_action"),
            "no_fake_data": True,
            "active_model_written": False,
            "customer_prediction_generated": False,
            "generated_at": health.get("generated_at"),
        }
    )

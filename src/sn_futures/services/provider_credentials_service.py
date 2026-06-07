from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


CREDENTIALS_VERSION = "local_api_provider_credentials_v1"
CREDENTIALS_REPORT_FILENAME = "local_api_provider_credentials_report.json"

PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "twelvedata": ("SN_TWELVEDATA_API_KEY",),
    "alphavantage": ("SN_ALPHA_VANTAGE_API_KEY", "SN_ALPHA_VANTAGE_KEY"),
    "fred": ("SN_FRED_API_KEY",),
    "custom_http_provider": ("SN_LOCAL_API_PROVIDER_TOKEN", "SN_CUSTOM_HTTP_PROVIDER_API_KEY"),
}

PROVIDER_METADATA: dict[str, dict[str, Any]] = {
    "twelvedata": {
        "display_name": "Twelve Data",
        "research_only": False,
        "production_eligible": True,
        "realtime_guarantee": True,
        "can_unlock_v12": True,
    },
    "alphavantage": {
        "display_name": "Alpha Vantage",
        "research_only": False,
        "production_eligible": True,
        "realtime_guarantee": False,
        "can_unlock_v12": True,
    },
    "fred": {
        "display_name": "FRED",
        "research_only": False,
        "production_eligible": True,
        "realtime_guarantee": False,
        "can_unlock_v12": True,
    },
    "yfinance_research_only": {
        "display_name": "yfinance",
        "research_only": True,
        "production_eligible": False,
        "realtime_guarantee": False,
        "can_unlock_v12": False,
    },
    "custom_http_provider": {
        "display_name": "Custom HTTP Provider",
        "research_only": False,
        "production_eligible": True,
        "realtime_guarantee": False,
        "can_unlock_v12": True,
    },
}

REQUIRED_PROVIDER_CREDENTIALS = ("twelvedata", "alphavantage")
LEGACY_MANAGED_PROXY_ENV_KEYS = (
    "SN_MANAGED_PROXY_ENABLED",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_DATA_PROXY_ENABLED",
    "SN_MANAGED_DATA_PROXY_URL",
    "SN_MANAGED_DATA_PROXY_TOKEN",
)
LOCAL_API_PROVIDER_BASE_URL_KEYS = ("SN_LOCAL_API_PROVIDER_BASE_URL",)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / CREDENTIALS_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _clean_env_value(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text or lowered in {"masked", "[masked]", "redacted", "[redacted]", "configured", "your_api_key_here"}:
        return ""
    if set(text) <= {"*"}:
        return ""
    return text


def _env_value(names: tuple[str, ...]) -> tuple[str, str]:
    for name in names:
        value = _clean_env_value(os.environ.get(name, ""))
        if value:
            return value, name
    return "", "none"


def detect_legacy_managed_proxy_status() -> dict[str, Any]:
    configured = [name for name in LEGACY_MANAGED_PROXY_ENV_KEYS if _clean_env_value(os.environ.get(name, ""))]
    return _safe(
        {
            "status": "legacy_enterprise_proxy_detected" if configured else "not_configured",
            "mode": "legacy_enterprise_proxy",
            "configured": bool(configured),
            "configured_vars": sorted(configured),
            "required_for_local_mode": False,
            "message": (
                "Legacy enterprise/proxy variables are detected. Local API provider mode remains the default."
                if configured
                else "No legacy managed proxy variables detected."
            ),
        }
    )


def _provider_payload(provider_id: str) -> dict[str, Any]:
    metadata = dict(PROVIDER_METADATA[provider_id])
    value, source = _env_value(PROVIDER_ENV_KEYS.get(provider_id, ()))
    base_url, base_url_source = ("", "none")
    if provider_id == "custom_http_provider":
        base_url, base_url_source = _env_value(LOCAL_API_PROVIDER_BASE_URL_KEYS)
    key_configured = bool(value)
    if provider_id == "custom_http_provider":
        key_configured = bool(value and base_url)
    return _safe(
        {
            "provider_id": provider_id,
            **metadata,
            "key_configured": key_configured,
            "key_masked": mask_secret(value) if key_configured else "",
            "key_source": source if key_configured else "none",
            "base_url_configured": bool(base_url) if provider_id == "custom_http_provider" else False,
            "base_url_source": base_url_source if base_url else "none",
            "credential_handoff_required": not key_configured and not bool(metadata.get("research_only")),
        }
    )


def build_safe_provider_setup_commands() -> list[str]:
    return [
        '$env:SN_LOCAL_API_PROVIDER_ENABLED="true"',
        '$env:SN_LOCAL_API_PROVIDER_ID="custom_http_provider"',
        '$env:SN_LOCAL_API_PROVIDER_BASE_URL="https://your-local-provider.example.com"',
        '$env:SN_LOCAL_API_PROVIDER_TOKEN="<paste-token-only-in-your-local-shell>"',
        '$env:SN_DATA_PROVIDER_PRIMARY="twelvedata"',
        '$env:SN_MARKET_DATA_PROVIDER="twelvedata"',
        '$env:SN_MACRO_DATA_PROVIDER="fred"',
        '$env:SN_TWELVEDATA_API_KEY="<paste-key-only-in-your-local-shell>"',
        '$env:SN_ALPHA_VANTAGE_API_KEY="<paste-key-only-in-your-local-shell>"',
        '$env:SN_FRED_API_KEY="<paste-key-only-in-your-local-shell>"',
        '$env:SN_PROVIDER_TIMEOUT_SECONDS="10"',
        '$env:SN_LOCAL_CACHE_ENABLED="true"',
    ]


def build_provider_credential_handoff(*, write: bool = True) -> dict[str, Any]:
    providers = {provider_id: _provider_payload(provider_id) for provider_id in PROVIDER_METADATA}
    configured = [
        provider_id
        for provider_id, details in providers.items()
        if details.get("key_configured") and not details.get("research_only")
    ]
    missing_required = [provider_id for provider_id in REQUIRED_PROVIDER_CREDENTIALS if provider_id not in configured]
    legacy_status = detect_legacy_managed_proxy_status()
    warnings: list[str] = []
    if legacy_status.get("configured"):
        warnings.append("legacy_managed_proxy_vars_detected")

    payload = {
        "status": "configured" if configured else "missing_config",
        "generated_at": _now(),
        "credentials_version": CREDENTIALS_VERSION,
        "provider_mode": "local_api_provider",
        "current_step": "configure_local_api_provider_credentials",
        "provider_credentials_status": "configured" if configured else "missing_config",
        "configured_providers": configured,
        "missing_provider_credentials": missing_required,
        "providers": providers,
        "safe_config_methods": ["local_shell_env", "ignored_local_config"],
        "copy_safe_setup_commands": build_safe_provider_setup_commands(),
        "local_cache_policy": {
            "name": "local_verified_api_cache",
            "production_managed_cache": False,
            "fields_recorded": [
                "provider",
                "request_time",
                "source_timestamp",
                "asof_date",
                "ingest_timestamp",
                "freshness",
            ],
        },
        "legacy_managed_proxy_status": legacy_status,
        "blocking_reasons": ["provider_api_key_missing"] if not configured else [],
        "warning_reasons": warnings,
        "feature_store_v12_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe(payload)
    if write:
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def get_provider_credentials_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, Mapping):
            return _safe(dict(payload))
    return build_provider_credential_handoff(write=False)


def refresh_provider_credentials_report() -> dict[str, Any]:
    return build_provider_credential_handoff(write=True)

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .provider_credentials_service import build_provider_credential_handoff, refresh_provider_credentials_report
from .provider_smoke_test_service import get_latest_provider_smoke_report


HUB_VERSION = "local_api_provider_hub_v1"
HUB_REPORT_FILENAME = "local_api_provider_hub_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / HUB_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _smoke_status(smoke: Mapping[str, Any]) -> str:
    return str(smoke.get("status") or "not_run").strip() or "not_run"


def build_local_api_provider_hub(*, write: bool = True) -> dict[str, Any]:
    credentials = build_provider_credential_handoff(write=False)
    smoke = get_latest_provider_smoke_report()
    configured = list(credentials.get("configured_providers") or [])
    missing = list(credentials.get("missing_provider_credentials") or [])
    provider_credentials_status = str(credentials.get("provider_credentials_status") or "missing_config")
    smoke_status = _smoke_status(_as_mapping(smoke))
    current_step = "configure_local_api_provider_credentials"
    if configured and smoke_status not in {"pass", "research_only"}:
        current_step = "run_provider_smoke"
    if configured and smoke_status == "pass":
        current_step = "safe_refresh_data_status"

    legacy_status = _as_mapping(credentials.get("legacy_managed_proxy_status"))
    warnings = list(credentials.get("warning_reasons") or [])
    if legacy_status.get("configured") and "legacy_managed_proxy_vars_detected" not in warnings:
        warnings.append("legacy_managed_proxy_vars_detected")
    blocking = []
    if provider_credentials_status != "configured":
        blocking.append("provider_api_key_missing")
    if configured and smoke_status not in {"pass", "research_only"}:
        blocking.append("provider_smoke_not_passed")

    yfinance = _as_mapping(_as_mapping(credentials.get("providers")).get("yfinance_research_only"))
    payload = {
        "status": "ready_for_refresh" if configured and smoke_status == "pass" else ("ready_for_smoke" if configured else "blocked"),
        "generated_at": _now(),
        "hub_version": HUB_VERSION,
        "provider_mode": "local_api_provider",
        "current_step": current_step,
        "provider_credentials_status": provider_credentials_status,
        "configured_providers": configured,
        "missing_provider_credentials": missing,
        "managed_proxy_required": False,
        "legacy_managed_proxy_status": legacy_status,
        "yfinance_research_only": {
            "research_only": bool(yfinance.get("research_only", True)),
            "production_eligible": bool(yfinance.get("production_eligible", False)),
            "realtime_guarantee": bool(yfinance.get("realtime_guarantee", False)),
            "can_unlock_v12": bool(yfinance.get("can_unlock_v12", False)),
        },
        "provider_smoke_status": smoke_status,
        "provider_smoke": smoke,
        "provider_credentials": credentials,
        "local_cache_policy": credentials.get("local_cache_policy") or {},
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "warning_reasons": list(dict.fromkeys(warnings)),
        "next_allowed_action": (
            "configure_local_api_provider_credentials"
            if not configured
            else ("safe_refresh_data_status" if smoke_status == "pass" else "run_provider_smoke")
        ),
        "safe_refresh_available": bool(configured and smoke_status == "pass"),
        "feature_store_v12_allowed": False,
        "feature_store_written": False,
        "backtest_invoked": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe(payload)
    if write:
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def get_local_api_provider_hub() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, Mapping):
            return _safe(dict(payload))
    return build_local_api_provider_hub(write=False)


def refresh_local_api_provider_hub() -> dict[str, Any]:
    refresh_provider_credentials_report()
    return build_local_api_provider_hub(write=True)

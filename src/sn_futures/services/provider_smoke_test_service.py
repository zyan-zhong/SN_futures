from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .provider_credentials_service import build_provider_credential_handoff
from .provider_schema_normalizer_service import normalize_provider_sample


SMOKE_VERSION = "local_api_provider_smoke_v1"
SMOKE_REPORT_FILENAME = "local_api_provider_smoke_report.json"


class MinimalProviderClient(Protocol):
    def fetch_minimal_sample(self, provider_id: str) -> Mapping[str, Any]:
        ...


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / SMOKE_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _blocked(provider_id: str, reasons: list[str], *, status: str = "blocked") -> dict[str, Any]:
    return _safe(
        {
            "status": status,
            "generated_at": _now(),
            "smoke_version": SMOKE_VERSION,
            "provider": provider_id,
            "provider_mode": "local_api_provider",
            "auth_status": "blocked",
            "endpoint_reachable": False,
            "field_coverage": {"fields_seen": [], "missing_canonical_fields": []},
            "rate_limit_warning": "",
            "freshness_status": "not_run",
            "research_only": provider_id == "yfinance_research_only",
            "production_eligible": False,
            "realtime_guarantee": False,
            "feature_store_v12_allowed": False,
            "feature_store_written": False,
            "production_cache_written": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "blocking_reasons": reasons,
            "report_path": str(_report_path()),
        }
    )


def run_provider_smoke_test(
    provider_id: str = "twelvedata",
    *,
    client: MinimalProviderClient | None = None,
    write: bool = True,
) -> dict[str, Any]:
    provider = str(provider_id or "twelvedata").strip().lower()
    credentials = build_provider_credential_handoff(write=False)
    providers = credentials.get("providers") if isinstance(credentials.get("providers"), Mapping) else {}
    provider_details = providers.get(provider) if isinstance(providers, Mapping) else None
    if not isinstance(provider_details, Mapping):
        payload = _blocked(provider, ["unknown_provider"])
    elif provider != "yfinance_research_only" and not provider_details.get("key_configured"):
        payload = _blocked(provider, ["provider_key_missing"])
    else:
        sample: Mapping[str, Any] = {}
        if client is not None:
            try:
                sample = client.fetch_minimal_sample(provider)
            except Exception as exc:
                payload = _blocked(provider, [f"provider_smoke_failed:{type(exc).__name__}"])
                if write:
                    _report_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return payload
        normalized = normalize_provider_sample(provider, sample)
        research_only = bool(provider_details.get("research_only"))
        payload = _safe(
            {
                "status": "research_only" if research_only else "pass",
                "generated_at": _now(),
                "smoke_version": SMOKE_VERSION,
                "provider": provider,
                "provider_mode": "local_api_provider",
                "auth_status": "pass",
                "endpoint_reachable": True,
                "field_coverage": normalized,
                "rate_limit_warning": "",
                "freshness_status": normalized.get("freshness_status") or "unknown",
                "research_only": research_only,
                "production_eligible": bool(provider_details.get("production_eligible")) and not research_only,
                "realtime_guarantee": bool(provider_details.get("realtime_guarantee")) and not research_only,
                "feature_store_v12_allowed": False,
                "feature_store_written": False,
                "production_cache_written": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
                "blocking_reasons": ["yfinance_research_only_cannot_unlock_v12"] if research_only else [],
                "report_path": str(_report_path()),
            }
        )
    if write:
        _report_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_latest_provider_smoke_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, Mapping):
            return _safe(dict(payload))
    return _blocked("twelvedata", ["provider_smoke_not_run"], status="not_run")

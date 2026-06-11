from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


PUBLIC_FIREWALL_ERROR_CODE = "no_demo_public_firewall"
PIPELINE_FIREWALL_ERROR_CODE = "no_demo_pipeline_firewall"

DIRTY_DATA_FLAGS = {
    "sample",
    "sample_mode",
    "sample_data_used",
    "demo",
    "demo_data_used",
    "fake",
    "fake_data_used",
    "mock_data_used",
    "baseline",
    "baseline_used",
    "sample_report",
    "demo_forecast",
}

DOWNSTREAM_SIDE_EFFECT_FLAGS = {
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "feature_store_written",
    "production_cache_written",
    "customer_prediction_generated",
}

RESEARCH_ALLOW_FLAGS = {
    "allowed_for_public",
    "allowed_for_feature_store",
    "allowed_for_training",
    "allowed_for_prediction",
    "allowed_for_backtest",
}

PIPELINE_TO_ALLOW_FLAG = {
    "public": "allowed_for_public",
    "feature_store": "allowed_for_feature_store",
    "training": "allowed_for_training",
    "prediction": "allowed_for_prediction",
    "backtest": "allowed_for_backtest",
}


@dataclass(frozen=True)
class DataSafetyViolation(Exception):
    error_code: str
    blocking_reasons: list[str]
    details_sanitized: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.error_code}: {', '.join(self.blocking_reasons)}"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "allowed", "success", "sample", "demo", "fake"}
    return bool(value)


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    yield prefix, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]" if prefix else f"[{index}]"
            yield from _walk(item, child)


def _safe_fixture_only(item: Mapping[str, Any]) -> bool:
    if not (_truthy(item.get("fixture")) or _truthy(item.get("fixture_only"))):
        return False
    return all(item.get(flag) is False for flag in RESEARCH_ALLOW_FLAGS)


def _dirty_flags(payload: Mapping[str, Any], *, skip_safe_fixture_evidence: bool = False) -> list[str]:
    flags: set[str] = set()
    for _, item in _walk(payload):
        if not isinstance(item, Mapping):
            continue
        if skip_safe_fixture_evidence and item is not payload and _safe_fixture_only(item):
            continue
        for flag in DIRTY_DATA_FLAGS:
            if _truthy(item.get(flag)):
                flags.add(flag)
        for flag in DOWNSTREAM_SIDE_EFFECT_FLAGS:
            if _truthy(item.get(flag)):
                flags.add(flag)
    return sorted(flags)


def _allowed_true_flags(payload: Mapping[str, Any]) -> list[str]:
    flags: set[str] = set()
    for _, item in _walk(payload):
        if not isinstance(item, Mapping):
            continue
        for flag in RESEARCH_ALLOW_FLAGS:
            if _truthy(item.get(flag)):
                flags.add(flag)
    return sorted(flags)


def mark_fixture_manifest(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(manifest or {})
    payload["fixture"] = True
    payload["fixture_only"] = True
    payload["allowed_for_public"] = False
    payload["allowed_for_feature_store"] = False
    payload["allowed_for_training"] = False
    payload["allowed_for_prediction"] = False
    payload["allowed_for_backtest"] = False
    return payload


def assert_manifest_allowed_for_pipeline(
    manifest: Mapping[str, Any] | None,
    *,
    pipeline: str,
) -> dict[str, Any]:
    payload = dict(manifest or {})
    pipeline_key = str(pipeline or "").strip().lower()
    dirty = _dirty_flags(payload, skip_safe_fixture_evidence=True)
    reasons: list[str] = list(dirty)
    if _truthy(payload.get("fixture")) or _truthy(payload.get("fixture_only")):
        reasons.append("fixture")
    allowed_flag = PIPELINE_TO_ALLOW_FLAG.get(pipeline_key)
    if allowed_flag and _truthy(payload.get(allowed_flag)) and reasons:
        reasons.append(allowed_flag)
    for flag in _allowed_true_flags(payload):
        if reasons and flag not in reasons:
            reasons.append(flag)
    if reasons:
        raise DataSafetyViolation(
            error_code=PIPELINE_FIREWALL_ERROR_CODE,
            blocking_reasons=sorted(set(reasons)),
            details_sanitized={
                "pipeline": pipeline_key,
                "dirty_flag_count": len(dirty),
                "fixture": bool(_truthy(payload.get("fixture")) or _truthy(payload.get("fixture_only"))),
            },
        )
    return payload


def blocked_manifest_from_violation(
    violation: DataSafetyViolation,
    *,
    status: str = "blocked",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(extra or {})
    payload.update(
        {
            "status": status,
            "error_code": violation.error_code,
            "blocking_reasons": sorted(set([*payload.get("blocking_reasons", []), *violation.blocking_reasons])),
            "details_sanitized": dict(violation.details_sanitized),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "mock_data_used": False,
            "fixture": False,
            "allowed_for_public": False,
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "training_invoked": False,
            "prediction_generated": False,
            "backtest_invoked": False,
            "feature_store_written": False,
            "customer_prediction_generated": False,
        }
    )
    return payload


def _public_blocked_payload(payload: Mapping[str, Any], *, violation_count: int) -> dict[str, Any]:
    blocked: dict[str, Any] = {
        "status": "blocked",
        "error_code": PUBLIC_FIREWALL_ERROR_CODE,
        "message": "Public Terminal blocked non-real fixture output.",
        "blocking_reasons": ["non_real_public_payload_blocked"],
        "details_sanitized": {
            "policy": PUBLIC_FIREWALL_ERROR_CODE,
            "violation_count": int(violation_count),
        },
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
        "mock_data_used": False,
        "fixture": False,
        "training_invoked": False,
        "prediction_generated": False,
        "backtest_invoked": False,
        "feature_store_written": False,
        "customer_prediction_generated": False,
    }
    if "cards" in payload:
        blocked["cards"] = {}
    if "data_watermark" in payload or "provider_smoke_passed" in payload or "ready_for_refresh" in payload:
        blocked.update(
            {
                "summary": "Public output blocked by the data safety firewall.",
                "next_action": "open_diagnostics",
                "provider_smoke_passed": False,
                "ready_for_refresh": False,
                "data_watermark": {
                    "status": "blocked",
                    "reason": PUBLIC_FIREWALL_ERROR_CODE,
                    "sample_data_used": False,
                    "baseline_used": False,
                    "customer_prediction_generated": False,
                },
                "provider_status": {},
            }
        )
    if "market" in payload:
        blocked["market"] = {
            "status": "blocked",
            "reason": PUBLIC_FIREWALL_ERROR_CODE,
            "chart": [],
            "latest_quote": None,
            "sample_data_used": False,
            "baseline_used": False,
            "customer_prediction_generated": False,
        }
    if "report" in payload:
        blocked["report"] = {
            "status": "blocked",
            "reason": PUBLIC_FIREWALL_ERROR_CODE,
            "provider_status": "blocked",
            "market_data_coverage": "empty",
            "event_coverage": "empty",
            "research_only": True,
            "investment_advice": False,
            "export_allowed": False,
        }
    return blocked


def assert_public_payload_real_or_blocked(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    public_payload = dict(payload or {})
    dirty = _dirty_flags(public_payload)
    if not dirty:
        return public_payload
    return _public_blocked_payload(public_payload, violation_count=len(dirty))

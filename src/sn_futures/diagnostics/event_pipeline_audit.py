from __future__ import annotations

from typing import Any

from .event_feature_audit import audit_event_features
from .event_ingestion_audit import audit_event_ingestion
from .event_model_usage_audit import audit_event_model_usage


def audit_event_pipeline(evidence: dict[str, Any]) -> dict[str, Any]:
    ingestion = audit_event_ingestion(evidence)
    features = audit_event_features(evidence)
    usage = audit_event_model_usage(evidence)
    ok = bool(ingestion.get("ok")) and bool(features.get("ok")) and bool(usage.get("ok"))
    warnings = []
    if not ingestion.get("ok"):
        warnings.append("event_ingestion_unhealthy")
    if not features.get("ok"):
        warnings.append("event_features_empty")
    if not usage.get("ok"):
        warnings.append("event_not_used_in_model")
    return {
        "ok": ok,
        "status": "pass" if ok else "warning",
        "summary": "事件链路通过" if ok else "事件链路需要关注：" + "、".join(warnings),
        "recognized_event_count": evidence.get("recognized_event_count", 0),
        "valid_event_count": evidence.get("valid_event_count", 0),
        "used_in_model_event_count": evidence.get("used_in_model_event_count", 0),
        "rejected_event_count": evidence.get("rejected_event_count", 0),
        "rejected_reason_breakdown": evidence.get("rejected_reason_breakdown", {}),
        "event_source_count": evidence.get("event_source_count", 0),
        "tier1_event_count": evidence.get("tier1_event_count", 0),
        "tier2_event_count": evidence.get("tier2_event_count", 0),
        "tier3_event_count": evidence.get("tier3_event_count", 0),
        "events_with_url_count": evidence.get("events_with_url_count", 0),
        "events_with_available_at_count": evidence.get("events_with_available_at_count", 0),
        "events_with_symbol_tags_count": evidence.get("events_with_symbol_tags_count", 0),
        "events_with_direction_bias_count": evidence.get("events_with_direction_bias_count", 0),
        "events_with_impact_score_count": evidence.get("events_with_impact_score_count", 0),
        "event_feature_nonzero_count": evidence.get("event_feature_nonzero_count", 0),
        "event_factor_weight": evidence.get("event_factor_weight", 0.0),
        "event_factor_direction": evidence.get("event_factor_direction", "neutral"),
        "event_feature_hash": evidence.get("event_feature_hash", ""),
        "sections": {
            "ingestion": ingestion,
            "features": features,
            "model_usage": usage,
        },
    }


from __future__ import annotations

from typing import Any


def audit_event_model_usage(evidence: dict[str, Any]) -> dict[str, Any]:
    used = int(evidence.get("used_in_model_event_count", 0) or 0)
    recognized = int(evidence.get("recognized_event_count", 0) or 0)
    rejected = int(evidence.get("rejected_event_count", 0) or 0)
    reasons = evidence.get("rejected_reason_breakdown", {}) if isinstance(evidence.get("rejected_reason_breakdown"), dict) else {}
    ok = used > 0 or recognized == 0
    return {
        "ok": ok,
        "used_in_model_event_count": used,
        "recognized_event_count": recognized,
        "rejected_event_count": rejected,
        "rejected_reason_breakdown": reasons,
        "event_factor_weight": evidence.get("event_factor_weight", 0.0),
        "event_factor_direction": evidence.get("event_factor_direction", "neutral"),
        "reason": "" if ok else "used_in_model_event_count_is_zero",
    }


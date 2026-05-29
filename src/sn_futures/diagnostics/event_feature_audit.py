from __future__ import annotations

from typing import Any


def audit_event_features(evidence: dict[str, Any]) -> dict[str, Any]:
    nonzero = int(evidence.get("event_feature_nonzero_count", 0) or 0)
    used = int(evidence.get("used_in_model_event_count", 0) or 0)
    recognized = int(evidence.get("recognized_event_count", 0) or 0)
    ok = nonzero > 0 or recognized == 0
    return {
        "ok": ok,
        "recognized_event_count": recognized,
        "used_in_model_event_count": used,
        "event_feature_nonzero_count": nonzero,
        "event_feature_hash": evidence.get("event_feature_hash", ""),
        "reason": "" if ok else "recognized_events_but_all_event_features_zero",
    }


from __future__ import annotations

from typing import Any


def audit_event_ingestion(evidence: dict[str, Any]) -> dict[str, Any]:
    provider_status = evidence.get("provider_status", []) if isinstance(evidence.get("provider_status"), list) else []
    source_count = int(evidence.get("event_source_count", 0) or 0)
    return {
        "ok": source_count > 0 or bool(provider_status),
        "recognized_event_count": int(evidence.get("recognized_event_count", 0) or 0),
        "event_source_count": source_count,
        "provider_status_count": len(provider_status),
        "tier1_event_count": int(evidence.get("tier1_event_count", 0) or 0),
        "tier2_event_count": int(evidence.get("tier2_event_count", 0) or 0),
        "tier3_event_count": int(evidence.get("tier3_event_count", 0) or 0),
    }


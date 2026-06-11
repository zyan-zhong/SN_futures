from __future__ import annotations

from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..resource_manager.scheduler import ResourceSnapshot, plan_resource_allocation


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "dev", "development"}
    return bool(value)


def evaluate_training_resource_policy(
    request: Mapping[str, Any],
    *,
    resources: ResourceSnapshot | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_payload = dict(request)
    resource_plan = plan_resource_allocation(request_payload.get("requested_resources"), resources)
    blocking = list(resource_plan.get("blocking_reasons") or [])
    if not _truthy(request_payload.get("dev_mode")):
        blocking.append("dev_mode_required")
    return sanitize_for_json(
        {
            "status": "blocked" if blocking else "ready",
            "dev_only": True,
            "dev_mode": _truthy(request_payload.get("dev_mode")),
            "resource_plan": resource_plan,
            "blocking_reasons": sorted(set(str(reason) for reason in blocking if str(reason))),
        }
    )

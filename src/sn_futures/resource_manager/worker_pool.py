from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json


@dataclass(frozen=True)
class WorkerPoolSnapshot:
    running_jobs: int = 0
    max_workers: int = 1
    backoff_until: str = ""
    busy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def normalise_worker_pool(payload: WorkerPoolSnapshot | Mapping[str, Any] | None = None) -> WorkerPoolSnapshot:
    if isinstance(payload, WorkerPoolSnapshot):
        return payload
    data = dict(payload or {})
    return WorkerPoolSnapshot(
        running_jobs=int(data.get("running_jobs") or 0),
        max_workers=max(int(data.get("max_workers") or 1), 1),
        backoff_until=str(data.get("backoff_until") or ""),
        busy=bool(data.get("busy")),
    )


def worker_pool_gate(
    snapshot: WorkerPoolSnapshot | Mapping[str, Any] | None = None,
    *,
    now: str = "",
) -> dict[str, Any]:
    pool = normalise_worker_pool(snapshot)
    reasons: list[str] = []
    if pool.busy or pool.running_jobs >= pool.max_workers:
        reasons.append("resource_busy")
    now_dt = _parse_time(now)
    backoff_dt = _parse_time(pool.backoff_until)
    if now_dt is not None and backoff_dt is not None and now_dt < backoff_dt:
        reasons.append("worker_pool_backoff")
    return sanitize_for_json(
        {
            "status": "blocked" if reasons else "ready",
            "busy": bool(reasons),
            "running_jobs": pool.running_jobs,
            "max_workers": pool.max_workers,
            "backoff_until": pool.backoff_until,
            "blocking_reasons": sorted(set(reasons)),
        }
    )

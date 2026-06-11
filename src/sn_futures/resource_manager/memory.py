from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MemorySnapshot:
    total_gb: float = 0.0
    available_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_memory_snapshot(payload: Mapping[str, Any] | MemorySnapshot | None = None) -> MemorySnapshot:
    if isinstance(payload, MemorySnapshot):
        return payload
    data = dict(payload or {})
    return MemorySnapshot(
        total_gb=float(data.get("total_gb") or 0.0),
        available_gb=float(data.get("available_gb") or 0.0),
    )


def evaluate_memory_limit(
    *,
    required_gb: float,
    snapshot: MemorySnapshot,
    max_fraction_of_available: float = 0.90,
) -> dict[str, Any]:
    required = max(float(required_gb or 0.0), 0.0)
    available = max(float(snapshot.available_gb or 0.0), 0.0)
    usable = available * max_fraction_of_available
    allowed = required <= usable
    return {
        "required_gb": required,
        "available_gb": available,
        "total_gb": max(float(snapshot.total_gb or 0.0), 0.0),
        "usable_gb": usable,
        "max_fraction_of_available": max_fraction_of_available,
        "allowed": allowed,
        "blocking_reasons": [] if allowed else ["memory_limit_exceeded"],
    }

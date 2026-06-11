from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class GpuSnapshot:
    available: bool = False
    device_count: int = 0
    name: str = ""
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_gpu_snapshot(payload: Mapping[str, Any] | GpuSnapshot | None = None) -> GpuSnapshot:
    if isinstance(payload, GpuSnapshot):
        return payload
    data = dict(payload or {})
    device_count = int(data.get("device_count") or 0)
    available = bool(data.get("available")) and device_count > 0
    return GpuSnapshot(
        available=available,
        device_count=device_count,
        name=str(data.get("name") or ""),
        memory_total_gb=float(data.get("memory_total_gb") or 0.0),
        memory_available_gb=float(data.get("memory_available_gb") or 0.0),
    )


def detect_gpu() -> GpuSnapshot:
    return GpuSnapshot(available=False, device_count=0)

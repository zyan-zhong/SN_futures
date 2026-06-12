from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from .gpu import GpuSnapshot
from .memory import MemorySnapshot
from .scheduler import ResourceSnapshot, plan_resource_allocation


@dataclass(frozen=True)
class HardwareSnapshot:
    cpu_count: int = 1
    gpu_available: bool = False
    gpu_count: int = 0
    gpu_name: str = ""
    gpu_memory_total_gb: float = 0.0
    gpu_memory_available_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0

    def to_resource_snapshot(self) -> ResourceSnapshot:
        return ResourceSnapshot(
            cpu_count=max(int(self.cpu_count or 1), 1),
            gpu=GpuSnapshot(
                available=bool(self.gpu_available) and int(self.gpu_count or 0) > 0,
                device_count=max(int(self.gpu_count or 0), 0),
                name=str(self.gpu_name or ""),
                memory_total_gb=max(float(self.gpu_memory_total_gb or 0.0), 0.0),
                memory_available_gb=max(float(self.gpu_memory_available_gb or 0.0), 0.0),
            ),
            memory=MemorySnapshot(
                total_gb=max(float(self.ram_total_gb or 0.0), 0.0),
                available_gb=max(float(self.ram_available_gb or 0.0), 0.0),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceBudget:
    requires_gpu: bool = False
    allow_cpu_fallback: bool = True
    memory_gb: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_hardware(payload: HardwareSnapshot | Mapping[str, Any] | ResourceSnapshot | None) -> ResourceSnapshot | None:
    if payload is None:
        return None
    if isinstance(payload, ResourceSnapshot):
        return payload
    if isinstance(payload, HardwareSnapshot):
        return payload.to_resource_snapshot()
    data = dict(payload)
    if "memory" in data or "gpu" in data:
        return ResourceSnapshot(
            cpu_count=int(data.get("cpu_count") or 1),
            gpu=GpuSnapshot(
                available=bool((data.get("gpu") or {}).get("available")) if isinstance(data.get("gpu"), Mapping) else False,
                device_count=int((data.get("gpu") or {}).get("device_count") or 0) if isinstance(data.get("gpu"), Mapping) else 0,
                name=str((data.get("gpu") or {}).get("name") or "") if isinstance(data.get("gpu"), Mapping) else "",
                memory_total_gb=float((data.get("gpu") or {}).get("memory_total_gb") or 0.0) if isinstance(data.get("gpu"), Mapping) else 0.0,
                memory_available_gb=float((data.get("gpu") or {}).get("memory_available_gb") or 0.0) if isinstance(data.get("gpu"), Mapping) else 0.0,
            ),
            memory=MemorySnapshot(
                total_gb=float((data.get("memory") or {}).get("total_gb") or 0.0) if isinstance(data.get("memory"), Mapping) else 0.0,
                available_gb=float((data.get("memory") or {}).get("available_gb") or 0.0) if isinstance(data.get("memory"), Mapping) else 0.0,
            ),
        )
    return HardwareSnapshot(
        cpu_count=int(data.get("cpu_count") or 1),
        gpu_available=bool(data.get("gpu_available")),
        gpu_count=int(data.get("gpu_count") or 0),
        gpu_name=str(data.get("gpu_name") or ""),
        gpu_memory_total_gb=float(data.get("gpu_memory_total_gb") or 0.0),
        gpu_memory_available_gb=float(data.get("gpu_memory_available_gb") or 0.0),
        ram_total_gb=float(data.get("ram_total_gb") or 0.0),
        ram_available_gb=float(data.get("ram_available_gb") or 0.0),
    ).to_resource_snapshot()


def plan_training_resources(
    budget: ResourceBudget | Mapping[str, Any] | None = None,
    *,
    hardware: HardwareSnapshot | Mapping[str, Any] | ResourceSnapshot | None = None,
) -> dict[str, Any]:
    request = budget.to_dict() if isinstance(budget, ResourceBudget) else dict(budget or {})
    plan = plan_resource_allocation(request, _normalise_hardware(hardware))
    return sanitize_for_json(
        {
            "status": plan.get("status"),
            "device": plan.get("device"),
            "budget": request,
            "hardware": plan.get("snapshot"),
            "memory": plan.get("memory"),
            "warnings": plan.get("warnings", []),
            "blocking_reasons": plan.get("blocking_reasons", []),
            "training_invoked": False,
            "prediction_generated": False,
            "backtest_invoked": False,
        }
    )
